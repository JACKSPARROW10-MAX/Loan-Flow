"""
LoanFlow – Configurable business rules.

Managers create, edit, activate and deactivate rules at runtime; nothing about
thresholds, limits or eligibility lives in the code. The code only knows the
*kinds* of rule it can evaluate (the catalog below) and how to run each kind
with whatever parameters the manager configured.

Each stored rule is: loan_type ("*" = every product), rule_name,
rule_config {"type": <catalog key>, "description": str, ...params},
is_active, is_mandatory.

Categories:
  eligibility – evaluated per application (Run Rules) and again at approval
  limit       – drives the maximum permissible loan amount
  risk        – drives the risk-band cut-offs
  fraud       – thresholds used by the application fraud check
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

ALL_PRODUCTS = "*"

# param types: number | integer | text | list (comma separated) | boolean
RULE_CATALOG: dict[str, dict[str, Any]] = {
    "min_income": {
        "label": "Minimum annual income", "category": "eligibility",
        "description": "Applicant's annual income must be at least the minimum.",
        "params": [{"name": "min", "label": "Minimum annual income (INR)", "type": "number", "default": 300000}],
    },
    "max_amount": {
        "label": "Maximum loan amount", "category": "eligibility",
        "description": "Requested amount must not exceed the maximum.",
        "params": [{"name": "max", "label": "Maximum amount (INR)", "type": "number", "default": 10000000}],
    },
    "min_amount": {
        "label": "Minimum loan amount", "category": "eligibility",
        "description": "Requested amount must be at least the minimum.",
        "params": [{"name": "min", "label": "Minimum amount (INR)", "type": "number", "default": 50000}],
    },
    "max_emi_ratio": {
        "label": "Maximum EMI-to-income ratio", "category": "eligibility",
        "description": "Existing EMIs must not exceed this share of monthly income.",
        "params": [{"name": "max_ratio", "label": "Maximum ratio (0.5 = 50%)", "type": "number", "default": 0.5}],
    },
    "employment_check": {
        "label": "Accepted employment types", "category": "eligibility",
        "description": "Employment type must be one of the accepted types.",
        "params": [{"name": "allowed", "label": "Accepted types (comma separated)", "type": "list",
                    "default": ["Salaried", "Self-Employed", "Business"]}],
    },
    "min_tenure_months": {
        "label": "Minimum tenure", "category": "eligibility",
        "description": "Requested tenure must be at least this many months.",
        "params": [{"name": "min", "label": "Minimum tenure (months)", "type": "integer", "default": 12}],
    },
    "max_tenure_months": {
        "label": "Maximum tenure", "category": "eligibility",
        "description": "Requested tenure must not exceed this many months.",
        "params": [{"name": "max", "label": "Maximum tenure (months)", "type": "integer", "default": 360}],
    },
    "min_age": {
        "label": "Minimum applicant age", "category": "eligibility",
        "description": "Applicant must be at least this old (uses the date of birth from KYC).",
        "params": [{"name": "min", "label": "Minimum age (years)", "type": "integer", "default": 21}],
    },
    "required_documents": {
        "label": "Required documents", "category": "eligibility",
        "description": "Listed document types must be uploaded (and optionally verified).",
        "params": [
            {"name": "types", "label": "Document types (comma separated)", "type": "list", "default": ["Aadhaar", "PAN"]},
            {"name": "must_be_verified", "label": "Must be verified by an officer", "type": "boolean", "default": False},
        ],
    },
    "income_multiple_limit": {
        "label": "Loan limit: income multiple and cap", "category": "limit",
        "description": "Maximum limit = annual income x multiple - 12 x existing EMI, capped.",
        "params": [
            {"name": "multiple", "label": "Income multiple", "type": "number", "default": 6.0},
            {"name": "cap", "label": "Product cap (INR)", "type": "number", "default": 10000000},
        ],
    },
    "risk_bands": {
        "label": "Risk band cut-offs", "category": "risk",
        "description": "Score at or above each cut-off falls in that band (Low > Medium > High, else Very High).",
        "params": [
            {"name": "low_min", "label": "Low risk from score", "type": "number", "default": 75},
            {"name": "medium_min", "label": "Medium risk from score", "type": "number", "default": 50},
            {"name": "high_min", "label": "High risk from score", "type": "number", "default": 25},
        ],
    },
    "fraud_income_variance": {
        "label": "Fraud: income variance vs statement", "category": "fraud",
        "description": "Flag when statement income differs from the form by more than this percentage.",
        "params": [{"name": "max_pct", "label": "Maximum variance (%)", "type": "number", "default": 15}],
    },
    "fraud_loan_to_income": {
        "label": "Fraud: loan-to-income multiple", "category": "fraud",
        "description": "Flag when the requested amount exceeds this multiple of annual income.",
        "params": [{"name": "max_multiple", "label": "Maximum multiple", "type": "number", "default": 8}],
    },
    "fraud_debt_ratio": {
        "label": "Fraud: existing debt load", "category": "fraud",
        "description": "Flag when existing EMIs exceed this share of monthly income.",
        "params": [{"name": "max_ratio", "label": "Maximum ratio (0.6 = 60%)", "type": "number", "default": 0.6}],
    },
    "fraud_delinquency": {
        "label": "Fraud: prior delinquency", "category": "fraud",
        "description": "Flag customers with past collection cases beyond this many days past due.",
        "params": [{"name": "max_dpd", "label": "Days past due", "type": "integer", "default": 30}],
    },
}


class RuleConfigError(ValueError):
    pass


def validate_config(cfg: dict) -> dict:
    """Validate and normalise a rule_config against the catalog."""
    if not isinstance(cfg, dict):
        raise RuleConfigError("rule_config must be an object")
    rtype = cfg.get("type")
    spec = RULE_CATALOG.get(rtype)
    if not spec:
        raise RuleConfigError(f"Unknown rule type '{rtype}'")
    out: dict[str, Any] = {"type": rtype, "description": str(cfg.get("description") or spec["label"])}
    for p in spec["params"]:
        raw = cfg.get(p["name"], p["default"])
        try:
            if p["type"] == "number":
                val: Any = float(raw)
            elif p["type"] == "integer":
                val = int(float(raw))
            elif p["type"] == "boolean":
                val = raw if isinstance(raw, bool) else str(raw).lower() in ("1", "true", "yes", "on")
            elif p["type"] == "list":
                items = raw if isinstance(raw, list) else str(raw).split(",")
                val = [str(i).strip() for i in items if str(i).strip()]
                if not val:
                    raise ValueError("empty list")
            else:
                val = str(raw)
        except (TypeError, ValueError):
            raise RuleConfigError(f"Invalid value for '{p['label']}'")
        if p["type"] in ("number", "integer") and val < 0:
            raise RuleConfigError(f"'{p['label']}' cannot be negative")
        out[p["name"]] = val
    return out


def rule_category(cfg: dict) -> Optional[str]:
    spec = RULE_CATALOG.get((cfg or {}).get("type"))
    return spec["category"] if spec else None


def _age_from_dob(dob: str) -> Optional[int]:
    try:
        born = datetime.strptime(dob[:10], "%Y-%m-%d").date()
    except Exception:
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def evaluate_rule(cfg: dict, application, documents=()) -> tuple[bool, str]:
    """Evaluate one eligibility rule. Returns (passed, reason)."""
    try:  # rules saved before a parameter existed get the catalog default for it
        cfg = validate_config(cfg)
    except RuleConfigError:
        pass
    rtype = cfg.get("type", "")

    if rtype == "min_income":
        lo = float(cfg.get("min", 0))
        ok = application.annual_income >= lo
        return ok, f"Annual income Rs.{application.annual_income:,.0f} {'>=' if ok else '<'} Rs.{lo:,.0f}"

    if rtype == "max_amount":
        hi = float(cfg.get("max", float("inf")))
        ok = application.requested_amount <= hi
        return ok, f"Requested Rs.{application.requested_amount:,.0f} {'<=' if ok else '>'} max Rs.{hi:,.0f}"

    if rtype == "min_amount":
        lo = float(cfg.get("min", 0))
        ok = application.requested_amount >= lo
        return ok, f"Requested Rs.{application.requested_amount:,.0f} {'>=' if ok else '<'} min Rs.{lo:,.0f}"

    if rtype == "max_emi_ratio":
        mx = float(cfg.get("max_ratio", 0.5))
        monthly = application.annual_income / 12
        ratio = application.existing_emi / monthly if monthly > 0 else 1
        ok = ratio <= mx
        return ok, f"EMI ratio {ratio:.2%} {'<=' if ok else '>'} {mx:.0%}"

    if rtype == "employment_check":
        allowed = cfg.get("allowed") or []
        ok = application.employment_type in allowed
        return ok, f"Employment type '{application.employment_type}' {'is' if ok else 'is not'} accepted ({', '.join(allowed)})"

    if rtype == "min_tenure_months":
        lo = int(cfg.get("min", 0))
        ok = application.loan_tenure_months >= lo
        return ok, f"Tenure {application.loan_tenure_months} months {'>=' if ok else '<'} {lo}"

    if rtype == "max_tenure_months":
        hi = int(cfg.get("max", 10**6))
        ok = application.loan_tenure_months <= hi
        return ok, f"Tenure {application.loan_tenure_months} months {'<=' if ok else '>'} {hi}"

    if rtype == "min_age":
        lo = int(cfg.get("min", 0))
        dob = (application.kyc_data or {}).get("dob") if application.kyc_data else None
        age = _age_from_dob(dob) if dob else None
        if age is None:
            return True, "Date of birth not available (run KYC); age not evaluated"
        ok = age >= lo
        return ok, f"Applicant age {age} {'>=' if ok else '<'} {lo}"

    if rtype == "required_documents":
        needed = cfg.get("types") or []
        must_verify = bool(cfg.get("must_be_verified", False))
        missing = []
        for t in needed:
            matches = [d for d in documents if d.document_type.lower() == t.lower()]
            if must_verify:
                matches = [d for d in matches if getattr(d.status, "value", d.status) == "Verified"]
            else:
                matches = [d for d in matches if getattr(d.status, "value", d.status) != "Mismatch"]
            if not matches:
                missing.append(t)
        if missing:
            return False, f"Missing {'verified ' if must_verify else ''}document(s): {', '.join(missing)}"
        return True, f"All required documents present: {', '.join(needed)}"

    return True, f"Rule type '{rtype}' is not evaluated per application"


def default_rules() -> list[dict]:
    """Starter rule set inserted once (per rule name and product) and then owned by managers."""
    def r(loan_type, name, cfg, mandatory=True):
        return {"loan_type": loan_type, "rule_name": name, "rule_config": validate_config(cfg), "is_mandatory": mandatory}

    rules = [
        r("Home Loan", "min_income", {"type": "min_income", "min": 300000, "description": "Minimum annual income Rs.3,00,000"}),
        r("Home Loan", "min_age", {"type": "min_age", "min": 21, "description": "Applicant must be at least 21 years old"}),
        r("Home Loan", "max_emi_ratio", {"type": "max_emi_ratio", "max_ratio": 0.5, "description": "Total EMIs must not exceed 50% of monthly income"}),
        r("Home Loan", "employment_required", {"type": "employment_check", "allowed": ["Salaried", "Self-Employed", "Business"], "description": "Must be Salaried, Self-Employed or Business"}),
        r("Home Loan", "max_amount", {"type": "max_amount", "max": 10000000, "description": "Maximum loan amount Rs.1,00,00,000"}),
        r("Personal Loan", "min_income", {"type": "min_income", "min": 200000, "description": "Minimum annual income Rs.2,00,000"}),
        r("Personal Loan", "max_amount", {"type": "max_amount", "max": 2000000, "description": "Maximum loan amount Rs.20,00,000"}),
        r("Personal Loan", "max_emi_ratio", {"type": "max_emi_ratio", "max_ratio": 0.4, "description": "Total EMIs must not exceed 40% of monthly income"}),
        # Limits per product
        r("Home Loan", "loan_limit", {"type": "income_multiple_limit", "multiple": 6.0, "cap": 10000000, "description": "Home loan limit: 6x income, cap Rs.1 crore"}),
        r("Personal Loan", "loan_limit", {"type": "income_multiple_limit", "multiple": 3.0, "cap": 2000000, "description": "Personal loan limit: 3x income, cap Rs.20 lakh"}),
        r("Vehicle Loan", "loan_limit", {"type": "income_multiple_limit", "multiple": 4.0, "cap": 5000000, "description": "Vehicle loan limit: 4x income, cap Rs.50 lakh"}),
        # Global rules
        r(ALL_PRODUCTS, "risk_bands", {"type": "risk_bands", "low_min": 75, "medium_min": 50, "high_min": 25, "description": "Risk band cut-offs"}, False),
        r(ALL_PRODUCTS, "fraud_income_variance", {"type": "fraud_income_variance", "max_pct": 15, "description": "Statement income may differ from the form by at most 15%"}, False),
        r(ALL_PRODUCTS, "fraud_loan_to_income", {"type": "fraud_loan_to_income", "max_multiple": 8, "description": "Flag loans above 8x annual income"}, False),
        r(ALL_PRODUCTS, "fraud_debt_ratio", {"type": "fraud_debt_ratio", "max_ratio": 0.6, "description": "Flag existing EMIs above 60% of monthly income"}, False),
        r(ALL_PRODUCTS, "fraud_delinquency", {"type": "fraud_delinquency", "max_dpd": 30, "description": "Flag past delinquency beyond 30 days"}, False),
    ]
    return rules
