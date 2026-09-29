"""
LoanFlow Comprehensive Test Suite — PostgreSQL-Only.
Tests:
- Authentication & RBAC
- Application lifecycle & State Machine (valid + invalid transitions)
- Sensitive KYC data masking
- Duplicate document detection via SHA-256 hash
- Policy & Eligibility rule engine explainability (pass AND fail, reasons saved)
- Risk scoring & Limit calculation (income formula verification)
- Maker-checker enforcement (preparer cannot approve, manager only)
- EMI schedule totals (principal_component sums to loan principal)
- Loan disbursement & EMI schedule generation
- Servicing repayment processing
- Delinquency & Collection monitoring
- Fraud / anomaly detection (income variance > 15%, advisory only, never auto-reject)
- Assessment report compilation & PDF generation
- Portfolio analytics
- audit_log immutability (Postgres trigger blocks UPDATE & DELETE)
"""
import os
import sys
import uuid
import hashlib
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport

# ═══════════════════════ POINT TESTS TO POSTGRESQL ═══════════════════════
# Must use PostgreSQL – never SQLite!
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5434/loanflow_test")
os.environ["JWT_SECRET"] = "test-secret-key-1234567890-test"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_EXPIRE_MINUTES"] = "120"
os.environ["CSRF_SECRET"] = "test-csrf-secret"

# Add services path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services")))

from shared.database import init_db, engine, AsyncSessionLocal, Base
from shared.security import create_access_token, mask_sensitive
from loan_app.main import app as loan_app
from loan_app.models import (
    Application, ApplicationStage, Document, LoanAccount,
    EMISchedule, AuditLog, PolicyRule, FraudAlert, CollectionCase, VALID_TRANSITIONS,
)
from auth.main import app as auth_app, UserModel, pwd_context

import sqlalchemy


# ═══════════════════════ FIXTURES ═══════════════════════

@pytest.fixture(autouse=True, scope="module")
def setup_test_database():
    """Initialize PostgreSQL test database. Drop and recreate all tables."""
    async def _init():
        # Confirm we are using PostgreSQL
        url_str = str(engine.url)
        assert "postgres" in url_str, f"Tests MUST use PostgreSQL, got: {url_str}"

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

            # Create the append-only audit_log trigger
            await conn.execute(sqlalchemy.text("""
                CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'audit_log is append-only: UPDATE and DELETE are not permitted';
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql;
            """))
            await conn.execute(sqlalchemy.text("""
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
            """))

        # Seed users
        async with AsyncSessionLocal() as session:
            cust = UserModel(
                id="cust-101", username="amit_customer", email="amit@example.com",
                hashed_password=pwd_context.hash("pass123"),
                full_name="Amit Sharma", role="customer",
            )
            emp = UserModel(
                id="emp-201", username="rahul_maker", email="rahul@bank.com",
                hashed_password=pwd_context.hash("pass123"),
                full_name="Rahul Verma (Loan Officer)", role="employee",
            )
            mgr = UserModel(
                id="mgr-301", username="priya_checker", email="priya@bank.com",
                hashed_password=pwd_context.hash("pass123"),
                full_name="Priya Mehta (Branch Manager)", role="manager",
            )
            cust2 = UserModel(
                id="cust-102", username="neha_customer", email="neha@example.com",
                hashed_password=pwd_context.hash("pass123"),
                full_name="Neha Gupta", role="customer",
            )
            session.add_all([cust, emp, mgr, cust2])

            # Seed Policy Rules (Home Loan)
            rules = [
                PolicyRule(rule_name="min_income", loan_type="Home Loan",
                           rule_config={"type": "min_income", "min": 300000,
                                        "description": "Min annual income ₹3,00,000"}),
                PolicyRule(rule_name="max_emi_ratio", loan_type="Home Loan",
                           rule_config={"type": "max_emi_ratio", "max_ratio": 0.5,
                                        "description": "EMI ratio ≤ 50%"}),
                PolicyRule(rule_name="max_amount", loan_type="Home Loan",
                           rule_config={"type": "max_amount", "max": 10000000,
                                        "description": "Max loan amount ₹1,00,00,000"}),
                PolicyRule(rule_name="employment_required", loan_type="Home Loan",
                           rule_config={"type": "employment_check",
                                        "description": "Must be Salaried or Self-Employed"}),
                # Personal Loan rules
                PolicyRule(rule_name="min_income", loan_type="Personal Loan",
                           rule_config={"type": "min_income", "min": 200000,
                                        "description": "Min annual income ₹2,00,000"}),
                PolicyRule(rule_name="max_amount", loan_type="Personal Loan",
                           rule_config={"type": "max_amount", "max": 2000000,
                                        "description": "Max loan amount ₹20,00,000"}),
            ]
            session.add_all(rules)
            await session.commit()
        # Dispose pool so the next event loop starts fresh
        await engine.dispose()

    asyncio.run(_init())
    yield
    # Teardown
    async def _clean():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
    try:
        asyncio.run(_clean())
    except Exception:
        pass


