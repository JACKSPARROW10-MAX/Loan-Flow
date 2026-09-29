"""
LoanFlow – Audit Service.
Subscribes to events and writes append-only audit rows.
Also provides a read API for audit logs.
"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.database import get_db, init_db
from shared.security import get_current_user, require_role, ROLE_EMPLOYEE, ROLE_MANAGER

# Import the AuditLog model from loan_app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loan_app"))
from loan_app.models import AuditLog

app = FastAPI(title="LoanFlow Audit Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/audit/entity/{entity_id}")
async def get_entity_audit(
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """Get all audit entries for a given entity."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
            "action": r.action, "old_value": r.old_value, "new_value": r.new_value,
            "performed_by": r.performed_by, "performed_by_role": r.performed_by_role,
            "details": r.details, "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.get("/audit/recent")
async def get_recent_audit(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role(ROLE_EMPLOYEE, ROLE_MANAGER)),
):
    """Get most recent audit entries across all entities."""
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id,
            "action": r.action, "old_value": r.old_value, "new_value": r.new_value,
            "performed_by": r.performed_by, "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.get("/health")
async def health():
    return {"status": "ok", "service": "audit"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
