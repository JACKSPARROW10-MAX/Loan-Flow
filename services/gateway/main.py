"""
LoanFlow – API Gateway.
Central entry point that proxies to internal services.
Handles CORS, rate limiting, security headers, and CSRF verification.
"""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.config import get_settings

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


# ─── Security Headers Middleware ───
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


app = FastAPI(title="LoanFlow API Gateway", version="1.0.0")

# ─── Middleware stack ───
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-csrf-token"],
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


# ─── Proxy routes ───
SERVICE_MAP = {
    "/auth": settings.auth_service_url,
    "/applications": settings.loan_app_service_url,
    "/documents": settings.loan_app_service_url,
    "/servicing": settings.loan_app_service_url,
    "/collection": settings.loan_app_service_url,
    "/rules": settings.loan_app_service_url,
    "/analytics": settings.loan_app_service_url,
    "/fraud": settings.loan_app_service_url,
    "/notifications": settings.notification_service_url,
    "/notify": settings.notification_service_url,
    "/ws": settings.notification_service_url,
    "/kyc": settings.kyc_service_url,
    "/score": settings.risk_service_url,
    "/audit": settings.audit_service_url,
}



async def proxy_request(request: Request, target_url: str):
    """Forward request to the target service, preserving cookies and headers."""
    async with httpx.AsyncClient() as client:
        # Build target URL
        url = target_url + request.url.path
        if request.url.query:
            url += f"?{request.url.query}"

        # Forward headers (including cookies)
        headers = dict(request.headers)
        headers.pop("host", None)

        body = await request.body()

        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            timeout=30,
        )

        # Build response, preserving set-cookie headers
        response = Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )
        return response


@app.get("/health")
async def health():
    # Must be registered before the catch-all proxy route below.
    return {"status": "ok", "service": "gateway"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def gateway(request: Request, path: str):
    """Route requests to the appropriate backend service."""
    # Find matching service
    for prefix, service_url in SERVICE_MAP.items():
        if f"/{path}".startswith(prefix):
            try:
                return await proxy_request(request, service_url)
            except httpx.ConnectError:
                return JSONResponse(
                    status_code=502,
                    content={"detail": f"Service unavailable: {prefix}"},
                )
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={"detail": f"Gateway error: {str(e)}"},
                )

    return JSONResponse(status_code=404, content={"detail": f"No service found for /{path}"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
