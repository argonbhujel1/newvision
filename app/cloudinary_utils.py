"""Cloudinary image upload helpers.

Configure via env (recommended on Render):
  CLOUDINARY_CLOUD_NAME=dmmrcq4ro
  CLOUDINARY_API_KEY=...
  CLOUDINARY_API_SECRET=...
  or single: CLOUDINARY_URL=cloudinary://KEY:SECRET@CLOUD_NAME

If Cloudinary is configured, uploads go there and a full HTTPS URL is stored.
Otherwise files are saved under app/static/uploads/ (local / ephemeral on Render).
"""
import os
import uuid
import logging

logger = logging.getLogger(__name__)

# Defaults can be overridden by env — prefer env on production
_DEFAULT_CLOUD = "dmmrcq4ro"
# Prefer env vars. Fallbacks allow local/dev; rotate secret if repo is public.
_DEFAULT_KEY = "617947781794296"
_DEFAULT_SECRET = "cq1MsV1StApAWg6CLzoWad1SecE"


def _parse_cloudinary_url(url: str):
    """Parse cloudinary://api_key:api_secret@cloud_name"""
    if not url or not url.startswith("cloudinary://"):
        return None, None, None
    try:
        rest = url[len("cloudinary://"):]
        creds, cloud = rest.rsplit("@", 1)
        key, secret = creds.split(":", 1)
        return cloud.strip(), key.strip(), secret.strip()
    except Exception:
        return None, None, None


def get_cloudinary_config():
    url = (os.environ.get("CLOUDINARY_URL") or "").strip()
    if url:
        cloud, key, secret = _parse_cloudinary_url(url)
        if cloud and key and secret:
            return cloud, key, secret
    cloud = (os.environ.get("CLOUDINARY_CLOUD_NAME") or _DEFAULT_CLOUD).strip()
    key = (os.environ.get("CLOUDINARY_API_KEY") or _DEFAULT_KEY).strip()
    secret = (os.environ.get("CLOUDINARY_API_SECRET") or _DEFAULT_SECRET).strip()
    if cloud and key and secret:
        return cloud, key, secret
    return None, None, None


def cloudinary_enabled():
    c, k, s = get_cloudinary_config()
    return bool(c and k and s)


def upload_to_cloudinary(file_storage_or_bytes, folder="nva", public_id=None, filename_hint=""):
    """Upload file-like or bytes to Cloudinary. Returns secure_url or None."""
    cloud, key, secret = get_cloudinary_config()
    if not (cloud and key and secret):
        return None
    try:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=cloud,
            api_key=key,
            api_secret=secret,
            secure=True,
        )
        opts = {
            "folder": f"new_vision_academy/{folder}".strip("/"),
            "resource_type": "image",
            "overwrite": False,
            "unique_filename": True,
        }
        if public_id:
            opts["public_id"] = public_id
            opts["unique_filename"] = False
            opts["overwrite"] = True

        # file_storage has .read / .stream or path
        result = cloudinary.uploader.upload(file_storage_or_bytes, **opts)
        url = result.get("secure_url") or result.get("url")
        return url
    except Exception as e:
        logger.exception("Cloudinary upload failed: %s", e)
        return None


def is_remote_url(path):
    if not path:
        return False
    p = str(path).strip().lower()
    return p.startswith("http://") or p.startswith("https://")
