"""
LoanFlow – ORM models for the Loan Application service.
All core tables: Application, Document, RuleResult, RiskScore, AuditLog, PolicyRule, Events.
"""
import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Text, Boolean,
    Enum as SAEnum, ForeignKey, JSON, Index, LargeBinary,
)
from sqlalchemy.orm import relationship, deferred

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.database import Base
from shared.user_model import UserModel  # noqa: F401  registers `users` for FKs


# ═══════════════════════ Enums ═══════════════════════

class ApplicationStage(str, enum.Enum):
    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    KYC = "KYC"
    DOCS = "Docs"
    VERIFICATION = "Verification"
    RISK = "Risk"
    PREPARED = "Prepared"
    WITH_MANAGER = "With Manager"
    APPROVED = "Approved"
    RETURNED = "Returned"
    REJECTED = "Rejected"


class DocumentStatus(str, enum.Enum):
    PENDING = "Pending"
    VERIFIED = "Verified"
    MISMATCH = "Mismatch"


class RiskBand(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    VERY_HIGH = "Very High"


# Valid state transitions
VALID_TRANSITIONS: dict[ApplicationStage, list[ApplicationStage]] = {
    ApplicationStage.DRAFT: [ApplicationStage.SUBMITTED],
    ApplicationStage.SUBMITTED: [ApplicationStage.KYC],
    ApplicationStage.KYC: [ApplicationStage.DOCS],
    ApplicationStage.DOCS: [ApplicationStage.VERIFICATION],
    ApplicationStage.VERIFICATION: [ApplicationStage.RISK],
    ApplicationStage.RISK: [ApplicationStage.PREPARED],
    ApplicationStage.PREPARED: [ApplicationStage.WITH_MANAGER],
    ApplicationStage.WITH_MANAGER: [
        ApplicationStage.APPROVED,
        ApplicationStage.RETURNED,
        ApplicationStage.REJECTED,
    ],
    ApplicationStage.RETURNED: [ApplicationStage.SUBMITTED],  # Can resubmit
    ApplicationStage.APPROVED: [],
    ApplicationStage.REJECTED: [],
}


# ═══════════════════════ Models ═══════════════════════

class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    app_number = Column(String(20), unique=True, nullable=False, index=True)
    customer_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    customer_name = Column(String(255), nullable=False)

    # Loan details
    loan_type = Column(String(100), nullable=False)  # Home Loan, Personal Loan, etc.
    requested_amount = Column(Float, nullable=False)
    annual_income = Column(Float, nullable=False, default=0)
    existing_emi = Column(Float, nullable=False, default=0)
    employment_type = Column(String(100), default="Salaried")
    employer_name = Column(String(255), default="")
    loan_tenure_months = Column(Integer, default=60)

    # Computed fields
    max_permissible_limit = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    risk_band = Column(String(50), nullable=True)
    eligibility_passed = Column(Integer, default=0)
    eligibility_total = Column(Integer, default=0)

    # Workflow
    stage = Column(SAEnum(ApplicationStage), default=ApplicationStage.DRAFT, nullable=False)
    prepared_by = Column(String, nullable=True)  # employee who prepared
    approved_by = Column(String, nullable=True)  # manager who approved/rejected
    sla_days = Column(Integer, default=7)
    sla_deadline = Column(DateTime(timezone=True), nullable=True)

    # KYC
    kyc_verified = Column(Boolean, default=False)
    kyc_data = Column(JSON, nullable=True)  # Stored masked

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    documents = relationship("Document", back_populates="application", lazy="selectin")
    rule_results = relationship("RuleResult", back_populates="application", lazy="selectin")
    fraud_alerts = relationship("FraudAlert", back_populates="application", lazy="selectin")

    __table_args__ = (
        Index("ix_applications_stage", "stage"),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String, ForeignKey("applications.id"), nullable=False, index=True)
    document_type = Column(String(100), nullable=False)  # Aadhaar, PAN, Income Proof, etc.
    file_name = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)  # Storage path
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256 for duplicate detection
    file_size = Column(Integer, default=0)
    mime_type = Column(String(100), default="application/octet-stream")
    status = Column(SAEnum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)
    malware_scanned = Column(Boolean, default=True)
    malware_scan_status = Column(String(50), default="CLEAN")  # CLEAN, SUSPICIOUS, FAILED
    verified_by = Column(String, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    remarks = Column(Text, nullable=True)
    # Document fraud analysis (see doc_fraud.py): score 0-1, flag CLEAN|SUSPICIOUS|HIGH_RISK
    fraud_score = Column(Float, nullable=True)
    fraud_flag = Column(String(20), nullable=True)
    fraud_findings = Column(JSON, nullable=True)
    # Copy of the file kept in the database when object storage is unavailable
    file_content = deferred(Column(LargeBinary, nullable=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    application = relationship("Application", back_populates="documents")

    __table_args__ = (
        Index("ix_documents_hash", "file_hash"),
    )



class RuleResult(Base):
    __tablename__ = "rule_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String, ForeignKey("applications.id"), nullable=False, index=True)
    rule_name = Column(String(200), nullable=False)
    rule_description = Column(Text, nullable=True)
    passed = Column(Boolean, nullable=False)
    reason = Column(Text, nullable=False)
    evaluated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    application = relationship("Application", back_populates="rule_results")


class PolicyRule(Base):
    """Rules stored as JSON per loan product in Postgres, cached in Redis."""
    __tablename__ = "policy_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    loan_type = Column(String(100), nullable=False, index=True)
    rule_name = Column(String(200), nullable=False)
    rule_config = Column(JSON, nullable=False)
    # e.g. {"type": "min_income", "min": 300000, "description": "Minimum annual income ₹3L"}
    is_active = Column(Boolean, default=True)
    # Mandatory rules block approval when they fail; advisory rules only warn
    is_mandatory = Column(Boolean, default=True, server_default="true")
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    """Append-only audit log. A Postgres trigger blocks UPDATE/DELETE."""
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(100), nullable=False)  # application, document, etc.
    entity_id = Column(String, nullable=False, index=True)
    action = Column(String(100), nullable=False)  # created, stage_changed, etc.
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    performed_by = Column(String, nullable=False)
    performed_by_role = Column(String(50), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
    )


class EventLog(Base):
    """Postgres fallback for event bus."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, nullable=False, unique=True)
    event_type = Column(String(200), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    source = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ═══════════════════════ Servicing & Collection Models ═══════════════════════

class LoanAccount(Base):
    """Active loan account post-disbursement."""
    __tablename__ = "loan_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_number = Column(String(30), unique=True, nullable=False, index=True)
    application_id = Column(String, ForeignKey("applications.id"), nullable=False, index=True)
    customer_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    principal_amount = Column(Float, nullable=False)
    interest_rate = Column(Float, nullable=False, default=9.5)  # annual percentage
    tenure_months = Column(Integer, nullable=False)
    emi_amount = Column(Float, nullable=False)
    outstanding_balance = Column(Float, nullable=False)
    total_paid = Column(Float, default=0.0)
    status = Column(String(50), default="ACTIVE")  # ACTIVE, CLOSED, DELINQUENT
    disbursed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    next_due_date = Column(DateTime(timezone=True), nullable=True)

    emi_schedules = relationship("EMISchedule", back_populates="loan_account", cascade="all, delete-orphan", lazy="selectin")
    payments = relationship("PaymentTransaction", back_populates="loan_account", cascade="all, delete-orphan", lazy="selectin")


class EMISchedule(Base):
    """Repayment schedule item per monthly installment."""
    __tablename__ = "emi_schedules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    loan_account_id = Column(String, ForeignKey("loan_accounts.id"), nullable=False, index=True)
    installment_number = Column(Integer, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    emi_amount = Column(Float, nullable=False)
    principal_component = Column(Float, nullable=False)
    interest_component = Column(Float, nullable=False)
    outstanding_principal = Column(Float, nullable=False)
    status = Column(String(50), default="PENDING")  # PENDING, PAID, OVERDUE
    paid_at = Column(DateTime(timezone=True), nullable=True)
    paid_amount = Column(Float, default=0.0)

    loan_account = relationship("LoanAccount", back_populates="emi_schedules")


class PaymentTransaction(Base):
    """Payment records for loan EMI repayments."""
    __tablename__ = "payment_transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    loan_account_id = Column(String, ForeignKey("loan_accounts.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    payment_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    payment_method = Column(String(100), default="UPI")
    reference_number = Column(String(100), nullable=False, unique=True)
    status = Column(String(50), default="SUCCESS")

    loan_account = relationship("LoanAccount", back_populates="payments")


class CollectionCase(Base):
    """Delinquency tracking and collection follow-up tasks."""
    __tablename__ = "collection_cases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    loan_account_id = Column(String, ForeignKey("loan_accounts.id"), nullable=False, index=True)
    dpd = Column(Integer, default=0)  # Days Past Due
    bucket = Column(String(50), default="CURRENT")  # CURRENT, 1-30 DPD, 31-60 DPD, 61-90 DPD, 90+ DPD
    overdue_amount = Column(Float, default=0.0)
    assigned_to = Column(String, nullable=True)
    last_contact_date = Column(DateTime(timezone=True), nullable=True)
    next_action_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="OPEN")  # OPEN, RESOLVED, LEGAL
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class FraudAlert(Base):
    """Fraud and anomaly detection alerts. Advisory only - never auto-rejects."""
    __tablename__ = "fraud_alerts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String, ForeignKey("applications.id"), nullable=False, index=True)
    anomaly_score = Column(Float, nullable=False, default=0.0)  # 0.0 - 1.0
    risk_level = Column(String(50), default="LOW")  # LOW, MEDIUM, HIGH
    flags = Column(JSON, nullable=False, default=list)  # list of strings/reasons
    is_manual_review_required = Column(Boolean, default=False)
    status = Column(String(50), default="PENDING_REVIEW")  # PENDING_REVIEW, CLEARED, CONFIRMED
    advisory_note = Column(String(255), default="Advisory only. Officer decides.")
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    application = relationship("Application", back_populates="fraud_alerts")


