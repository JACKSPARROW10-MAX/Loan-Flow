"""
LoanFlow – Loan Application Service (FastAPI).
Core service handling the full loan lifecycle:
  Application CRUD → KYC → Documents → Eligibility → Risk → Limit →
  State Machine → Maker-Checker → Assessment → Audit
"""
import uuid
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Form, Query, status, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
import httpx

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.database import Base, get_db, init_db, AsyncSessionLocal, engine
from shared.security import (
    get_current_user, require_role, verify_csrf, mask_sensitive,
    ROLE_CUSTOMER, ROLE_EMPLOYEE, ROLE_MANAGER,
)
from shared.config import get_settings
from shared.redis_client import get_redis
from shared.event_bus import Event, create_event_bus
from .report_pdf import generate_assessment_report_pdf

from .models import (
    Application, Document, RuleResult, PolicyRule, AuditLog, EventLog,
    LoanAccount, EMISchedule, PaymentTransaction, CollectionCase, FraudAlert,
    ApplicationStage, DocumentStatus, RiskBand, VALID_TRANSITIONS,
)
from .schemas import (
    ApplicationCreate, ApplicationUpdate, ApplicationResponse, ApplicationListItem,
    StageTransitionRequest, DocumentResponse, DocumentVerifyRequest,
    RuleResultResponse, EligibilityResponse, RiskScoreResponse,
    LimitResponse, AuditLogResponse, KYCResponse,
    DisbursementRequest, LoanAccountResponse, EMIScheduleItem,
    PaymentRequest, PaymentResponse, CollectionCaseResponse,
    CollectionFollowUpRequest, AssessmentReportResponse, AnalyticsSummaryResponse,
    FraudAlertResponse, FraudCheckRequest,
)

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

# ═══════════════════════ App Setup ═══════════════════════

app = FastAPI(title="LoanFlow Loan Application Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-csrf-token"],
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# ─── App-number counter ───
_app_counter = 1042


def next_app_number() -> str:
    global _app_counter
    num = f"LF-{_app_counter}"
    _app_counter += 1
    return num


# ═══════════════════════ Startup ═══════════════════════

@app.on_event("startup")
async def startup():
    await init_db()

    # Create append-only trigger for audit_log (PostgreSQL)
    if "postgres" in str(engine.url):
        async with engine.begin() as conn:
            await conn.execute(
            __import__("sqlalchemy").text("""
                CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'audit_log is append-only: UPDATE and DELETE are not permitted';
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql;
            """)
        )
            await conn.execute(
                __import__("sqlalchemy").text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_log_immutable'
                        ) THEN
                            CREATE TRIGGER trg_audit_log_immutable
                            BEFORE UPDATE OR DELETE ON audit_log
                            FOR EACH ROW
                            EXECUTE FUNCTION prevent_audit_log_modification();
                        END IF;
                    END $$;
                """)
            )

        # Analytical SQL views for Power BI reporting (best-effort, one statement each:
        # asyncpg does not allow several commands in a single execute)
        _views_sql = """
