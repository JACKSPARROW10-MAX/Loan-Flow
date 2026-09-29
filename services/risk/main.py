"""
LoanFlow – Risk Scoring Service.
Exposes a simple risk scoring model (scikit-learn logistic regression).
"""
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="LoanFlow Risk Scoring Service", version="1.0.0")


class ScoreRequest(BaseModel):
    annual_income: float
    requested_amount: float
    existing_emi: float
    employment_type: str = "Salaried"
    loan_tenure_months: int = 60


class ScoreResponse(BaseModel):
    score: float
    band: str
    factors: list[dict]


def compute_risk_score(data: ScoreRequest) -> tuple[float, str, list[dict]]:
    """
    Simple rule-based + weighted scoring model.
    In production, this would use a trained scikit-learn model.
    """
    score = 50.0
    factors = []

    # 1. Income factor
    if data.annual_income > 1500000:
        score += 18
        factors.append({"factor": "High income", "impact": "+18", "detail": f"₹{data.annual_income:,.0f}"})
    elif data.annual_income > 800000:
        score += 10
        factors.append({"factor": "Good income", "impact": "+10", "detail": f"₹{data.annual_income:,.0f}"})
    elif data.annual_income > 400000:
        score += 3
        factors.append({"factor": "Moderate income", "impact": "+3", "detail": f"₹{data.annual_income:,.0f}"})
    else:
        score -= 12
        factors.append({"factor": "Low income", "impact": "-12", "detail": f"₹{data.annual_income:,.0f}"})

    # 2. EMI burden
    monthly_income = data.annual_income / 12
    emi_ratio = data.existing_emi / monthly_income if monthly_income > 0 else 1
    if emi_ratio < 0.15:
        score += 12
        factors.append({"factor": "Low EMI burden", "impact": "+12", "detail": f"{emi_ratio:.1%}"})
    elif emi_ratio < 0.35:
        score += 5
        factors.append({"factor": "Moderate EMI burden", "impact": "+5", "detail": f"{emi_ratio:.1%}"})
    elif emi_ratio > 0.5:
        score -= 18
        factors.append({"factor": "High EMI burden", "impact": "-18", "detail": f"{emi_ratio:.1%}"})

    # 3. Loan-to-income ratio
    lti = data.requested_amount / data.annual_income if data.annual_income > 0 else 10
    if lti < 1.5:
        score += 12
        factors.append({"factor": "Conservative LTI", "impact": "+12", "detail": f"{lti:.1f}x"})
    elif lti < 3:
        score += 5
        factors.append({"factor": "Moderate LTI", "impact": "+5", "detail": f"{lti:.1f}x"})
    elif lti > 5:
        score -= 15
        factors.append({"factor": "High LTI", "impact": "-15", "detail": f"{lti:.1f}x"})

    # 4. Employment type
    emp_scores = {"Salaried": 8, "Business": 3, "Self-Employed": 2}
    emp_bonus = emp_scores.get(data.employment_type, -5)
    score += emp_bonus
    factors.append({"factor": f"Employment: {data.employment_type}", "impact": f"{emp_bonus:+d}", "detail": ""})

    # Clamp
    score = max(0, min(100, round(score, 1)))

    # Band
    if score >= 75:
        band = "Low"
    elif score >= 50:
        band = "Medium"
    elif score >= 25:
        band = "High"
    else:
        band = "Very High"

    return score, band, factors


@app.post("/score", response_model=ScoreResponse)
async def score(body: ScoreRequest):
    """Compute risk score for a loan application."""
    score_val, band, factors = compute_risk_score(body)
    return ScoreResponse(score=score_val, band=band, factors=factors)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "risk"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
