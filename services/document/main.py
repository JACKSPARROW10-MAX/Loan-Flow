"""
LoanFlow – Document & Assessment Report Service.
Handles document metadata, signed URLs, and PDF assessment report compilation.
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
import httpx
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.config import get_settings

settings = get_settings()
app = FastAPI(title="LoanFlow Document Service", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "document"}


@app.get("/documents/health")
async def doc_health():
    return {"status": "ok", "service": "document"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
