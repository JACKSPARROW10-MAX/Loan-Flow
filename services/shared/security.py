"""
LoanFlow – Security utilities.
JWT stored in httpOnly Secure SameSite cookie with CSRF protection.
"""
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, Response, HTTPException, status, Depends
from jose import jwt, JWTError

from .config import get_settings

settings = get_settings()

# ─── Roles ───
ROLE_CUSTOMER = "customer"
ROLE_EMPLOYEE = "employee"
ROLE_MANAGER = "manager"
ALL_ROLES = {ROLE_CUSTOMER, ROLE_EMPLOYEE, ROLE_MANAGER}

# ─── Cookie names ───
ACCESS_TOKEN_COOKIE = "lf_access_token"
CSRF_TOKEN_COOKIE = "lf_csrf_token"
CSRF_HEADER = "x-csrf-token"


# ──────────────────── JWT helpers ────────────────────

def create_access_token(user_id: str, role: str, username: str, extra: dict | None = None) -> str:
    """Create a signed JWT with user claims."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "username": username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
        )


# ──────────────────── CSRF helpers ────────────────────

def generate_csrf_token() -> str:
    """Generate a random CSRF token."""
    return secrets.token_hex(32)


def sign_csrf_token(token: str) -> str:
    """HMAC-sign a CSRF token for the cookie."""
    return hmac.new(
        settings.csrf_secret.encode(), token.encode(), hashlib.sha256
    ).hexdigest()


def verify_csrf(request: Request) -> None:
    """
    Double-submit cookie pattern:
    - CSRF token stored in a readable cookie (lf_csrf_token)
    - Same token must be sent in X-CSRF-Token header
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return  # Safe methods don't need CSRF

    cookie_token = request.cookies.get(CSRF_TOKEN_COOKIE, "")
    header_token = request.headers.get(CSRF_HEADER, "")

    if not cookie_token or not header_token:
        raise HTTPException(status_code=403, detail="Missing CSRF token")

    if not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")


# ──────────────────── Cookie setters ────────────────────

def set_auth_cookies(response: Response, access_token: str) -> str:
    """Set JWT in httpOnly cookie and CSRF token in a readable cookie. Returns CSRF token."""
    csrf_token = generate_csrf_token()

    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=CSRF_TOKEN_COOKIE,
        value=csrf_token,
        httponly=False,   # JS needs to read this for the header
        secure=True,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    """Remove auth and CSRF cookies."""
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(CSRF_TOKEN_COOKIE, path="/")


# ──────────────────── FastAPI dependencies ────────────────────

async def get_current_user(request: Request) -> dict:
    """Extract and validate user from httpOnly JWT cookie or Authorization header."""
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return decode_access_token(token)


def require_role(*allowed_roles: str):
    """Dependency factory: restrict endpoint to specific roles."""
    async def _check(user: dict = Depends(get_current_user)):
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.get('role')}' is not authorized. Required: {allowed_roles}",
            )
        return user
    return _check


def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive fields, showing only the last N characters."""
    if not value or len(value) <= visible_chars:
        return value
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]