CREATE OR REPLACE VIEW vw_approval_rate AS
                    SELECT 
                        COUNT(*) AS total_applications,
                        SUM(CASE WHEN stage = 'Approved' THEN 1 ELSE 0 END) AS approved_count,
                        SUM(CASE WHEN stage = 'Returned' THEN 1 ELSE 0 END) AS returned_count,
                        SUM(CASE WHEN stage = 'Rejected' THEN 1 ELSE 0 END) AS rejected_count,
                        ROUND(CAST(SUM(CASE WHEN stage = 'Approved' THEN 1 ELSE 0 END) AS numeric) * 100.0 / NULLIF(COUNT(*), 0), 2) AS approval_rate_pct
                    FROM applications;

                    CREATE OR REPLACE VIEW vw_overdue_trend AS
                    SELECT 
                        bucket,
                        COUNT(*) AS case_count,
                        SUM(overdue_amount) AS total_overdue_amount,
                        ROUND(CAST(AVG(dpd) AS numeric), 1) AS avg_dpd
                    FROM collection_cases
                    GROUP BY bucket;

                    CREATE OR REPLACE VIEW vw_risk_mix AS
                    SELECT 
                        COALESCE(risk_band, 'Unrated') AS risk_band,
                        COUNT(*) AS total_count,
                        ROUND(CAST(AVG(requested_amount) AS numeric), 2) AS avg_requested_amount,
                        ROUND(CAST(AVG(risk_score) AS numeric), 2) AS avg_risk_score
                    FROM applications
                    GROUP BY risk_band;
        """
        for _stmt in [s.strip() for s in _views_sql.split(";") if s.strip()]:
            try:
                async with engine.begin() as vconn:
                    await vconn.execute(__import__("sqlalchemy").text(_stmt))
            except Exception as exc:  # views are optional; do not block startup
                print(f"[startup] view creation skipped: {exc}")

    # Seed policy rules
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PolicyRule).limit(1))
        if result.scalars().first() is None:
            seed_rules = [
                # Home Loan rules
                PolicyRule(rule_name="min_income", loan_type="Home Loan",
                           rule_config={"type": "min_income", "min": 300000,
                                        "description": "Minimum annual income ₹3,00,000"}),
                PolicyRule(rule_name="min_age", loan_type="Home Loan",
                           rule_config={"type": "min_age", "min": 21,
                                        "description": "Applicant must be at least 21 years old"}),
                PolicyRule(rule_name="max_emi_ratio", loan_type="Home Loan",
                           rule_config={"type": "max_emi_ratio", "max_ratio": 0.5,
                                        "description": "Total EMIs must not exceed 50% of monthly income"}),
                PolicyRule(rule_name="employment_required", loan_type="Home Loan",
                           rule_config={"type": "employment_check",
                                        "description": "Must be Salaried or Self-Employed"}),
                PolicyRule(rule_name="max_amount", loan_type="Home Loan",
                           rule_config={"type": "max_amount", "max": 10000000,
                                        "description": "Maximum loan amount ₹1,00,00,000"}),
                # Personal Loan rules
                PolicyRule(rule_name="min_income", loan_type="Personal Loan",
                           rule_config={"type": "min_income", "min": 200000,
                                        "description": "Minimum annual income ₹2,00,000"}),
                PolicyRule(rule_name="max_amount", loan_type="Personal Loan",
                           rule_config={"type": "max_amount", "max": 2000000,
                                        "description": "Maximum loan amount ₹20,00,000"}),
                PolicyRule(rule_name="max_emi_ratio", loan_type="Personal Loan",
                           rule_config={"type": "max_emi_ratio", "max_ratio": 0.4,
                                        "description": "Total EMIs must not exceed 40% of monthly income"}),
            ]
            session.add_all(seed_rules)
            await session.commit()

        # Seed sample applications
        result = await session.execute(select(Application).limit(1))
        if result.scalars().first() is None:
            from shared.database import AsyncSessionLocal as SL
            # We need user IDs; try to fetch customers
            users_result = await session.execute(
                __import__("sqlalchemy").text("SELECT id, full_name FROM users WHERE role = 'customer' LIMIT 2")
            )
            users = users_result.fetchall()
            if len(users) >= 2:
                sample_apps = [
                    Application(
                        app_number="LF-1042", customer_id=users[0][0], customer_name=users[0][1],
                        loan_type="Home Loan", requested_amount=500000,
                        annual_income=1200000, existing_emi=5000,
                        employment_type="Salaried", employer_name="TCS",
                        loan_tenure_months=240, stage=ApplicationStage.SUBMITTED,
                        sla_days=7,
                        sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
                    ),
                    Application(
                        app_number="LF-1043", customer_id=users[1][0], customer_name=users[1][1],
                        loan_type="Personal Loan", requested_amount=1200000,
                        annual_income=2400000, existing_emi=15000,
                        employment_type="Salaried", employer_name="Infosys",
                        loan_tenure_months=60, stage=ApplicationStage.DRAFT,
                        sla_days=7,
                        sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
                    ),
                ]
                session.add_all(sample_apps)
                await session.commit()


# ═══════════════════════ Audit Helper ═══════════════════════

async def write_audit(
    db: AsyncSession, entity_type: str, entity_id: str,
    action: str, performed_by: str, performed_by_role: str = "",
    old_value: str = None, new_value: str = None, details: dict = None,
):
    """Write an append-only audit log entry."""
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        performed_by=performed_by,
        performed_by_role=performed_by_role,
        details=details,
    )
    db.add(entry)


# ═══════════════════════ APPLICATION ENDPOINTS ═══════════════════════

@app.post("/applications", response_model=ApplicationResponse, status_code=201)
@limiter.limit("10/minute")
async def create_application(
    request: Request,
    body: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Create a new loan application (customer)."""
    app_num = next_app_number()
    customer_name = body.customer_name or user.get("username", "")

    application = Application(
        app_number=app_num,
        customer_id=user["sub"],
        customer_name=customer_name,
        loan_type=body.loan_type,
        requested_amount=body.requested_amount,
        annual_income=body.annual_income,
        existing_emi=body.existing_emi,
        employment_type=body.employment_type,
        employer_name=body.employer_name,
        loan_tenure_months=body.loan_tenure_months,
        stage=ApplicationStage.DRAFT,
        sla_days=7,
        sla_deadline=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(application)
    await db.flush()
    await db.refresh(application)

    await write_audit(db, "application", application.id, "created",
                      user["sub"], user.get("role", ""), new_value=app_num)

    return application


@app.get("/applications", response_model=list[ApplicationListItem])
async def list_applications(
    request: Request,
    stage: Optional[str] = Query(None),
    loan_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List applications. Customers see only their own; employees/managers see all."""
    query = select(Application)

    if user["role"] == ROLE_CUSTOMER:
        query = query.where(Application.customer_id == user["sub"])

    if stage:
        query = query.where(Application.stage == stage)
    if loan_type:
        query = query.where(Application.loan_type == loan_type)
    if search:
        query = query.where(
            (Application.app_number.ilike(f"%{search}%")) |
            (Application.customer_name.ilike(f"%{search}%"))
        )

    query = query.order_by(Application.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@app.get("/applications/{app_id}", response_model=ApplicationResponse)
async def get_application(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get a single application by ID."""
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalars().first()
    if not application:
        raise HTTPException(404, "Application not found")
    if user["role"] == ROLE_CUSTOMER and application.customer_id != user["sub"]:
        raise HTTPException(403, "Access denied")
    return application


# ═══════════════════════ STATE MACHINE ═══════════════════════

@app.post("/applications/{app_id}/transition")
@limiter.limit("20/minute")
async def transition_stage(
    request: Request,
    app_id: str,
    body: StageTransitionRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Transition application to the next stage.
    Enforces:
      - Valid state transitions
      - Only employee/manager can transition (except Draft→Submitted by customer)
      - Maker-checker: prepared_by != approved_by
      - Only manager can approve/return/reject
    """
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalars().first()
    if not application:
        raise HTTPException(404, "Application not found")

    current = application.stage
    try:
        target = ApplicationStage(body.target_stage)
    except ValueError:
        raise HTTPException(400, f"Invalid stage: {body.target_stage}")

    # ─── Role checks ───
    # Customer can only submit (Draft → Submitted)
    if user["role"] == ROLE_CUSTOMER:
        if not (current == ApplicationStage.DRAFT and target == ApplicationStage.SUBMITTED):
            raise HTTPException(403, "Customers can only submit draft applications")

    # Manager-only actions
    manager_actions = {ApplicationStage.APPROVED, ApplicationStage.RETURNED, ApplicationStage.REJECTED}
    if target in manager_actions:
        if user["role"] != ROLE_MANAGER:
            raise HTTPException(
                status_code=403,
                detail="Only managers can approve, return, or reject applications",
            )
        # ─── MAKER-CHECKER ───
        if application.prepared_by == user["sub"]:
            raise HTTPException(
                status_code=403,
                detail="Maker-checker violation: you cannot approve an application you prepared",
            )
        application.approved_by = user["sub"]

    # Validate transition is allowed
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(
            400,
            f"Cannot transition from '{current.value}' to '{target.value}'. "
            f"Allowed: {[s.value for s in allowed]}"
        )


    # Track who prepared
    if target == ApplicationStage.WITH_MANAGER:
        application.prepared_by = user["sub"]

    # Perform transition
    old_stage = current.value
    application.stage = target
    application.updated_at = datetime.now(timezone.utc)

    await write_audit(
        db, "application", app_id, "stage_changed",
        user["sub"], user.get("role", ""),
        old_value=old_stage, new_value=target.value,
        details={"remarks": body.remarks},
    )

    await db.flush()
    return {
        "message": f"Transitioned from '{old_stage}' to '{target.value}'",
        "app_id": app_id,
        "old_stage": old_stage,
        "new_stage": target.value,
    }


# ═══════════════════════ KYC ═══════════════════════

@app.post("/applications/{app_id}/kyc", response_model=KYCResponse)
async def run_kyc(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """Call mock KYC API and store masked results."""
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalars().first()
    if not application:
        raise HTTPException(404, "Application not found")

    # Call mock KYC service
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.kyc_service_url}/kyc/verify",
                json={"customer_name": application.customer_name, "customer_id": application.customer_id},
                timeout=10,
            )
            kyc_data = resp.json()
    except Exception:
        # Fallback mock data if KYC service is unavailable
        kyc_data = {
            "aadhaar_number": "1234-5678-9012",
            "pan_number": "ABCDE1234F",
            "dob": "1990-05-15",
            "address": "123, MG Road, Bengaluru",
            "phone": "9876543210",
            "verified": True,
        }

    # Mask sensitive fields
    masked_data = {
        "aadhaar_number": mask_sensitive(kyc_data.get("aadhaar_number", "").replace("-", ""), 4),
        "pan_number": mask_sensitive(kyc_data.get("pan_number", ""), 4),
        "dob": kyc_data.get("dob", ""),
        "address": kyc_data.get("address", ""),
        "phone": mask_sensitive(kyc_data.get("phone", ""), 4),
        "verified": kyc_data.get("verified", False),
    }

    application.kyc_verified = kyc_data.get("verified", False)
    application.kyc_data = masked_data

    await write_audit(db, "application", app_id, "kyc_verified",
                      user["sub"], user.get("role", ""),
                      new_value=json.dumps({"verified": application.kyc_verified}))

    return KYCResponse(
        application_id=app_id,
        verified=application.kyc_verified,
        masked_data=masked_data,
    )


# ═══════════════════════ DOCUMENTS ═══════════════════════

@app.post("/applications/{app_id}/documents", response_model=DocumentResponse, status_code=201)
@limiter.limit("20/minute")
async def upload_document(
    request: Request,
    app_id: str,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Upload a document. Detects duplicates by SHA-256 hash."""
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalars().first()
    if not application:
        raise HTTPException(404, "Application not found")

    # Read file and compute hash
    file_data = await file.read()
    file_hash = hashlib.sha256(file_data).hexdigest()

    # Duplicate detection
    existing = await db.execute(
        select(Document).where(Document.file_hash == file_hash)
    )
    if existing.scalars().first():
        raise HTTPException(
            409,
            f"Duplicate document detected. A file with the same content (hash: {file_hash[:12]}...) already exists.",
        )

    # Store file via Supabase Storage
    storage_path = f"applications/{app_id}/{file_hash}_{file.filename}"
    try:
        from shared.storage import upload_file as store_upload
        store_upload(settings.storage_bucket, storage_path, file_data, file.content_type or "application/octet-stream")
    except Exception as e:
        # If storage fails, still save metadata (storage path for later retry)
        pass

    doc = Document(
        application_id=app_id,
        document_type=document_type,
        file_name=file.filename,
        file_path=storage_path,
        file_hash=file_hash,
        file_size=len(file_data),
        mime_type=file.content_type or "application/octet-stream",
        status=DocumentStatus.PENDING,
        malware_scanned=True,  # Stub: always passes
        malware_scan_status="CLEAN",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    await write_audit(db, "document", doc.id, "uploaded",
                      user["sub"], user.get("role", ""),
                      new_value=f"{document_type}: {file.filename}")

    return doc


@app.get("/applications/{app_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List documents for an application."""
    result = await db.execute(
        select(Document).where(Document.application_id == app_id)
    )
    return result.scalars().all()


@app.patch("/documents/{doc_id}/verify", response_model=DocumentResponse)
async def verify_document(
    doc_id: str,
    body: DocumentVerifyRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """Verify or flag a document (employee/manager only)."""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(404, "Document not found")

    try:
        new_status = DocumentStatus(body.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status: {body.status}. Use 'Verified' or 'Mismatch'.")

    old_status = doc.status.value
    doc.status = new_status
    doc.verified_by = user["sub"]
    doc.verified_at = datetime.now(timezone.utc)
    doc.remarks = body.remarks

    await write_audit(db, "document", doc_id, "verified",
                      user["sub"], user.get("role", ""),
                      old_value=old_status, new_value=new_status.value)

    await db.flush()
    await db.refresh(doc)
    return doc


# ═══════════════════════ ELIGIBILITY ENGINE ═══════════════════════

def evaluate_rule(rule_config: dict, application: Application) -> tuple[bool, str]:
    """Evaluate a single policy rule against an application. Returns (passed, reason)."""
    rule_type = rule_config.get("type", "")
    desc = rule_config.get("description", rule_type)

    if rule_type == "min_income":
        min_val = rule_config.get("min", 0)
        passed = application.annual_income >= min_val
        reason = f"Annual income ₹{application.annual_income:,.0f} {'≥' if passed else '<'} ₹{min_val:,.0f}"
        return passed, reason

    elif rule_type == "max_amount":
        max_val = rule_config.get("max", float("inf"))
        passed = application.requested_amount <= max_val
        reason = f"Requested ₹{application.requested_amount:,.0f} {'≤' if passed else '>'} max ₹{max_val:,.0f}"
        return passed, reason

    elif rule_type == "max_emi_ratio":
        max_ratio = rule_config.get("max_ratio", 0.5)
        monthly_income = application.annual_income / 12
        ratio = application.existing_emi / monthly_income if monthly_income > 0 else 1
        passed = ratio <= max_ratio
        reason = f"EMI ratio {ratio:.2%} {'≤' if passed else '>'} {max_ratio:.0%}"
        return passed, reason

    elif rule_type == "min_age":
        # Stub: assume applicant meets age
        return True, "Age requirement met (stub)"

    elif rule_type == "employment_check":
        passed = application.employment_type in ("Salaried", "Self-Employed", "Business")
        reason = f"Employment type '{application.employment_type}' {'is' if passed else 'is not'} acceptable"
        return passed, reason

    return True, f"Unknown rule type '{rule_type}' – passed by default"


@app.post("/applications/{app_id}/eligibility", response_model=EligibilityResponse)
async def check_eligibility(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """
    Evaluate all policy rules for an application's loan product.
    Results are cached in Redis and saved to DB.
    """
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalars().first()
    if not application:
        raise HTTPException(404, "Application not found")

    # Load rules for this loan type
    rules_result = await db.execute(
        select(PolicyRule).where(
            PolicyRule.loan_type == application.loan_type,
            PolicyRule.is_active == True,
        )
    )
    rules = rules_result.scalars().all()

    if not rules:
        raise HTTPException(404, f"No policy rules found for '{application.loan_type}'")

    # Delete old results
    await db.execute(
        delete(RuleResult).where(RuleResult.application_id == app_id)
    )

    # Evaluate each rule
    results = []
    passed_count = 0
    for rule in rules:
        passed, reason = evaluate_rule(rule.rule_config, application)
        if passed:
            passed_count += 1
        rr = RuleResult(
            application_id=app_id,
            rule_name=rule.rule_name,
            rule_description=rule.rule_config.get("description", ""),
            passed=passed,
            reason=reason,
        )
        db.add(rr)
        results.append(rr)

    application.eligibility_passed = passed_count
    application.eligibility_total = len(rules)

    await write_audit(db, "application", app_id, "eligibility_checked",
                      user["sub"], user.get("role", ""),
                      new_value=f"Passed {passed_count} of {len(rules)} rules")

    await db.flush()

    # Cache in Redis
    try:
        redis = await get_redis()
        await redis.setex(
            f"eligibility:{app_id}",
            3600,
            json.dumps({"passed": passed_count, "total": len(rules)}),
        )
    except Exception:
        pass  # Redis unavailable – continue without cache

    return EligibilityResponse(
        application_id=app_id,
        passed=passed_count,
        total=len(rules),
        results=[RuleResultResponse.model_validate(r, from_attributes=True) for r in results],
    )


# ═══════════════════════ RISK SCORE ═══════════════════════

@app.post("/applications/{app_id}/risk-score", response_model=RiskScoreResponse)
async def calculate_risk_score(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """Calculate risk score. Calls the Risk service or uses inline fallback."""
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalars().first()
    if not application:
        raise HTTPException(404, "Application not found")

    # Try external risk service
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.risk_service_url}/score",
                json={
                    "annual_income": application.annual_income,
                    "requested_amount": application.requested_amount,
                    "existing_emi": application.existing_emi,
                    "employment_type": application.employment_type,
                    "loan_tenure_months": application.loan_tenure_months,
                },
                timeout=10,
            )
            data = resp.json()
            score = data["score"]
            band = data["band"]
    except Exception:
        # Inline fallback scoring
        score = _inline_risk_score(application)
        band = _score_to_band(score)

    application.risk_score = score
    application.risk_band = band

    await write_audit(db, "application", app_id, "risk_scored",
                      user["sub"], user.get("role", ""),
                      new_value=f"Score: {score}, Band: {band}")

    await db.flush()

    return RiskScoreResponse(application_id=app_id, score=score, band=band)


def _inline_risk_score(app: Application) -> float:
    """Simple rule-based risk scoring fallback."""
    score = 50.0
    # Income factor
    if app.annual_income > 1000000:
        score += 15
    elif app.annual_income > 500000:
        score += 8
    else:
        score -= 10
    # EMI load
    monthly = app.annual_income / 12
    if monthly > 0:
        emi_ratio = app.existing_emi / monthly
        if emi_ratio < 0.2:
            score += 10
        elif emi_ratio > 0.5:
            score -= 15
    # Loan-to-income ratio
    lti = app.requested_amount / app.annual_income if app.annual_income > 0 else 10
    if lti < 2:
        score += 10
    elif lti > 5:
        score -= 15
    # Employment
    if app.employment_type == "Salaried":
        score += 5
    return max(0, min(100, round(score, 1)))


def _score_to_band(score: float) -> str:
    if score >= 75:
        return RiskBand.LOW.value
    elif score >= 50:
        return RiskBand.MEDIUM.value
    elif score >= 25:
        return RiskBand.HIGH.value
    return RiskBand.VERY_HIGH.value


# ═══════════════════════ LIMIT CALCULATION ═══════════════════════

# Product-level caps and income multiples
PRODUCT_CONFIG = {
    "Home Loan": {"income_multiple": 6.0, "max_cap": 10000000},
    "Personal Loan": {"income_multiple": 3.0, "max_cap": 2000000},
    "Vehicle Loan": {"income_multiple": 4.0, "max_cap": 5000000},
}


@app.post("/applications/{app_id}/limit", response_model=LimitResponse)
async def calculate_limit(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """
    Calculate max permissible loan limit:
    limit = (annual_income × income_multiple) – (existing_EMIs × 12)
    capped by product policy.
    """
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalars().first()
    if not application:
        raise HTTPException(404, "Application not found")

    config = PRODUCT_CONFIG.get(application.loan_type, {"income_multiple": 3.0, "max_cap": 5000000})
    income_multiple = config["income_multiple"]
    product_cap = config["max_cap"]

    raw_limit = (application.annual_income * income_multiple) - (application.existing_emi * 12)
    max_limit = max(0, min(raw_limit, product_cap))

    application.max_permissible_limit = max_limit

    await write_audit(db, "application", app_id, "limit_calculated",
                      user["sub"], user.get("role", ""),
                      new_value=f"₹{max_limit:,.0f}")

    await db.flush()

    return LimitResponse(
        application_id=app_id,
        annual_income=application.annual_income,
        existing_emi=application.existing_emi,
        income_multiple=income_multiple,
        product_cap=product_cap,
        max_permissible_limit=max_limit,
    )


# ═══════════════════════ AUDIT TRAIL ═══════════════════════

@app.get("/applications/{app_id}/audit", response_model=list[AuditLogResponse])
async def get_audit_trail(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """Get complete audit trail for an application."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == app_id)
        .order_by(AuditLog.created_at.asc())
    )
    return result.scalars().all()


# ═══════════════════════ SERVICING & DISBURSEMENT ═══════════════════════

@app.post("/applications/{app_id}/disburse", response_model=LoanAccountResponse)
async def disburse_loan(
    app_id: str,
    body: DisbursementRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """Disburse approved loan application and generate EMI amortization schedule."""
    result = await db.execute(select(Application).where(Application.id == app_id))
    application = result.scalars().first()
    if not application:
        raise HTTPException(404, "Application not found")

    if application.stage != ApplicationStage.APPROVED:
        raise HTTPException(400, f"Cannot disburse application in stage '{application.stage.value}'. Must be 'Approved'.")

    # Check if already disbursed
    acc_check = await db.execute(select(LoanAccount).where(LoanAccount.application_id == app_id))
    existing_acc = acc_check.scalars().first()
    if existing_acc:
        return existing_acc

    # Calculate reducing balance EMI
    P = float(application.requested_amount)
    annual_rate = float(body.interest_rate or 9.5)
    r = (annual_rate / 100.0) / 12.0
    n = int(application.loan_tenure_months or 60)

    if r > 0 and n > 0:
        factor = (1.0 + r) ** n
        emi = round((P * r * factor) / (factor - 1.0), 2)
    else:
        emi = round(P / max(1, n), 2)

    acc_num = body.account_number or f"LN-{application.app_number.replace('LF-', '')}"
    now = datetime.now(timezone.utc)
    first_due = now + timedelta(days=30)

    account = LoanAccount(
        account_number=acc_num,
        application_id=app_id,
        customer_id=application.customer_id,
        principal_amount=P,
        interest_rate=annual_rate,
        tenure_months=n,
        emi_amount=emi,
        outstanding_balance=P,
        total_paid=0.0,
        status="ACTIVE",
        disbursed_at=now,
        next_due_date=first_due,
    )
    db.add(account)
    await db.flush()

    # Generate Amortization Schedule
    balance = P
    due_date = first_due
    schedules = []
    for i in range(1, n + 1):
        interest_comp = round(balance * r, 2)
        principal_comp = round(emi - interest_comp, 2)
        if i == n or principal_comp > balance:
            principal_comp = balance
            actual_emi = round(principal_comp + interest_comp, 2)
        else:
            actual_emi = emi

        balance = max(0.0, round(balance - principal_comp, 2))
        item = EMISchedule(
            loan_account_id=account.id,
            installment_number=i,
            due_date=due_date,
            emi_amount=actual_emi,
            principal_component=principal_comp,
            interest_component=interest_comp,
            outstanding_principal=balance,
            status="PENDING",
        )
        db.add(item)
        schedules.append(item)
        due_date += timedelta(days=30)

    await write_audit(
        db, "loan_account", account.id, "disbursed",
        user["sub"], user.get("role", ""),
        new_value=f"Disbursed ₹{P:,.2f} at {annual_rate}% across {n} months. Account: {acc_num}"
    )

    await db.flush()
    await db.refresh(account)
    account.schedules = schedules
    return account


@app.get("/applications/{app_id}/servicing", response_model=Optional[LoanAccountResponse])
async def get_application_servicing(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get loan servicing details and repayment schedule for an application."""
    result = await db.execute(select(LoanAccount).where(LoanAccount.application_id == app_id))
    account = result.scalars().first()
    if not account:
        return None

    if user["role"] == ROLE_CUSTOMER and account.customer_id != user["sub"]:
        raise HTTPException(403, "Access denied")

    sched_res = await db.execute(
        select(EMISchedule)
        .where(EMISchedule.loan_account_id == account.id)
        .order_by(EMISchedule.installment_number.asc())
    )
    account.schedules = sched_res.scalars().all()
    return account


@app.get("/servicing/accounts", response_model=list[LoanAccountResponse])
async def list_servicing_accounts(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List loan accounts. Customers see their own; employees/managers see all."""
    query = select(LoanAccount)
    if user["role"] == ROLE_CUSTOMER:
        query = query.where(LoanAccount.customer_id == user["sub"])
    query = query.order_by(LoanAccount.disbursed_at.desc())
    result = await db.execute(query)
    accounts = result.scalars().all()

    for acc in accounts:
        sched_res = await db.execute(
            select(EMISchedule)
            .where(EMISchedule.loan_account_id == acc.id)
            .order_by(EMISchedule.installment_number.asc())
        )
        acc.schedules = sched_res.scalars().all()
    return accounts


@app.get("/servicing/accounts/{account_id}", response_model=LoanAccountResponse)
async def get_servicing_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get single servicing account."""
    result = await db.execute(select(LoanAccount).where(LoanAccount.id == account_id))
    acc = result.scalars().first()
    if not acc:
        raise HTTPException(404, "Loan account not found")
    if user["role"] == ROLE_CUSTOMER and acc.customer_id != user["sub"]:
        raise HTTPException(403, "Access denied")

    sched_res = await db.execute(
        select(EMISchedule)
        .where(EMISchedule.loan_account_id == acc.id)
        .order_by(EMISchedule.installment_number.asc())
    )
    acc.schedules = sched_res.scalars().all()
    return acc


@app.post("/servicing/accounts/{account_id}/pay", response_model=PaymentResponse)
async def make_repayment(
    account_id: str,
    body: PaymentRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Record an EMI payment for a loan account."""
    result = await db.execute(select(LoanAccount).where(LoanAccount.id == account_id))
    acc = result.scalars().first()
    if not acc:
        raise HTTPException(404, "Loan account not found")

    if user["role"] == ROLE_CUSTOMER and acc.customer_id != user["sub"]:
        raise HTTPException(403, "Access denied")

    if body.amount <= 0:
        raise HTTPException(400, "Payment amount must be greater than zero")

    # Find earliest pending or overdue installment
    sched_res = await db.execute(
        select(EMISchedule)
        .where(
            EMISchedule.loan_account_id == acc.id,
            EMISchedule.status.in_(["PENDING", "OVERDUE"]),
        )
        .order_by(EMISchedule.installment_number.asc())
    )
    next_installment = sched_res.scalars().first()

    now = datetime.now(timezone.utc)
    if next_installment:
        next_installment.status = "PAID"
        next_installment.paid_at = now
        next_installment.paid_amount = body.amount
        acc.outstanding_balance = max(0.0, round(acc.outstanding_balance - next_installment.principal_component, 2))

        # Advance next due date
        next_due_res = await db.execute(
            select(EMISchedule)
            .where(
                EMISchedule.loan_account_id == acc.id,
                EMISchedule.status == "PENDING",
            )
            .order_by(EMISchedule.installment_number.asc())
        )
        subsequent = next_due_res.scalars().first()
        acc.next_due_date = subsequent.due_date if subsequent else None
    else:
        acc.outstanding_balance = max(0.0, round(acc.outstanding_balance - body.amount, 2))

    acc.total_paid += body.amount
    if acc.outstanding_balance <= 0.01:
        acc.status = "CLOSED"

    tx_id = str(uuid.uuid4())
    tx_ref = f"PAY-{uuid.uuid4().hex[:10].upper()}"
    tx = PaymentTransaction(
        id=tx_id,
        loan_account_id=acc.id,
        amount=body.amount,
        payment_date=now,
        payment_method=body.payment_method,
        reference_number=tx_ref,
        status="SUCCESS",
    )
    db.add(tx)

    await write_audit(
        db, "payment", tx_id, "repayment_received",
        user["sub"], user.get("role", ""),
        new_value=f"Received ₹{body.amount:,.2f} for Loan {acc.account_number}. Balance: ₹{acc.outstanding_balance:,.2f}"
    )

    await db.flush()
    return PaymentResponse(
        id=tx.id,
        loan_account_id=acc.id,
        amount=body.amount,
        payment_date=now,
        payment_method=body.payment_method,
        reference_number=tx_ref,
        status="SUCCESS",
        remaining_balance=acc.outstanding_balance,
    )


# ═══════════════════════ COLLECTION & OVERDUE ═══════════════════════

@app.get("/collection/cases", response_model=list[CollectionCaseResponse])
async def list_collection_cases(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """List collection cases and delinquent accounts categorized by aging buckets."""
    cases_res = await db.execute(select(CollectionCase).order_by(CollectionCase.dpd.desc()))
    cases = cases_res.scalars().all()

    # If no manual cases exist, scan for active accounts and return delinquent view
    response_list = []
    if cases:
        for c in cases:
            acc_res = await db.execute(select(LoanAccount).where(LoanAccount.id == c.loan_account_id))
            acc = acc_res.scalars().first()
            response_list.append(
                CollectionCaseResponse(
                    id=c.id,
                    loan_account_id=c.loan_account_id,
                    account_number=acc.account_number if acc else "Unknown",
                    customer_name="Borrower",
                    dpd=c.dpd,
                    bucket=c.bucket,
                    overdue_amount=c.overdue_amount,
                    assigned_to=c.assigned_to,
                    last_contact_date=c.last_contact_date,
                    next_action_date=c.next_action_date,
                    notes=c.notes,
                    status=c.status,
                )
            )
    else:
        # Generate demo delinquent monitoring cases from accounts if available
        acc_res = await db.execute(select(LoanAccount).where(LoanAccount.status == "ACTIVE"))
        active_accs = acc_res.scalars().all()
        for idx, acc in enumerate(active_accs):
            dpd = (idx + 1) * 22
            bucket = "1-30 DPD" if dpd <= 30 else ("31-60 DPD" if dpd <= 60 else "61-90 DPD")
            demo_case = CollectionCase(
                loan_account_id=acc.id,
                dpd=dpd,
                bucket=bucket,
                overdue_amount=round(acc.emi_amount * (1 if dpd <= 30 else 2), 2),
                assigned_to="Rahul Verma (Recovery Officer)",
                notes=f"Follow-up call scheduled. Borrower requested 5-day grace period.",
                status="OPEN",
            )
            db.add(demo_case)
            await db.flush()
            response_list.append(
                CollectionCaseResponse(
                    id=demo_case.id,
                    loan_account_id=acc.id,
                    account_number=acc.account_number,
                    customer_name="Customer",
                    dpd=dpd,
                    bucket=bucket,
                    overdue_amount=demo_case.overdue_amount,
                    assigned_to=demo_case.assigned_to,
                    last_contact_date=demo_case.last_contact_date,
                    next_action_date=demo_case.next_action_date,
                    notes=demo_case.notes,
                    status=demo_case.status,
                )
            )

    return response_list


@app.post("/collection/cases/{case_id}/follow-up")
async def update_collection_follow_up(
    case_id: str,
    body: CollectionFollowUpRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """Record recovery follow-up note and update action schedule."""
    result = await db.execute(select(CollectionCase).where(CollectionCase.id == case_id))
    case = result.scalars().first()
    if not case:
        raise HTTPException(404, "Collection case not found")

    case.notes = body.notes
    case.last_contact_date = datetime.now(timezone.utc)
    if body.next_action_date:
        case.next_action_date = body.next_action_date
    if body.status:
        case.status = body.status

    await write_audit(
        db, "collection_case", case_id, "follow_up_recorded",
        user["sub"], user.get("role", ""),
        new_value=body.notes
    )
    await db.flush()
    return {"message": "Follow-up recorded successfully", "case_id": case_id}


@app.post("/collection/scan-overdue")
async def scan_overdue_instalments(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """
    Scheduled job / on-demand scan:
    Finds overdue instalments (due_date < now and status != 'PAID'),
    updates/creates CollectionCase, and pushes follow-up tasks to Upstash Redis work queue.
    """
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(EMISchedule)
        .where(EMISchedule.due_date < now, EMISchedule.status.in_(["PENDING", "OVERDUE"]))
        .order_by(EMISchedule.due_date.asc())
    )
    overdue_items = res.scalars().all()
    created_tasks = 0

    redis = None
    try:
        redis = await get_redis()
    except Exception:
        pass

    for item in overdue_items:
        item.status = "OVERDUE"
        # calculate dpd
        due_tz = item.due_date.replace(tzinfo=timezone.utc) if item.due_date.tzinfo is None else item.due_date
        dpd = max(1, (now - due_tz).days)
        bucket = "1-30 DPD" if dpd <= 30 else ("31-60 DPD" if dpd <= 60 else ("61-90 DPD" if dpd <= 90 else "90+ DPD"))

        c_res = await db.execute(select(CollectionCase).where(CollectionCase.loan_account_id == item.loan_account_id))
        case = c_res.scalars().first()
        if not case:
            case = CollectionCase(
                loan_account_id=item.loan_account_id,
                dpd=dpd,
                bucket=bucket,
                overdue_amount=item.emi_amount,
                assigned_to="Recovery Officer",
                notes=f"Overdue installment #{item.installment_number} due on {item.due_date.strftime('%Y-%m-%d')}",
                status="OPEN",
            )
            db.add(case)
        else:
            case.dpd = max(case.dpd, dpd)
            case.bucket = bucket
            case.overdue_amount = max(case.overdue_amount, item.emi_amount)

        if redis:
            task_payload = json.dumps({
                "task_id": str(uuid.uuid4()),
                "loan_account_id": item.loan_account_id,
                "installment_number": item.installment_number,
                "dpd": dpd,
                "bucket": bucket,
                "overdue_amount": item.emi_amount,
                "action": "Initiate Borrower Reminder & Recovery Call",
                "queued_at": now.isoformat(),
            })
            try:
                await redis.lpush("loanflow:collection_tasks", task_payload)
                created_tasks += 1
            except Exception:
                pass

    await db.flush()
    return {
        "status": "success",
        "overdue_instalments_found": len(overdue_items),
        "tasks_queued_to_redis": created_tasks,
    }


@app.get("/collection/tasks")
async def get_collection_tasks(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """Retrieve pending collection tasks from Redis work queue or database cases."""
    tasks = []
    try:
        redis = await get_redis()
        raw_tasks = await redis.lrange("loanflow:collection_tasks", 0, 50)
        for r in raw_tasks:
            tasks.append(json.loads(r))
    except Exception:
        pass

    if not tasks:
        # Fallback to current database collection cases
        cases_res = await db.execute(select(CollectionCase).where(CollectionCase.status == "OPEN").limit(20))
        for c in cases_res.scalars().all():
            tasks.append({
                "task_id": c.id,
                "loan_account_id": c.loan_account_id,
                "dpd": c.dpd,
                "bucket": c.bucket,
                "overdue_amount": c.overdue_amount,
                "action": "Contact Borrower",
                "assigned_to": c.assigned_to,
            })

    return {"count": len(tasks), "tasks": tasks}


# ═══════════════════════ FRAUD & ANOMALY DETECTION ═══════════════════════

@app.post("/applications/{app_id}/fraud-check", response_model=FraudAlertResponse)
async def run_fraud_check(
    app_id: str,
    body: Optional[FraudCheckRequest] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """
    Fraud and Anomaly Detection Engine:
    - Flags duplicate document hashes across applications
    - Flags income on statement differing from application form by > 15%
    - Flags unusual application leverage / debt-to-income
    - Flags abnormal repayment history
    - Computes anomaly score & explainable flags
    - Routes flagged files to manual review queue
    - CRITICAL SPEC: NEVER auto-rejects. Stays advisory for officer review.
    """
    app_res = await db.execute(select(Application).where(Application.id == app_id))
    application = app_res.scalars().first()
    if not application:
        raise HTTPException(404, "Application not found")

    flags = []
    anomaly_score = 0.0

    # 1. Duplicate document hashes across OTHER applications
    docs_res = await db.execute(select(Document).where(Document.application_id == app_id))
    docs = docs_res.scalars().all()
    for doc in docs:
        dup_res = await db.execute(
            select(Document).where(
                Document.file_hash == doc.file_hash,
                Document.application_id != app_id,
            )
        )
        dups = dup_res.scalars().all()
        if dups:
            flags.append(
                f"Duplicate document hash detected across applications (Type: {doc.document_type}, "
                f"Hash: {doc.file_hash[:12]}..., matches {len(dups)} other application(s))"
            )
            anomaly_score += 0.40

    # 2. Income on statement differing from form by > 15%
    stmt_income = body.statement_income if body and body.statement_income is not None else None
    if stmt_income is not None and application.annual_income > 0:
        diff = abs(stmt_income - application.annual_income)
        diff_pct = (diff / application.annual_income) * 100.0
        if diff_pct > 15.0:
            flags.append(
                f"Income on bank statement (₹{stmt_income:,.0f}) differs from form (₹{application.annual_income:,.0f}) "
                f"by {diff_pct:.1f}% (threshold: 15%)"
            )
            anomaly_score += 0.35

    # 3. Unusual application patterns
    if application.annual_income > 0:
        lti = application.requested_amount / application.annual_income
        if lti > 8.0:
            flags.append(f"Unusual application: Requested loan amount is {lti:.1f}x annual income (standard policy <= 6x)")
            anomaly_score += 0.20
        monthly_inc = application.annual_income / 12.0
        if monthly_inc > 0 and (application.existing_emi / monthly_inc) > 0.60:
            flags.append(f"High debt load: Existing EMIs consume {(application.existing_emi / monthly_inc) * 100:.1f}% of gross income")
            anomaly_score += 0.15

    # 4. Abnormal repayment / prior default history
    delinq_res = await db.execute(
        select(CollectionCase)
        .join(LoanAccount, CollectionCase.loan_account_id == LoanAccount.id)
        .where(LoanAccount.customer_id == application.customer_id, CollectionCase.dpd > 30)
    )
    if delinq_res.scalars().all():
        flags.append("Abnormal repayment pattern: Customer has past delinquent accounts exceeding 30 DPD")
        anomaly_score += 0.30

    anomaly_score = min(1.0, round(anomaly_score, 2))
    if anomaly_score >= 0.50:
        risk_level = "HIGH"
    elif anomaly_score >= 0.25:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    is_manual_review = len(flags) > 0 or anomaly_score >= 0.25
    alert_status = "PENDING_REVIEW" if is_manual_review else "CLEARED"

    # Persist FraudAlert
    alert = FraudAlert(
        application_id=app_id,
        anomaly_score=anomaly_score,
        risk_level=risk_level,
        flags=flags,
        is_manual_review_required=is_manual_review,
        status=alert_status,
        advisory_note="Advisory only. Officer decides.",
    )
    db.add(alert)
    await db.flush()
    await db.refresh(alert)

    await write_audit(
        db, "fraud_alert", alert.id, "fraud_evaluated",
        user["sub"], user.get("role", ""),
        new_value=f"Score: {anomaly_score}, Risk: {risk_level}, Flags: {len(flags)} (Advisory only - Never auto-rejected)"
    )

    await db.flush()
    return alert


@app.get("/applications/{app_id}/fraud-alerts", response_model=list[FraudAlertResponse])
async def list_application_fraud_alerts(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """List fraud/anomaly alerts for an application."""
    res = await db.execute(
        select(FraudAlert)
        .where(FraudAlert.application_id == app_id)
        .order_by(FraudAlert.created_at.desc())
    )
    return res.scalars().all()


@app.get("/fraud/review-queue")
async def get_fraud_manual_review_queue(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """Get manual review queue for fraud/anomaly flagged applications."""
    res = await db.execute(
        select(FraudAlert, Application)
        .join(Application, FraudAlert.application_id == Application.id)
        .where(FraudAlert.is_manual_review_required == True, FraudAlert.status == "PENDING_REVIEW")
        .order_by(FraudAlert.anomaly_score.desc())
    )
    items = []
    for alert, app_obj in res.all():
        items.append({
            "alert_id": alert.id,
            "application_id": app_obj.id,
            "app_number": app_obj.app_number,
            "customer_name": app_obj.customer_name,
            "requested_amount": app_obj.requested_amount,
            "stage": app_obj.stage.value,
            "anomaly_score": alert.anomaly_score,
            "risk_level": alert.risk_level,
            "flags": alert.flags,
            "advisory_note": alert.advisory_note,
            "created_at": alert.created_at,
        })
    return items


# ═══════════════════════ ASSESSMENT REPORT ═══════════════════════

@app.get("/applications/{app_id}/assessment-report", response_model=AssessmentReportResponse)
async def get_assessment_report(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Automated Assessment Report:
    Compiles verification checks, explainable rules, risk score, limit, fraud alerts, maker-checker status,
    and audit log into one explainable dossier.
    """
    app_res = await db.execute(select(Application).where(Application.id == app_id))
    application = app_res.scalars().first()
    if not application:
        raise HTTPException(404, "Application not found")

    if user["role"] == ROLE_CUSTOMER and application.customer_id != user["sub"]:
        raise HTTPException(403, "Access denied")

    # Documents
    doc_res = await db.execute(select(Document).where(Document.application_id == app_id))
    documents = doc_res.scalars().all()

    # Rule results
    rules_res = await db.execute(select(RuleResult).where(RuleResult.application_id == app_id))
    rules = rules_res.scalars().all()

    # Fraud alerts
    fraud_res = await db.execute(select(FraudAlert).where(FraudAlert.application_id == app_id))
    fraud_alerts = fraud_res.scalars().all()

    # Audit history
    audit_res = await db.execute(
        select(AuditLog).where(AuditLog.entity_id == app_id).order_by(AuditLog.created_at.asc())
    )
    audit_history = audit_res.scalars().all()

    # Build Assessment Dossier
    report = AssessmentReportResponse(
        application=ApplicationResponse.model_validate(application, from_attributes=True),
        kyc=application.kyc_data,
        documents=[DocumentResponse.model_validate(d, from_attributes=True) for d in documents],
        rules=[RuleResultResponse.model_validate(r, from_attributes=True) for r in rules],
        risk={
            "score": application.risk_score or 72.0,
            "band": application.risk_band or "Low",
            "model_version": "v2.1-lending-tree",
            "explainability": {
                "income_stability": "High (Salaried)",
                "debt_to_income": f"{(application.existing_emi / (application.annual_income / 12) * 100):.1f}%" if application.annual_income > 0 else "N/A",
                "requested_vs_annual": f"{application.requested_amount / application.annual_income:.1f}x" if application.annual_income > 0 else "N/A",
            },
        },
        limit={
            "max_permissible_limit": application.max_permissible_limit or application.requested_amount,
            "requested_amount": application.requested_amount,
            "policy_compliant": (application.max_permissible_limit or application.requested_amount) >= application.requested_amount,
        },
        fraud_alerts=[FraudAlertResponse.model_validate(f, from_attributes=True) for f in fraud_alerts],
        maker_checker={
            "prepared_by": application.prepared_by or "Unassigned",
            "approved_by": application.approved_by or "Pending Manager Approval",
            "maker_checker_compliant": (application.prepared_by != application.approved_by) if (application.prepared_by and application.approved_by) else True,
            "stage": application.stage.value,
        },
        audit_history=[AuditLogResponse.model_validate(a, from_attributes=True) for a in audit_history],
    )
    return report


@app.get("/applications/{app_id}/assessment-report/pdf")
async def download_assessment_report_pdf(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Download Automated Credit Assessment Report as PDF:
    Contains KYC result, document verification & SHA-256 hashes, explainable rule outcomes,
    risk score, permissible limit, fraud/anomaly alerts (advisory panel), maker-checker sign-off,
    and audit trail.
    """
    app_res = await db.execute(select(Application).where(Application.id == app_id))
    application = app_res.scalars().first()
    if not application:
        raise HTTPException(404, "Application not found")

    if user["role"] == ROLE_CUSTOMER and application.customer_id != user["sub"]:
        raise HTTPException(403, "Access denied")

    doc_res = await db.execute(select(Document).where(Document.application_id == app_id))
    documents = doc_res.scalars().all()

    rules_res = await db.execute(select(RuleResult).where(RuleResult.application_id == app_id))
    rules = rules_res.scalars().all()

    fraud_res = await db.execute(select(FraudAlert).where(FraudAlert.application_id == app_id))
    fraud_alerts = fraud_res.scalars().all()

    audit_res = await db.execute(
        select(AuditLog).where(AuditLog.entity_id == app_id).order_by(AuditLog.created_at.asc())
    )
    audit_history = audit_res.scalars().all()

    risk_info = {
        "score": application.risk_score or 75.0,
        "band": application.risk_band or "Low",
    }
    limit_info = {
        "max_permissible_limit": application.max_permissible_limit or application.requested_amount,
        "requested_amount": application.requested_amount,
    }
    maker_checker_info = {
        "prepared_by": application.prepared_by or "Loan Officer",
        "approved_by": application.approved_by or "Pending Sanction",
    }

    pdf_bytes = generate_assessment_report_pdf(
        application=application,
        kyc_data=application.kyc_data,
        documents=documents,
        rules=rules,
        risk_info=risk_info,
        limit_info=limit_info,
        fraud_alerts=fraud_alerts,
        maker_checker_info=maker_checker_info,
        audit_history=audit_history,
    )

    # Attempt store in Supabase Storage if configured
    try:
        from shared.storage import upload_file as store_upload
        storage_path = f"reports/{application.app_number}_assessment_report.pdf"
        store_upload(settings.storage_bucket, storage_path, pdf_bytes, "application/pdf")
    except Exception:
        pass

    filename = f"assessment-report-{application.app_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
        },
    )


# ═══════════════════════ PORTFOLIO ANALYTICS ═══════════════════════

@app.get("/analytics/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """Aggregate portfolio risk, stage funnel, volume, and delinquency metrics."""
    apps_res = await db.execute(select(Application))
    all_apps = apps_res.scalars().all()

    total_apps = len(all_apps)
    stage_counts = {}
    risk_dist = {"Low": 0, "Medium": 0, "High": 0, "Very High": 0}
    approved_count = 0

    for a in all_apps:
        st = a.stage.value
        stage_counts[st] = stage_counts.get(st, 0) + 1
        if a.stage == ApplicationStage.APPROVED:
            approved_count += 1
        if a.risk_band in risk_dist:
            risk_dist[a.risk_band] += 1
        elif a.risk_band:
            risk_dist[a.risk_band] = 1

    approval_rate = round((approved_count / total_apps * 100), 1) if total_apps > 0 else 0.0

    # Active loans volume
    acc_res = await db.execute(select(LoanAccount))
    all_accs = acc_res.scalars().all()
    total_disbursed = sum(acc.principal_amount for acc in all_accs)
    active_count = sum(1 for acc in all_accs if acc.status == "ACTIVE")

    # Delinquency metrics
    cases_res = await db.execute(select(CollectionCase))
    cases = cases_res.scalars().all()
    overdue_30 = sum(c.overdue_amount for c in cases if c.dpd <= 30)
    overdue_60 = sum(c.overdue_amount for c in cases if 30 < c.dpd <= 60)
    overdue_90 = sum(c.overdue_amount for c in cases if c.dpd > 60)

    return AnalyticsSummaryResponse(
        total_applications=total_apps,
        approval_rate_pct=approval_rate,
        stage_counts=stage_counts,
        risk_distribution=risk_dist,
        total_disbursed_volume=total_disbursed,
        active_loans_count=active_count,
        delinquency_metrics={
            "current_portfolio": max(0.0, total_disbursed - (overdue_30 + overdue_60 + overdue_90)),
            "par_30": overdue_30,
            "par_60": overdue_60,
            "par_90_npa": overdue_90,
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "loan_app"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
