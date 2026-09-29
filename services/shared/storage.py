"""
LoanFlow – Supabase Storage client for document uploads.
Uses Supabase Storage (S3-compatible) with signed URLs.
"""
from supabase import create_client, Client
from .config import get_settings

settings = get_settings()

_supabase: Client | None = None


def get_supabase_client() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
    return _supabase


def upload_file(bucket: str, path: str, file_data: bytes, content_type: str = "application/octet-stream"):
    """Upload a file to Supabase Storage."""
    client = get_supabase_client()
    return client.storage.from_(bucket).upload(
        path,
        file_data,
        {"content-type": content_type},
    )


def get_signed_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    """Generate a signed download URL (default 1 hour)."""
    client = get_supabase_client()
    result = client.storage.from_(bucket).create_signed_url(path, expires_in)
    return result.get("signedURL", "")


def get_upload_signed_url(bucket: str, path: str) -> str:
    """Generate a signed upload URL for browser direct upload."""
    client = get_supabase_client()
    result = client.storage.from_(bucket).create_signed_upload_url(path)
    return result.get("signedURL", result.get("signed_url", ""))


def delete_file(bucket: str, paths: list[str]):
    """Delete files from Supabase Storage."""
    client = get_supabase_client()
    return client.storage.from_(bucket).remove(paths)
