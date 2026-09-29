"""
LoanFlow – Pydantic schemas for the Loan Application service.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from .models import ApplicationStage, DocumentStatus, RiskBand


# ═══════════════════════ Application ═══════════════════════

class ApplicationCreate(BaseModel):
    loan_type: str = Field(..., example="Home Loan")
    requested_amount: float = Field(..., gt=0, example=500000)
    annual_income: float = Field(..., gt=0, example=1200000)
    existing_emi: float = Field(0, ge=0, example=5000)
    employment_type: str = Field("Salaried", example="Salaried")
    employer_name: str = Field("", example="TCS")
    loan_tenure_months: int = Field(60, ge=12, le=360, example=240)
    customer_name: str = Field("", example="Amit Sharma")


class ApplicationUpdate(BaseModel):
    requested_amount: Optional[float] = None
    annual_income: Optional[float] = None
    existing_emi: Optional[float] = None
    employment_type: Optional[str] = None
    employer_name: Optional[str] = None
    loan_tenure_months: Optional[int] = None


class ApplicationResponse(BaseModel):
    id: str
    app_number: str
    customer_id: str
    customer_name: str
    loan_type: str
    requested_amount: float
    annual_income: float
    existing_emi: float
    employment_type: str
    employer_name: str
    loan_tenure_months: int
    max_permissible_limit: Optional[float]
    risk_score: Optional[float]
    risk_band: Optional[str]
    eligibility_passed: int
    eligibility_total: int
    stage: str
    prepared_by: Optional[str]
    approved_by: Optional[str]
    kyc_verified: bool
    kyc_data: Optional[dict] = None
    sla_days: int
    sla_deadline: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationListItem(BaseModel):
    id: str
    app_number: str
    customer_name: str
    loan_type: str
    requested_amount: float
    stage: str
    eligibility_passed: int
    eligibility_total: int
    risk_score: Optional[float]
    risk_band: Optional[str]
    sla_days: int
    sla_deadline: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════ Stage Transition ═══════════════════════

class StageTransitionRequest(BaseModel):
    target_stage: str
    remarks: Optional[str] = None


# ═══════════════════════ Document ═══════════════════════

class DocumentResponse(BaseModel):
    id: str
    application_id: str
    document_type: str
    file_name: str
    file_hash: str
    file_size: int
    mime_type: Optional[str] = None
    status: str
    fraud_score: Optional[float] = None
    fraud_flag: Optional[str] = None
    fraud_findings: Optional[list[str]] = None
    malware_scanned: bool
    malware_scan_status: Optional[str] = "CLEAN"
    verified_by: Optional[str]
    verified_at: Optional[datetime]
    remarks: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentVerifyRequest(BaseModel):
    status: str  # Verified or Mismatch
    remarks: Optional[str] = None


# ═══════════════════════ Rule Result ═══════════════════════

class RuleResultResponse(BaseModel):
    id: str
    rule_name: str
    rule_description: Optional[str]
    passed: bool
    reason: str
    evaluated_at: datetime

    class Config:
        from_attributes = True


class EligibilityResponse(BaseModel):
    application_id: str
    passed: int
    total: int
    results: list[RuleResultResponse]


# ═══════════════════════ Risk Score ═══════════════════════

class RiskScoreResponse(BaseModel):
    application_id: str
    score: float
    band: str


# ═══════════════════════ Limit ═══════════════════════

class LimitResponse(BaseModel):
    application_id: str
    annual_income: float
    existing_emi: float
    income_multiple: float
    product_cap: float
    max_permissible_limit: float


# ═══════════════════════ Audit ═══════════════════════

class AuditLogResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    action: str
    old_value: Optional[str]
    new_value: Optional[str]
    performed_by: str
    performed_by_role: Optional[str]
    details: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════ KYC ═══════════════════════

class KYCResponse(BaseModel):
    application_id: str
    verified: bool
    masked_data: dict  # Sensitive fields masked


# ═══════════════════════ Servicing & Payment ═══════════════════════

class DisbursementRequest(BaseModel):
    interest_rate: Optional[float] = 9.5
    account_number: Optional[str] = None


class EMIScheduleItem(BaseModel):
    id: str
    installment_number: int
    due_date: datetime
    emi_amount: float
    principal_component: float
    interest_component: float
    outstanding_principal: float
    status: str
    paid_at: Optional[datetime] = None
    paid_amount: float = 0.0

    class Config:
        from_attributes = True


class LoanAccountResponse(BaseModel):
    id: str
    account_number: str
    application_id: str
    customer_id: str
    principal_amount: float
    interest_rate: float
    tenure_months: int
    emi_amount: float
    outstanding_balance: float
    total_paid: float
    status: str
    disbursed_at: datetime
    next_due_date: Optional[datetime] = None
    schedules: Optional[list[EMIScheduleItem]] = []

    class Config:
        from_attributes = True


class PaymentRequest(BaseModel):
    amount: float
    payment_method: str = "UPI"


class PaymentResponse(BaseModel):
    id: str
    loan_account_id: str
    amount: float
    payment_date: datetime
    payment_method: str
    reference_number: str
    status: str
    remaining_balance: float

    class Config:
        from_attributes = True


# ═══════════════════════ Collection ═══════════════════════

class CollectionCaseResponse(BaseModel):
    id: str
    loan_account_id: str
    account_number: Optional[str] = None
    customer_name: Optional[str] = None
    dpd: int
    bucket: str
    overdue_amount: float
    assigned_to: Optional[str] = None
    last_contact_date: Optional[datetime] = None
    next_action_date: Optional[datetime] = None
    notes: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class CollectionFollowUpRequest(BaseModel):
    notes: str
    next_action_date: Optional[datetime] = None
    status: Optional[str] = "OPEN"


class FraudCheckRequest(BaseModel):
    statement_income: Optional[float] = None
    force_recheck: bool = False


class FraudAlertResponse(BaseModel):
    id: str
    application_id: str
    anomaly_score: float
    risk_level: str
    flags: list[str]
    is_manual_review_required: bool
    status: str
    advisory_note: str = "Advisory only. Officer decides."
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════ Assessment Report & Analytics ═══════════════════════

class AssessmentReportResponse(BaseModel):
    application: ApplicationResponse
    kyc: Optional[dict] = None
    documents: list[DocumentResponse]
    rules: list[RuleResultResponse]
    risk: dict
    limit: dict
    fraud_alerts: list[FraudAlertResponse] = []
    maker_checker: dict
    audit_history: list[AuditLogResponse]


class AnalyticsSummaryResponse(BaseModel):
    total_applications: int
    approval_rate_pct: float
    stage_counts: dict[str, int]
    risk_distribution: dict[str, int]
    total_disbursed_volume: float
    active_loans_count: int
    delinquency_metrics: dict[str, float]




# ═══════════════════════ Rules & Regulations ═══════════════════════

class RuleWrite(BaseModel):
    loan_type: str = Field(..., min_length=1, max_length=100)   # product name, or "*" for all products
    rule_name: str = Field(..., min_length=1, max_length=200)
    rule_config: dict
    is_active: bool = True
    is_mandatory: bool = True


class RuleActiveRequest(BaseModel):
    is_active: bool