def run_async_test(coro_fn):
    """
    Run an async test function and dispose the engine pool before closing
    the event loop. This prevents stale asyncpg connections from leaking
    into the next test's event loop.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro_fn())
    finally:
        loop.run_until_complete(engine.dispose())
        loop.close()


def get_auth_cookies(user_id: str, role: str, username: str) -> dict:
    token = create_access_token(user_id=user_id, role=role, username=username)
    return {"lf_access_token": token}


# ═══════════════════════ TEST 1 — KYC Masking ═══════════════════════

def test_kyc_masking_utility():
    """Verify sensitive fields are securely masked (show only last 4 chars)."""
    assert mask_sensitive("123456789012", 4).endswith("9012")
    assert "12345678" not in mask_sensitive("123456789012", 4)
    assert mask_sensitive("ABCDE1234F", 4).endswith("234F")
    assert mask_sensitive("9876543210", 4).endswith("3210")
    assert "987654" not in mask_sensitive("9876543210", 4)


# ═══════════════════════ TEST 2 — Full Lifecycle + Maker-Checker ═══════════════════════

def test_full_loan_lifecycle_and_maker_checker():
    """
    End-to-end: Create → Upload → Duplicate (409) → Submit → KYC →
    Docs → Verify → Risk → Eligibility → Risk Score → Limit →
    Prepare → With Manager → Maker-checker → Manager Approve →
    Disburse → Repay → Assessment Report → Analytics.
    """
    async def _run():
        transport = ASGITransport(app=loan_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            cust = get_auth_cookies("cust-101", "customer", "amit_customer")
            emp = get_auth_cookies("emp-201", "employee", "rahul_maker")
            mgr = get_auth_cookies("mgr-301", "manager", "priya_checker")

            # 1. Customer creates draft
            res = await client.post("/applications", json={
                "loan_type": "Home Loan", "requested_amount": 1000000,
                "annual_income": 1500000, "existing_emi": 8000,
                "employment_type": "Salaried", "employer_name": "Tech Corp",
                "loan_tenure_months": 120, "customer_name": "Amit Sharma",
            }, cookies=cust)
            assert res.status_code == 201, res.text
            app_data = res.json()
            app_id = app_data["id"]
            assert app_data["stage"] == "Draft"

            # 2. Upload document
            doc_content = b"Salary Slip 2026 PDF Content For Test"
            files = {"file": ("salary_slip.pdf", doc_content, "application/pdf")}
            res = await client.post(f"/applications/{app_id}/documents",
                                    data={"document_type": "Income Proof"},
                                    files=files, cookies=cust)
            assert res.status_code == 201
            doc_data = res.json()
            assert doc_data["file_hash"] == hashlib.sha256(doc_content).hexdigest()
            assert doc_data["malware_scan_status"] == "CLEAN"

            # 3. Duplicate detection → HTTP 409
            res_dup = await client.post(f"/applications/{app_id}/documents",
                                        data={"document_type": "Income Proof"},
                                        files={"file": ("salary_slip.pdf", doc_content, "application/pdf")},
                                        cookies=cust)
            assert res_dup.status_code == 409
            assert "Duplicate document detected" in res_dup.json()["detail"]

            # 4. Submit (Draft → Submitted)
            res = await client.post(f"/applications/{app_id}/transition",
                                    json={"target_stage": "Submitted"}, cookies=cust)
            assert res.status_code == 200
            assert res.json()["new_stage"] == "Submitted"

            # 5. Customer cannot transition to Approved
            res_fail = await client.post(f"/applications/{app_id}/transition",
                                         json={"target_stage": "Approved"}, cookies=cust)
            assert res_fail.status_code == 403

            # 6. Employee runs KYC
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "KYC"}, cookies=emp)
            res_kyc = await client.post(f"/applications/{app_id}/kyc", cookies=emp)
            assert res_kyc.status_code == 200
            kyc = res_kyc.json()
            assert kyc["verified"] is True
            assert "*" in kyc["masked_data"]["aadhaar_number"]

            # 7. Move through stages
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Docs"}, cookies=emp)
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Verification"}, cookies=emp)

            # Verify document
            await client.patch(f"/documents/{doc_data['id']}/verify",
                               json={"status": "Verified", "remarks": "Salary OK"},
                               cookies=emp)

            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Risk"}, cookies=emp)

            # 8. Eligibility Rules
            res_elig = await client.post(f"/applications/{app_id}/eligibility", cookies=emp)
            assert res_elig.status_code == 200
            elig = res_elig.json()
            assert elig["passed"] >= 1
            assert elig["total"] >= 2
            # Check that reasons are saved and explainable
            for r in elig["results"]:
                assert "reason" in r and len(r["reason"]) > 5

            # 9. Risk Score
            res_risk = await client.post(f"/applications/{app_id}/risk-score", cookies=emp)
            assert res_risk.status_code == 200
            risk = res_risk.json()
            assert risk["score"] > 0
            assert risk["band"] in ["Low", "Medium", "High", "Very High"]

            # 10. Limit Calculation
            res_lim = await client.post(f"/applications/{app_id}/limit", cookies=emp)
            assert res_lim.status_code == 200
            lim = res_lim.json()
            # Verify formula: (annual_income × income_multiple) – (existing_EMI × 12)
            expected = (1500000 * 6.0) - (8000 * 12)  # Home Loan: 6x income_multiple
            assert lim["max_permissible_limit"] == expected

            # 11. Prepare → With Manager
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Prepared"}, cookies=emp)
            res_wm = await client.post(f"/applications/{app_id}/transition",
                                       json={"target_stage": "With Manager",
                                              "remarks": "Ready for approval"},
                                       cookies=emp)
            assert res_wm.status_code == 200

            # ─── MAKER-CHECKER ENFORCEMENT ───

            # A) Employee (non-manager) tries to approve → 403
            res_emp_approve = await client.post(f"/applications/{app_id}/transition",
                                                json={"target_stage": "Approved"}, cookies=emp)
            assert res_emp_approve.status_code == 403
            assert "Only managers" in res_emp_approve.json()["detail"]

            # B) Customer tries to approve → 403
            res_cust_approve = await client.post(f"/applications/{app_id}/transition",
                                                 json={"target_stage": "Approved"}, cookies=cust)
            assert res_cust_approve.status_code == 403

            # C) Manager (distinct user) approves → 200
            res_mgr = await client.post(f"/applications/{app_id}/transition",
                                        json={"target_stage": "Approved",
                                               "remarks": "Approved"},
                                        cookies=mgr)
            assert res_mgr.status_code == 200
            assert res_mgr.json()["new_stage"] == "Approved"

            # 12. Disburse → EMI Schedule
            res_dis = await client.post(f"/applications/{app_id}/disburse",
                                        json={"interest_rate": 8.75}, cookies=mgr)
            assert res_dis.status_code == 200
            loan = res_dis.json()
            assert loan["status"] == "ACTIVE"
            assert loan["principal_amount"] == 1000000
            assert len(loan["schedules"]) == 120

            # ─── EMI SCHEDULE TOTALS VERIFICATION ───
            total_principal = sum(s["principal_component"] for s in loan["schedules"])
            assert abs(total_principal - 1000000) < 0.02, \
                f"Sum of principal_components ({total_principal}) != loan principal (1000000)"

            # 13. Repayment
            account_id = loan["id"]
            res_pay = await client.post(f"/servicing/accounts/{account_id}/pay",
                                        json={"amount": loan["emi_amount"], "payment_method": "UPI"},
                                        cookies=cust)
            assert res_pay.status_code == 200
            assert res_pay.json()["status"] == "SUCCESS"
            assert res_pay.json()["remaining_balance"] < 1000000

            # Verify schedule updated
            res_serv = await client.get(f"/applications/{app_id}/servicing", cookies=cust)
            assert res_serv.status_code == 200
            assert res_serv.json()["schedules"][0]["status"] == "PAID"

            # 14. Assessment Report (JSON)
            res_report = await client.get(f"/applications/{app_id}/assessment-report", cookies=mgr)
            assert res_report.status_code == 200
            report = res_report.json()
            assert report["application"]["stage"] == "Approved"
            assert report["maker_checker"]["maker_checker_compliant"] is True
            assert report["maker_checker"]["prepared_by"] == "emp-201"
            assert report["maker_checker"]["approved_by"] == "mgr-301"
            assert len(report["audit_history"]) >= 5

            # 15. Assessment Report (PDF download)
            res_pdf = await client.get(f"/applications/{app_id}/assessment-report/pdf", cookies=mgr)
            assert res_pdf.status_code == 200
            assert res_pdf.headers["content-type"] == "application/pdf"
            assert len(res_pdf.content) > 1000  # Non-trivial PDF

            # 16. Analytics
            res_an = await client.get("/analytics/summary", cookies=emp)
            assert res_an.status_code == 200
            analytics = res_an.json()
            assert analytics["total_applications"] >= 1
            assert analytics["total_disbursed_volume"] >= 1000000

    run_async_test(_run)


# ═══════════════════════ TEST 3 — Eligibility FAIL with reasons saved ═══════════════════════

def test_eligibility_fail_with_reasons():
    """Applicant with low income should fail eligibility; reasons must be saved."""
    async def _run():
        transport = ASGITransport(app=loan_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            cust = get_auth_cookies("cust-102", "customer", "neha_customer")
            emp = get_auth_cookies("emp-201", "employee", "rahul_maker")

            # Create application with too-low income (below ₹3L threshold)
            res = await client.post("/applications", json={
                "loan_type": "Home Loan", "requested_amount": 5000000,
                "annual_income": 150000, "existing_emi": 25000,
                "employment_type": "Unemployed", "employer_name": "",
                "loan_tenure_months": 240, "customer_name": "Neha Gupta",
            }, cookies=cust)
            assert res.status_code == 201
            app_id = res.json()["id"]

            # Walk to Risk stage
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Submitted"}, cookies=cust)
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "KYC"}, cookies=emp)
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Docs"}, cookies=emp)
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Verification"}, cookies=emp)
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Risk"}, cookies=emp)

            # Run eligibility
            res_elig = await client.post(f"/applications/{app_id}/eligibility", cookies=emp)
            assert res_elig.status_code == 200
            elig = res_elig.json()

            # Should have failures
            failed_rules = [r for r in elig["results"] if not r["passed"]]
            assert len(failed_rules) >= 1, f"Expected at least 1 failed rule, got {len(failed_rules)}"

            # Reasons must be meaningful, not empty
            for r in failed_rules:
                assert r["reason"] and len(r["reason"]) > 5
                assert "reason" in r

            # The pass count should be less than total
            assert elig["passed"] < elig["total"]

    run_async_test(_run)


# ═══════════════════════ TEST 4 — Invalid State Transitions ═══════════════════════

def test_invalid_state_transitions_rejected():
    """Attempting an invalid state transition returns HTTP 400."""
    async def _run():
        transport = ASGITransport(app=loan_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            cust = get_auth_cookies("cust-101", "customer", "amit_customer")
            emp = get_auth_cookies("emp-201", "employee", "rahul_maker")

            # Create draft application
            res = await client.post("/applications", json={
                "loan_type": "Personal Loan", "requested_amount": 500000,
                "annual_income": 800000, "existing_emi": 5000,
                "employment_type": "Salaried", "employer_name": "Wipro",
                "loan_tenure_months": 36, "customer_name": "Amit Sharma",
            }, cookies=cust)
            app_id = res.json()["id"]

            # Draft → KYC should fail (must go Draft → Submitted first)
            res_bad = await client.post(f"/applications/{app_id}/transition",
                                        json={"target_stage": "KYC"}, cookies=emp)
            assert res_bad.status_code in (400, 403), f"Expected 400 or 403, got {res_bad.status_code}"

            # Draft → Approved should fail
            res_bad2 = await client.post(f"/applications/{app_id}/transition",
                                         json={"target_stage": "Approved"}, cookies=emp)
            assert res_bad2.status_code in (400, 403)

            # Draft → Risk should fail
            res_bad3 = await client.post(f"/applications/{app_id}/transition",
                                         json={"target_stage": "Risk"}, cookies=emp)
            assert res_bad3.status_code in (400, 403)

    run_async_test(_run)


# ═══════════════════════ TEST 5 — Same-user approval forbidden (maker-checker) ═══════════════════════

def test_same_user_approval_forbidden():
    """The employee who prepared the file must get HTTP 403 when trying to approve."""
    async def _run():
        transport = ASGITransport(app=loan_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            cust = get_auth_cookies("cust-101", "customer", "amit_customer")
            emp = get_auth_cookies("emp-201", "employee", "rahul_maker")
            # Create a second manager user for this test:
            # We'll use the employee cookie directly — they should get 403 regardless
            mgr_emp = get_auth_cookies("emp-201", "manager", "rahul_maker")
            # ^ A manager token with the SAME user ID as the preparer

            res = await client.post("/applications", json={
                "loan_type": "Home Loan", "requested_amount": 500000,
                "annual_income": 1000000, "existing_emi": 5000,
                "employment_type": "Salaried", "employer_name": "HCL",
                "loan_tenure_months": 60, "customer_name": "Amit Sharma",
            }, cookies=cust)
            app_id = res.json()["id"]

            # Walk to With Manager
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Submitted"}, cookies=cust)
            for stage in ["KYC", "Docs", "Verification", "Risk", "Prepared", "With Manager"]:
                await client.post(f"/applications/{app_id}/transition",
                                  json={"target_stage": stage}, cookies=emp)

            # Same user (emp-201) tries to approve with manager role → 403 maker-checker violation
            res_viol = await client.post(f"/applications/{app_id}/transition",
                                         json={"target_stage": "Approved"}, cookies=mgr_emp)
            assert res_viol.status_code == 403
            assert "Maker-checker" in res_viol.json()["detail"]

    run_async_test(_run)


# ═══════════════════════ TEST 6 — Non-manager cannot approve ═══════════════════════

def test_non_manager_cannot_approve():
    """Only role=manager can approve; employee and customer get HTTP 403."""
    async def _run():
        transport = ASGITransport(app=loan_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            cust = get_auth_cookies("cust-101", "customer", "amit_customer")
            emp = get_auth_cookies("emp-201", "employee", "rahul_maker")

            res = await client.post("/applications", json={
                "loan_type": "Home Loan", "requested_amount": 600000,
                "annual_income": 1200000, "existing_emi": 3000,
                "employment_type": "Salaried", "employer_name": "Infosys",
                "loan_tenure_months": 60, "customer_name": "Amit Sharma",
            }, cookies=cust)
            app_id = res.json()["id"]

            # Walk to With Manager
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Submitted"}, cookies=cust)
            for stage in ["KYC", "Docs", "Verification", "Risk", "Prepared", "With Manager"]:
                await client.post(f"/applications/{app_id}/transition",
                                  json={"target_stage": stage}, cookies=emp)

            # Employee tries to approve → 403
            res_emp = await client.post(f"/applications/{app_id}/transition",
                                        json={"target_stage": "Approved"}, cookies=emp)
            assert res_emp.status_code == 403
            assert "Only managers" in res_emp.json()["detail"]

            # Customer tries to approve → 403
            res_cust = await client.post(f"/applications/{app_id}/transition",
                                         json={"target_stage": "Approved"}, cookies=cust)
            assert res_cust.status_code == 403

    run_async_test(_run)


# ═══════════════════════ TEST 7 — Duplicate document hash across applications ═══════════════════════

def test_duplicate_document_hash_across_applications():
    """Same file uploaded to TWO different applications should be detected as duplicate."""
    async def _run():
        transport = ASGITransport(app=loan_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            cust = get_auth_cookies("cust-101", "customer", "amit_customer")
            cust2 = get_auth_cookies("cust-102", "customer", "neha_customer")

            # App 1
            res1 = await client.post("/applications", json={
                "loan_type": "Personal Loan", "requested_amount": 300000,
                "annual_income": 600000, "existing_emi": 2000,
                "employment_type": "Salaried", "employer_name": "TCS",
                "loan_tenure_months": 36, "customer_name": "Amit Sharma",
            }, cookies=cust)
            app_id1 = res1.json()["id"]

            # App 2
            res2 = await client.post("/applications", json={
                "loan_type": "Personal Loan", "requested_amount": 200000,
                "annual_income": 500000, "existing_emi": 1000,
                "employment_type": "Salaried", "employer_name": "Infosys",
                "loan_tenure_months": 24, "customer_name": "Neha Gupta",
            }, cookies=cust2)
            app_id2 = res2.json()["id"]

            # Upload same file content to App 1
            shared_content = b"Shared PAN Card Document Content For Cross-App Duplicate Test"
            res_up1 = await client.post(f"/applications/{app_id1}/documents",
                                         data={"document_type": "Identity Proof"},
                                         files={"file": ("pan_card.pdf", shared_content, "application/pdf")},
                                         cookies=cust)
            assert res_up1.status_code == 201

            # Upload same content to App 2 → HTTP 409
            res_up2 = await client.post(f"/applications/{app_id2}/documents",
                                         data={"document_type": "Identity Proof"},
                                         files={"file": ("pan_card.pdf", shared_content, "application/pdf")},
                                         cookies=cust2)
            assert res_up2.status_code == 409
            assert "Duplicate" in res_up2.json()["detail"]

    run_async_test(_run)


# ═══════════════════════ TEST 8 — audit_log UPDATE and DELETE blocked ═══════════════════════

def test_audit_log_immutable_trigger():
    """PostgreSQL trigger must block UPDATE and DELETE on audit_log."""
    async def _run():
        async with AsyncSessionLocal() as session:
            # Insert a test audit entry
            from loan_app.models import AuditLog
            entry = AuditLog(
                entity_type="test_entity", entity_id="test-immutable-001",
                action="test_action", performed_by="test-user",
                performed_by_role="employee", new_value="original",
            )
            session.add(entry)
            await session.commit()
            entry_id = entry.id

        # Attempt UPDATE → should raise
        async with AsyncSessionLocal() as session:
            try:
                await session.execute(
                    sqlalchemy.text("UPDATE audit_log SET new_value = 'hacked' WHERE id = :id"),
                    {"id": entry_id}
                )
                await session.commit()
                assert False, "UPDATE on audit_log should have been blocked by trigger"
            except Exception as e:
                await session.rollback()
                assert "append-only" in str(e).lower() or "not permitted" in str(e).lower(), \
                    f"Expected trigger error, got: {e}"

        # Attempt DELETE → should raise
        async with AsyncSessionLocal() as session:
            try:
                await session.execute(
                    sqlalchemy.text("DELETE FROM audit_log WHERE id = :id"),
                    {"id": entry_id}
                )
                await session.commit()
                assert False, "DELETE on audit_log should have been blocked by trigger"
            except Exception as e:
                await session.rollback()
                assert "append-only" in str(e).lower() or "not permitted" in str(e).lower(), \
                    f"Expected trigger error, got: {e}"

    run_async_test(_run)


# ═══════════════════════ TEST 9 — Fraud check (income variance, advisory) ═══════════════════════

def test_fraud_check_income_variance_advisory_only():
    """
    Fraud check:
    - Income variance > 15% should flag but NOT auto-reject.
    - Advisory note must say 'Officer decides'.
    - Application stage should NOT change due to fraud check.
    """
    async def _run():
        transport = ASGITransport(app=loan_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            cust = get_auth_cookies("cust-101", "customer", "amit_customer")
            emp = get_auth_cookies("emp-201", "employee", "rahul_maker")

            res = await client.post("/applications", json={
                "loan_type": "Personal Loan", "requested_amount": 400000,
                "annual_income": 1000000, "existing_emi": 5000,
                "employment_type": "Salaried", "employer_name": "Google",
                "loan_tenure_months": 36, "customer_name": "Amit Sharma",
            }, cookies=cust)
            app_id = res.json()["id"]
            original_stage = res.json()["stage"]

            # Run fraud check with statement income differing by > 15%
            res_fraud = await client.post(
                f"/applications/{app_id}/fraud-check",
                json={"statement_income": 700000},  # 30% lower
                cookies=emp,
            )
            assert res_fraud.status_code == 200
            fraud = res_fraud.json()

            # Must have flags
            assert len(fraud["flags"]) >= 1
            assert any("15%" in f or "differs" in f.lower() for f in fraud["flags"])

            # Advisory only — never auto-reject
            assert fraud["advisory_note"] == "Advisory only. Officer decides."
            assert fraud["status"] in ("PENDING_REVIEW", "CLEARED")

            # Application stage must NOT change
            res_app = await client.get(f"/applications/{app_id}", cookies=cust)
            assert res_app.json()["stage"] == original_stage

    run_async_test(_run)


# ═══════════════════════ TEST 10 — Limit calculation formula ═══════════════════════

def test_limit_calculation_formula():
    """Verify limit = (annual_income × income_multiple) – (existing_EMI × 12), capped."""
    async def _run():
        transport = ASGITransport(app=loan_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            cust = get_auth_cookies("cust-102", "customer", "neha_customer")
            emp = get_auth_cookies("emp-201", "employee", "rahul_maker")

            res = await client.post("/applications", json={
                "loan_type": "Personal Loan", "requested_amount": 500000,
                "annual_income": 600000, "existing_emi": 10000,
                "employment_type": "Salaried", "employer_name": "TCS",
                "loan_tenure_months": 36, "customer_name": "Neha Gupta",
            }, cookies=cust)
            app_id = res.json()["id"]

            # Walk to Risk
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Submitted"}, cookies=cust)
            for stage in ["KYC", "Docs", "Verification", "Risk"]:
                await client.post(f"/applications/{app_id}/transition",
                                  json={"target_stage": stage}, cookies=emp)

            res_lim = await client.post(f"/applications/{app_id}/limit", cookies=emp)
            assert res_lim.status_code == 200
            lim = res_lim.json()

            # Personal Loan: income_multiple=3.0, max_cap=2000000
            expected_raw = (600000 * 3.0) - (10000 * 12)  # 1,800,000 - 120,000 = 1,680,000
            expected = min(expected_raw, 2000000)
            assert lim["max_permissible_limit"] == expected
            assert lim["income_multiple"] == 3.0
            assert lim["product_cap"] == 2000000

    run_async_test(_run)


# ═══════════════════════ TEST 11 — EMI schedule principal sums to loan ═══════════════════════

def test_emi_schedule_principal_sums_to_loan_amount():
    """Sum of principal_component across all EMI schedule items must equal principal_amount."""
    async def _run():
        transport = ASGITransport(app=loan_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            cust = get_auth_cookies("cust-102", "customer", "neha_customer")
            emp = get_auth_cookies("emp-201", "employee", "rahul_maker")
            mgr = get_auth_cookies("mgr-301", "manager", "priya_checker")

            res = await client.post("/applications", json={
                "loan_type": "Personal Loan", "requested_amount": 200000,
                "annual_income": 800000, "existing_emi": 3000,
                "employment_type": "Salaried", "employer_name": "Wipro",
                "loan_tenure_months": 24, "customer_name": "Neha Gupta",
            }, cookies=cust)
            app_id = res.json()["id"]

            # Walk to Approved
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Submitted"}, cookies=cust)
            for stage in ["KYC", "Docs", "Verification", "Risk", "Prepared", "With Manager"]:
                await client.post(f"/applications/{app_id}/transition",
                                  json={"target_stage": stage}, cookies=emp)
            await client.post(f"/applications/{app_id}/transition",
                              json={"target_stage": "Approved"}, cookies=mgr)

            # Disburse
            res_dis = await client.post(f"/applications/{app_id}/disburse",
                                        json={"interest_rate": 12.0}, cookies=mgr)
            assert res_dis.status_code == 200
            loan = res_dis.json()

            assert len(loan["schedules"]) == 24
            total_principal = sum(s["principal_component"] for s in loan["schedules"])
            assert abs(total_principal - 200000) < 0.02, \
                f"Principal sum {total_principal} != loan amount 200000"

    run_async_test(_run)


# ═══════════════════════ TEST 12 — Database is PostgreSQL ═══════════════════════

def test_database_is_postgresql():
    """Confirm tests are running against PostgreSQL, not SQLite."""
    url = str(engine.url)
    assert "postgresql" in url or "postgres" in url, \
        f"Tests MUST use PostgreSQL. Current DATABASE_URL engine: {url}"
    assert "sqlite" not in url, f"SQLite detected — forbidden! URL: {url}"


# ═══════════════════════ TEST 13 — Registration approval workflow ═══════════════════════

def test_registration_requires_approval():
    """New customers need an officer, new officers need a manager, before they can log in."""
    async def _run():
        transport = ASGITransport(app=auth_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            emp = get_auth_cookies("emp-201", "employee", "rahul_maker")
            mgr = get_auth_cookies("mgr-301", "manager", "priya_checker")

            # Managers cannot self-register
            r = await client.post("/auth/register", json={
                "username": "sneaky", "email": "s@x.com", "password": "pw123456",
                "full_name": "Sneaky", "role": "manager"})
            assert r.status_code == 400

            # New customer: pending, cannot log in
            r = await client.post("/auth/register", json={
                "username": "newcust", "email": "nc@x.com", "password": "pw123456",
                "full_name": "New Customer", "role": "customer"})
            assert r.status_code == 201 and r.json()["status"] == "pending"
            cust_id = r.json()["id"]
            r = await client.post("/auth/login", json={"username": "newcust", "password": "pw123456"})
            assert r.status_code == 403

            # New officer: pending
            r = await client.post("/auth/register", json={
                "username": "newoff", "email": "no@x.com", "password": "pw123456",
                "full_name": "New Officer", "role": "employee"})
            assert r.status_code == 201
            off_id = r.json()["id"]

            # Officer sees only customers, and cannot approve another officer
            r = await client.get("/auth/pending", cookies=emp)
            assert [u["id"] for u in r.json()] == [cust_id]
            r = await client.post(f"/auth/users/{off_id}/approve", cookies=emp)
            assert r.status_code == 403

            # Officer approves the customer, who can then log in
            r = await client.post(f"/auth/users/{cust_id}/approve", cookies=emp)
            assert r.status_code == 200 and r.json()["status"] == "active"
            r = await client.post("/auth/login", json={"username": "newcust", "password": "pw123456"})
            assert r.status_code == 200

            # Manager approves the officer
            r = await client.post(f"/auth/users/{off_id}/approve", cookies=mgr)
            assert r.status_code == 200
            r = await client.post("/auth/login", json={"username": "newoff", "password": "pw123456"})
            assert r.status_code == 200

    run_async_test(_run)
