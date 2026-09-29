"""
LoanFlow – Mock KYC Service.
Returns deterministic KYC verification data for development.
"""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="LoanFlow Mock KYC Service", version="1.0.0")


class KYCRequest(BaseModel):
    customer_name: str
    customer_id: str


class KYCResult(BaseModel):
    aadhaar_number: str
    pan_number: str
    dob: str
    address: str
    phone: str
    verified: bool


@app.post("/kyc/verify", response_model=KYCResult)
async def verify_kyc(body: KYCRequest):
    """Return mock KYC data. Always verifies successfully."""
    # Deterministic mock data based on customer name
    return KYCResult(
        aadhaar_number="9876-5432-1098",
        pan_number="ABCDE1234F",
        dob="1990-05-15",
        address="42, Koramangala 4th Block, Bengaluru 560034",
        phone="9876543210",
        verified=True,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock_kyc"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
