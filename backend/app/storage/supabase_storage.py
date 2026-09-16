"""Supabase Storage service — handles object upload, signed URL generation, and cleanup."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger("lmcs.storage")


def is_supabase_configured(settings: Settings) -> bool:
    """Returns True if Supabase URL and service role key are populated."""
    return bool(settings.supabase_url.strip() and settings.supabase_service_role_key.strip())


async def upload_scan_image(
    *,
    scan_id: str,
    image_id: str,
    raw_bytes: bytes,
    content_type: str,
    extension: str,
    settings: Settings,
) -> dict[str, Any]:
    """Uploads scan image to Supabase Storage, with fallback to local storage if not configured."""
    storage_path = f"scans/{scan_id}/{image_id}.{extension}"
    bucket = settings.supabase_bucket or "lmcs-images"

    # Always cache locally to captures/ directory for instant rendering, offline access & PDF generation
    local_path = Path("captures") / scan_id / f"{image_id}.{extension}"
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(raw_bytes)
    except Exception as exc:
        logger.warning("Local capture write failed: %s", exc)

    if is_supabase_configured(settings):
        base_url = settings.supabase_url.rstrip("/")
        url = f"{base_url}/storage/v1/object/{bucket}/{storage_path}"
        headers = {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
            "Content-Type": content_type or "image/jpeg",
            "x-upsert": "true",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, content=raw_bytes)
                if res.status_code in (200, 201):
                    logger.info("Successfully uploaded %s to Supabase bucket %s", storage_path, bucket)
                    return {
                        "provider": "supabase",
                        "bucket": bucket,
                        "storage_path": storage_path,
                        "mime_type": content_type,
                        "file_size": len(raw_bytes),
                    }
                else:
                    logger.error(
                        "Supabase storage upload failed (%d): %s. Using local copy.",
                        res.status_code,
                        res.text,
                    )
        except Exception as exc:
            logger.warning("Supabase storage exception: %s. Using local copy.", exc)

    # Local return if Supabase not configured or upload failed
    return {
        "provider": "local",
        "bucket": "local",
        "storage_path": str(local_path).replace("\\", "/"),
        "mime_type": content_type,
        "file_size": len(raw_bytes),
    }


async def download_scan_image(
    *,
    bucket: str,
    storage_path: str,
    settings: Settings,
) -> tuple[bytes, str] | None:
    """Downloads an object from Supabase Storage using service role credentials.
    Returns (raw_bytes, content_type) or None.
    """
    if not is_supabase_configured(settings):
        return None

    base_url = settings.supabase_url.rstrip("/")
    clean_path = storage_path.lstrip("/")
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }

    endpoints = [
        f"{base_url}/storage/v1/object/authenticated/{bucket}/{clean_path}",
        f"{base_url}/storage/v1/object/{bucket}/{clean_path}",
        f"{base_url}/storage/v1/object/public/{bucket}/{clean_path}",
    ]

    for url in endpoints:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200 and res.content:
                    content_type = res.headers.get("content-type", "image/jpeg")
                    return res.content, content_type
        except Exception as exc:
            logger.warning("Error fetching from %s: %s", url, exc)

    # If direct file fetch did not return 200, search prefix in bucket
    try:
        prefix = clean_path.rsplit("/", 1)[0] if "/" in clean_path else clean_path
        list_url = f"{base_url}/storage/v1/object/list/{bucket}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            list_res = await client.post(list_url, headers=headers, json={"prefix": prefix, "limit": 10})
            if list_res.status_code == 200:
                files = list_res.json()
                for item in files:
                    name = item.get("name")
                    if name and not name.startswith("."):
                        found_path = f"{prefix}/{name}"
                        for sub_url in [
                            f"{base_url}/storage/v1/object/authenticated/{bucket}/{found_path}",
                            f"{base_url}/storage/v1/object/{bucket}/{found_path}",
                            f"{base_url}/storage/v1/object/public/{bucket}/{found_path}",
                        ]:
                            f_res = await client.get(sub_url, headers=headers)
                            if f_res.status_code == 200 and f_res.content:
                                return f_res.content, f_res.headers.get("content-type", "image/jpeg")
    except Exception as exc:
        logger.warning("Error listing files in prefix for %s: %s", clean_path, exc)

    return None


async def create_signed_url(
    *,
    storage_provider: str,
    bucket: str,
    storage_path: str,
    settings: Settings,
    expires_in: int | None = None,
) -> str | None:
    """Generates a temporary viewing URL for a private inspection evidence image."""
    ttl = expires_in or settings.supabase_signed_url_ttl or 300

    if storage_provider == "supabase" and is_supabase_configured(settings):
        base_url = settings.supabase_url.rstrip("/")
        clean_path = storage_path.lstrip("/")
        url = f"{base_url}/storage/v1/object/sign/{bucket}/{clean_path}"
        headers = {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
            "Content-Type": "application/json",
        }
        payload = {"expiresIn": ttl}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    signed_path = data.get("signedURL") or data.get("signedUrl")
                    if signed_path:
                        if signed_path.startswith("http://") or signed_path.startswith("https://"):
                            return signed_path
                        # Supabase storage requires /storage/v1 prefix on API gateway
                        if not signed_path.startswith("/storage/v1"):
                            clean_sub = signed_path if signed_path.startswith("/") else f"/{signed_path}"
                            signed_path = f"/storage/v1{clean_sub}"
                        return f"{base_url}{signed_path}"
                logger.warning(
                    "Supabase sign returned %d: %s. Using public object URL.",
                    res.status_code,
                    res.text,
                )
        except Exception as exc:
            logger.warning("Supabase sign exception for %s: %s", storage_path, exc)

        # Supabase fallback: return local /scans proxy endpoint so backend can stream it with service_role_key
        return f"/scans/{clean_path}"

    # Local file fallback — return relative static mount URL
    if storage_path.startswith("captures/") or storage_path.startswith("scans/"):
        return f"/{storage_path.lstrip('/')}"
    return f"/captures/{storage_path.lstrip('/')}"


async def delete_scan_images(
    items: list[tuple[str, str, str]],  # (provider, bucket, storage_path)
    settings: Settings,
) -> None:
    """Rollback cleanup of uploaded objects if submission transaction fails."""
    supabase_prefixes: list[str] = []
    bucket = settings.supabase_bucket or "lmcs-images"

    for provider, bkt, path in items:
        if provider == "supabase":
            supabase_prefixes.append(path)
        elif provider == "local":
            try:
                p = Path(path)
                if p.exists():
                    p.unlink()
            except Exception:
                pass

    if supabase_prefixes and is_supabase_configured(settings):
        base_url = settings.supabase_url.rstrip("/")
        url = f"{base_url}/storage/v1/object/{bucket}"
        headers = {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.request("DELETE", url, headers=headers, json={"prefixes": supabase_prefixes})
        except Exception as exc:
            logger.warning("Supabase cleanup error: %s", exc)
