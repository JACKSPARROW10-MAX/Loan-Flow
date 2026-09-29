"""
LoanFlow – Auth Service: User registration, login, RBAC.
JWT stored in httpOnly cookies with CSRF protection.
"""
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, Response, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, String, DateTime, select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.database import Base, get_db, init_db
from shared.security import (
    create_access_token, set_auth_cookies, clear_auth_cookies,
    get_current_user, require_role, verify_csrf,
    ROLE_CUSTOMER, ROLE_EMPLOYEE, ROLE_MANAGER,
    ACCESS_TOKEN_COOKIE,
)
from shared.config import get_settings
from shared.user_model import UserModel

settings = get_settings()

# ─── Password hashing ───
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─── Rate limiter ───
limiter = Limiter(key_func=get_remote_address)

# ═══════════════════════ ORM Model ═══════════════════════

# UserModel is defined in shared/user_model.py (imported below) so that
# loan_app can resolve its foreign keys to `users` without the auth service.


# ═══════════════════════ Pydantic Schemas ═══════════════════════

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: str
    role: str = ROLE_CUSTOMER  # Default; admin can override


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    role: str
    status: str = "active"
    created_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════ FastAPI App ═══════════════════════

app = FastAPI(title="LoanFlow Auth Service", version="1.0.0")

# ─── Middleware ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-csrf-token"],
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.on_event("startup")
async def startup():
    await init_db()
    # create_all does not alter existing tables: add the approval-status column if missing
    from shared.database import engine
    if "postgres" in str(engine.url):
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active'"
            ))
    # Seed default users if none exist
    from shared.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserModel).limit(1))
        if result.scalars().first() is None:
            seed_users = [
                UserModel(
                    id=str(uuid.uuid4()), username="admin",
                    email="admin@loanflow.dev", full_name="System Admin",
                    hashed_password=pwd_context.hash("admin123"),
                    role=ROLE_MANAGER,
                ),
                UserModel(
                    id=str(uuid.uuid4()), username="employee1",
                    email="employee1@loanflow.dev", full_name="Rahul Verma",
                    hashed_password=pwd_context.hash("emp123"),
                    role=ROLE_EMPLOYEE,
                ),
                UserModel(
                    id=str(uuid.uuid4()), username="customer1",
                    email="customer1@loanflow.dev", full_name="Amit Sharma",
                    hashed_password=pwd_context.hash("cust123"),
                    role=ROLE_CUSTOMER,
                ),
                UserModel(
                    id=str(uuid.uuid4()), username="customer2",
                    email="customer2@loanflow.dev", full_name="Rajesh Patil",
                    hashed_password=pwd_context.hash("cust123"),
                    role=ROLE_CUSTOMER,
                ),
                UserModel(
                    id=str(uuid.uuid4()), username="manager1",
                    email="manager1@loanflow.dev", full_name="Priya Mehta",
                    hashed_password=pwd_context.hash("mgr123"),
                    role=ROLE_MANAGER,
                ),
            ]
            session.add_all(seed_users)
            await session.commit()


# ═══════════════════════ Endpoints ═══════════════════════

@app.post("/auth/register", response_model=UserResponse, status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # Check if username or email already exists
    existing = await db.execute(
        select(UserModel).where(
            (UserModel.username == body.username) | (UserModel.email == body.email)
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Username or email already exists")

    # Self-registration is only for customers and loan officers; managers are provisioned internally.
    if body.role not in {ROLE_CUSTOMER, ROLE_EMPLOYEE}:
        raise HTTPException(status_code=400, detail="Only customer or officer accounts can be registered")

    # New accounts cannot log in until approved (customers by an officer, officers by a manager).
    user = UserModel(
        username=body.username,
        email=body.email,
        full_name=body.full_name,
        hashed_password=pwd_context.hash(body.password),
        role=body.role,
        status="pending",
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@app.post("/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Authenticate and set httpOnly JWT cookie."""
    result = await db.execute(
        select(UserModel).where(UserModel.username == body.username)
    )
    user = result.scalars().first()
    if not user or not pwd_context.verify(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.status == "pending":
        raise HTTPException(status_code=403, detail="Your account is awaiting approval")
    if user.status == "rejected":
        raise HTTPException(status_code=403, detail="Your registration was rejected")

    token = create_access_token(user_id=user.id, role=user.role, username=user.username)
    csrf_token = set_auth_cookies(response, token)

    return {
        "message": "Login successful",
        "access_token": token,
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
        },
        "csrf_token": csrf_token,
    }


@app.post("/auth/logout")
async def logout(response: Response):
    """Clear auth cookies."""
    clear_auth_cookies(response)
    return {"message": "Logged out"}


@app.get("/auth/me", response_model=UserResponse)
async def get_me(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current user profile."""
    result = await db.execute(select(UserModel).where(UserModel.id == user["sub"]))
    db_user = result.scalars().first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@app.get("/auth/users", response_model=list[UserResponse])
async def list_users(
    user: dict = Depends(require_role(ROLE_MANAGER, ROLE_EMPLOYEE)),
    db: AsyncSession = Depends(get_db),
):
    """List all users (manager/employee only)."""
    result = await db.execute(select(UserModel))
    return result.scalars().all()


def _can_review(reviewer_role: str, target_role: str) -> bool:
    """Officers approve customers; managers approve officers (and customers)."""
    if reviewer_role == ROLE_MANAGER:
        return target_role in {ROLE_CUSTOMER, ROLE_EMPLOYEE}
    if reviewer_role == ROLE_EMPLOYEE:
        return target_role == ROLE_CUSTOMER
    return False


@app.get("/auth/pending", response_model=list[UserResponse])
async def list_pending(
    user: dict = Depends(require_role(ROLE_MANAGER, ROLE_EMPLOYEE)),
    db: AsyncSession = Depends(get_db),
):
    """Registrations waiting for the caller to review."""
    result = await db.execute(
        select(UserModel).where(UserModel.status == "pending").order_by(UserModel.created_at)
    )
    return [u for u in result.scalars().all() if _can_review(user["role"], u.role)]


async def _review(user_id: str, reviewer: dict, db: AsyncSession, new_status: str):
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    target = result.scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if not _can_review(reviewer["role"], target.role):
        raise HTTPException(status_code=403, detail="You are not allowed to review this account")
    if target.status != "pending":
        raise HTTPException(status_code=409, detail=f"Account is already {target.status}")
    target.status = new_status
    await db.flush()
    await db.refresh(target)
    return target


@app.post("/auth/users/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: str,
    user: dict = Depends(require_role(ROLE_MANAGER, ROLE_EMPLOYEE)),
    db: AsyncSession = Depends(get_db),
):
    return await _review(user_id, user, db, "active")


@app.post("/auth/users/{user_id}/reject", response_model=UserResponse)
async def reject_user(
    user_id: str,
    user: dict = Depends(require_role(ROLE_MANAGER, ROLE_EMPLOYEE)),
    db: AsyncSession = Depends(get_db),
):
    return await _review(user_id, user, db, "rejected")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
