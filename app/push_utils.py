"""Notification broadcast helpers.

Works in two modes:
1) DB broadcast queue – clients poll /api/notifications/latest (works on LAN HTTP)
2) Web Push via pywebpush with real VAPID keys (works on HTTPS even when site is closed)

On Render (HTTPS) real Web Push delivers to phones in background after subscribe.

IMPORTANT: pywebpush's webpush() only accepts:
  - a file path to a PEM key, or
  - a raw base64url / DER string via Vapid.from_string, or
  - a pre-built Vapid instance
Passing a PEM string directly fails with "Could not deserialize key data".
We therefore load the PEM with Vapid.from_pem() and pass the instance.
"""
import json
import logging
import os
import re
from app import db
from app.models import PushSubscription, SiteNotification

logger = logging.getLogger(__name__)

# Real VAPID key pair (can override with env vars on Render)
_DEFAULT_PUBLIC = "BAUxgxcgEWm4-vHiaRuE7fck6PQdkgT6PiBxSWKlpLXeL1BrcCGpQsYjAogiwi9CMECvvgK61cFvGg-8cdRG94w"
_DEFAULT_PRIVATE = """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg4Q2QgA8I/VHeUpcf
RANKSmqLDEYECNj9JU1t8MSBUyOhRANCAAQFMYMXIBFpuPrx4mkbhO33JOj0HZIE
+j4gcUlipaS13i9Qa3AhqULGIwKIIsIvQjBAr74CutXBbxoPvHHURveM
-----END PRIVATE KEY-----"""

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", _DEFAULT_PUBLIC).strip()
_raw_private = os.environ.get("VAPID_PRIVATE_KEY", _DEFAULT_PRIVATE)
VAPID_CLAIMS = {"sub": os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:info@newvisionacademy.edu.np")}


def _normalize_pem(pem: str) -> str:
    """Restore a valid multi-line PEM from env vars that collapsed newlines/spaces."""
    if not pem:
        return ""
    pem = pem.strip().replace("\r\n", "\n").replace("\r", "\n")
    if "BEGIN" in pem and "\n" not in pem:
        # Single-line PEM from env – restore structure carefully
        # Avoid breaking the header/footer labels
        m = re.match(
            r"(-----BEGIN [A-Z0-9 ]+-----)\s*(.+?)\s*(-----END [A-Z0-9 ]+-----)",
            pem,
            re.DOTALL,
        )
        if m:
            header, body, footer = m.group(1), m.group(2), m.group(3)
            # body may have spaces instead of newlines; re-chunk to 64 chars
            body = re.sub(r"\s+", "", body)
            lines = [body[i : i + 64] for i in range(0, len(body), 64)]
            pem = header + "\n" + "\n".join(lines) + "\n" + footer
    return pem.strip()


VAPID_PRIVATE_KEY = _normalize_pem(_raw_private or "")


def _load_vapid_instance():
    """Build a py_vapid.Vapid object from the PEM private key.

    Returns (vapid_instance_or_None, error_message_or_None).
    """
    if not VAPID_PRIVATE_KEY or "BEGIN" not in VAPID_PRIVATE_KEY:
        return None, "VAPID private key missing or invalid (no BEGIN PRIVATE KEY)"
    try:
        from py_vapid import Vapid

        vapid = Vapid.from_pem(VAPID_PRIVATE_KEY.encode("utf-8"))
        return vapid, None
    except Exception as e:
        logger.exception("Failed to load VAPID private key")
        return None, f"VAPID key load failed: {e}"


def get_vapid_public_key():
    return VAPID_PUBLIC_KEY


def send_push_to_all(title, body, url="/"):
    """Save broadcast + send Web Push to all real subscriptions.

    Returns an int subclass with extra attributes:
      .sent, .failed, .total, .web_push_sent, .errors, .dead_removed
    so existing callers that do int(result) still work.
    """
    subs = PushSubscription.query.all()
    sent = 0
    failed = 0
    dead = []
    web_push_sent = 0
    errors = []

    log = SiteNotification(
        title=title or "New Vision Academy",
        body=body or "",
        url=url or "/",
        sent_count=0,
    )
    db.session.add(log)
    db.session.flush()

    has_webpush = False
    webpush_fn = None
    vapid_instance = None

    try:
        from pywebpush import webpush

        webpush_fn = webpush
        vapid_instance, key_err = _load_vapid_instance()
        if vapid_instance is None:
            errors.append(key_err or "VAPID key could not be loaded")
            has_webpush = False
        else:
            has_webpush = True
    except ImportError:
        logger.warning("pywebpush not installed – only polling mode works")
        errors.append("pywebpush not installed on server")

    payload = json.dumps({
        "id": log.id,
        "title": log.title,
        "body": log.body,
        "url": log.url,
    })

    for sub in subs:
        endpoint = (sub.endpoint or "").strip()
        # Soft / polling-only placeholders (no real push endpoint)
        if not endpoint.startswith("https://"):
            sent += 1  # polling clients will pick up via /api/notifications/latest
            continue

        if not has_webpush or not webpush_fn or vapid_instance is None:
            # Still count for polling; real push unavailable
            sent += 1
            continue

        p256dh = (sub.p256dh or "").strip()
        auth = (sub.auth or "").strip()
        if not p256dh or not auth:
            failed += 1
            msg = f"Missing push keys (p256dh/auth) for endpoint {endpoint[:50]}…"
            errors.append(msg)
            logger.warning(msg)
            continue

        try:
            # Pass pre-loaded Vapid instance – NOT the PEM string
            # (PEM string goes through Vapid.from_string which expects raw/DER only)
            webpush_fn(
                subscription_info={
                    "endpoint": endpoint,
                    "keys": {
                        "p256dh": p256dh,
                        "auth": auth,
                    },
                },
                data=payload,
                vapid_private_key=vapid_instance,
                vapid_claims=dict(VAPID_CLAIMS),
                ttl=86400,
            )
            sent += 1
            web_push_sent += 1
        except Exception as e:
            failed += 1
            err_str = str(e)
            logger.warning("Push failed for %s…: %s", endpoint[:50], e)
            errors.append(f"{endpoint[:40]}… → {err_str[:120]}")
            err_l = err_str.lower()
            # Expired / unsubscribed endpoints
            if any(x in err_l for x in ("410", "404", "gone", "unsubscribed", "notfound", "not found")):
                dead.append(sub)

    for s in dead:
        db.session.delete(s)

    log.sent_count = sent
    db.session.commit()
    logger.info(
        "Notification id=%s sent=%s failed=%s web_push=%s dead_removed=%s",
        log.id, sent, failed, web_push_sent, len(dead),
    )

    class _Result(int):
        pass

    result = _Result(sent)
    result.sent = sent
    result.failed = failed
    result.total = len(subs)
    result.web_push_sent = web_push_sent
    result.errors = errors[:5]
    result.dead_removed = len(dead)
    return result
