"""
Webhook Sender Service
=======================
Sends HMAC-SHA256-signed POST requests to the customer-facing website
(spanker) whenever the CRM changes a status.

The website's /api/webhooks/crm endpoint validates the signature and
writes into portal_notifications + travel_requests automatically.

Architecture
------------
  CRM status change (any router)
        ↓
  send_crm_webhook()   ← this file
        ↓  HTTP POST with x-crm-signature header
  spanker /api/webhooks/crm
        ↓
  processCrmWebhook()  (crm-adapter.ts)
        ↓
  portal_notifications INSERT → Supabase Realtime → customer browser

Configuration (all optional — webhook is skipped when URL is absent)
----------------------------------------------------------------------
  PORTAL_WEBHOOK_URL     Full URL of the website webhook endpoint
                         e.g. https://yourdomain.com/api/webhooks/crm
                              http://localhost:3000/api/webhooks/crm (dev)

  PORTAL_WEBHOOK_SECRET  HMAC-SHA256 secret — must match CRM_WEBHOOK_SECRET
                         in the website's .env.local
                         Generate: python -c "import secrets; print(secrets.token_hex(32))"

  PORTAL_WEBHOOK_TIMEOUT Request timeout in seconds (default: 5)

Fire-and-forget contract
------------------------
  send_crm_webhook() NEVER raises. A failed delivery is logged at WARNING
  level but does NOT prevent the CRM action from completing.
  The website also handles duplicate tracking_ids gracefully.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
_WEBHOOK_URL:     str = os.getenv("PORTAL_WEBHOOK_URL",     "").rstrip("/")
_WEBHOOK_SECRET:  str = os.getenv("PORTAL_WEBHOOK_SECRET",  "")
_WEBHOOK_TIMEOUT: int = int(os.getenv("PORTAL_WEBHOOK_TIMEOUT", "5"))

# ── CRM int status → website PortalStatus string map ─────────────────────────
# Mirrors the PORTAL_TO_CRM_MAP in visa-states.ts (spanker)
_CRM_INT_TO_PORTAL: Dict[int, str] = {
    1: "pending_documents",
    2: "documents_review",
    3: "in_progress",
    4: "in_progress",
    5: "completed",
    6: "cancelled",
    7: "cancelled",
}

# String aliases used by crm_customers.py / crm_pipeline.py → PortalStatus
_CRM_STR_TO_PORTAL: Dict[str, str] = {
    "DOCS_PENDING":          "pending_documents",
    "UNDER_REVIEW":          "documents_review",
    "SUBMITTED_TO_EMBASSY":  "in_progress",
    "APPROVED":              "completed",
    "REJECTED":              "cancelled",
    # pipeline string statuses
    "pending_documents":     "pending_documents",
    "documents_review":      "documents_review",
    "docs_approved":         "docs_approved",
    "in_progress":           "in_progress",
    "completed":             "completed",
    "cancelled":             "cancelled",
}

# Human-readable Arabic labels for the staff_message field
_PORTAL_STATUS_AR: Dict[str, str] = {
    "pending_documents": "في انتظار المستندات",
    "documents_review":  "قيد مراجعة المستندات",
    "docs_approved":     "تم قبول المستندات",
    "in_progress":       "قيد التنفيذ",
    "completed":         "مكتمل ✅",
    "cancelled":         "ملغي",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_status(raw: Any) -> str:
    """Convert CRM int (1-7) or string slug to a PortalStatus string."""
    if isinstance(raw, int):
        return _CRM_INT_TO_PORTAL.get(raw, "pending_documents")
    if isinstance(raw, str):
        return _CRM_STR_TO_PORTAL.get(raw, raw)
    return "pending_documents"


def _sign(body: str) -> str:
    """Return sha256=<hex> HMAC signature for the given body."""
    mac = hmac.new(
        _WEBHOOK_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    )
    return f"sha256={mac.hexdigest()}"


def _build_payload(
    tracking_id:      str,
    raw_status:       Any,
    staff_message:    str,
    staff_id:         Optional[str]       = None,
    document_updates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build the CRMStatusUpdate payload the website expects."""
    portal_status = _normalize_status(raw_status)
    label_ar      = _PORTAL_STATUS_AR.get(portal_status, portal_status)

    payload: Dict[str, Any] = {
        "tracking_id": tracking_id,
        "status":      portal_status,
        "message":     staff_message or f"تم تحديث حالة طلبك إلى: {label_ar}",
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    }
    if staff_id:
        payload["staff_id"] = staff_id
    if document_updates:
        payload["document_updates"] = document_updates

    return payload


# ─── Public API ───────────────────────────────────────────────────────────────

def send_crm_webhook(
    tracking_id:      str,
    raw_status:       Any,
    staff_message:    str          = "",
    staff_id:         Optional[str] = None,
    document_updates: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Fire-and-forget: POST a signed status-update webhook to the customer portal.

    Parameters
    ----------
    tracking_id      : travel_requests.id (or visa_applications.id when linked)
    raw_status       : CRM int 1-7 OR PortalStatus string slug OR CRM string alias
    staff_message    : Human-readable Arabic update shown to the customer
    staff_id         : auth.users.id of the acting staff member (optional)
    document_updates : List of {"type": <doc_type>, "status": <doc_status>} dicts

    Never raises — all exceptions are swallowed and logged.
    """
    if not _WEBHOOK_URL:
        # Webhook not configured — skip silently in dev / staging
        logger.debug(
            "[webhook_sender] PORTAL_WEBHOOK_URL not set — skipping webhook for %s",
            tracking_id[:8],
        )
        return

    payload = _build_payload(
        tracking_id, raw_status, staff_message, staff_id, document_updates
    )
    body    = json.dumps(payload, ensure_ascii=False)

    headers: Dict[str, str] = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent":   "CRM-Spanker/1.0",
    }

    if _WEBHOOK_SECRET:
        headers["x-crm-signature"] = _sign(body)
    else:
        logger.warning(
            "[webhook_sender] PORTAL_WEBHOOK_SECRET not set — sending unsigned webhook"
        )

    try:
        req = urllib.request.Request(
            _WEBHOOK_URL,
            data=body.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_WEBHOOK_TIMEOUT) as resp:
            status_code = resp.status
            if status_code == 200:
                logger.info(
                    "[webhook_sender] ✅ Sent webhook for %s → %s (HTTP %d)",
                    tracking_id[:8], payload["status"], status_code,
                )
            else:
                logger.warning(
                    "[webhook_sender] ⚠️  Unexpected HTTP %d for tracking_id=%s",
                    status_code, tracking_id[:8],
                )

    except urllib.error.HTTPError as exc:
        logger.warning(
            "[webhook_sender] ⚠️  HTTP %d from portal webhook (tracking_id=%s): %s",
            exc.code, tracking_id[:8], exc.reason,
        )
    except urllib.error.URLError as exc:
        logger.warning(
            "[webhook_sender] ⚠️  Cannot reach portal webhook (tracking_id=%s): %s",
            tracking_id[:8], exc.reason,
        )
    except Exception as exc:   # pragma: no cover
        logger.warning(
            "[webhook_sender] ⚠️  Unexpected error sending webhook (tracking_id=%s): %s",
            tracking_id[:8], exc,
        )
