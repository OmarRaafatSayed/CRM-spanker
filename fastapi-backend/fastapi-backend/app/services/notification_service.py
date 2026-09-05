"""
Portal Notification Service
============================
Reusable service that writes rows to public.portal_notifications.

Because portal_notifications is added to the supabase_realtime
publication, every INSERT is pushed to the customer's browser
automatically — no polling needed on the website.

Usage (from any router):
    from app.services.notification_service import notify_customer

    await notify_customer(
        supabase=supabase,
        customer_auth_id="uuid-of-auth.users-row",
        title="تم تحديث حالة طلبك",
        body="حالة طلب التأشيرة تغيرت إلى: قيد المراجعة",
        notif_type="status_update",
        data={"application_id": "...", "new_status": 2},
    )

The function is fire-and-forget: exceptions are logged but never
re-raised so a notification failure never breaks the main action.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Notification type literals ────────────────────────────────────────────────
# Must match the CHECK constraint in portal_notifications.type
STATUS_UPDATE      = "status_update"
DOC_APPROVED       = "document_approved"
DOC_REJECTED       = "document_rejected"
PAYMENT_DUE        = "payment_due"
PAYMENT_CONFIRMED  = "payment_confirmed"
MESSAGE            = "message"
INFO               = "info"

# ── Visa status labels (integer → Arabic label) ───────────────────────────────
VISA_STATUS_AR = {
    1: "تم جمع المستندات",
    2: "قيد المراجعة",
    3: "موعد السفارة",
    4: "مقدّم للقنصلية",
    5: "تمت الموافقة ✅",
    6: "مرفوض ❌",
    7: "ملغي",
}

VISA_STATUS_EN = {
    1: "Documents Collected",
    2: "In Review",
    3: "Embassy Appointment",
    4: "Submitted to Consulate",
    5: "Approved",
    6: "Rejected",
    7: "Cancelled",
}

# ── String status labels (pipeline router uses strings) ───────────────────────
VISA_STATUS_STR_AR = {
    "DOCS_PENDING":          "في انتظار المستندات",
    "UNDER_REVIEW":          "قيد المراجعة",
    "SUBMITTED_TO_EMBASSY":  "مقدّم للقنصلية",
    "APPROVED":              "تمت الموافقة ✅",
    "REJECTED":              "مرفوض ❌",
}

QUOTATION_STATUS_AR = {
    "DRAFT":    "مسودة",
    "SENT":     "تم الإرسال",
    "ACCEPTED": "مقبول ✅",
    "EXPIRED":  "منتهي الصلاحية",
    "REJECTED": "مرفوض",
}

BOOKING_STATUS_AR = {
    "PENDING_PAYMENT": "في انتظار الدفع",
    "CONFIRMED":       "مؤكد ✅",
    "CANCELLED":       "ملغي",
    "COMPLETED":       "مكتمل ✅",
}


# ─── Core send function ───────────────────────────────────────────────────────

async def notify_customer(
    supabase: Any,
    customer_auth_id: str,
    title: str,
    body: str,
    notif_type: str = INFO,
    data: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Insert one notification row for a customer.

    Parameters
    ----------
    supabase          : Supabase service-role client
    customer_auth_id  : auth.users.id of the target customer
    title             : Short heading shown in the notification bell
    body              : Full message body
    notif_type        : One of the TYPE_* constants above
    data              : Optional JSONB payload (deep-link data for the website)

    Returns True on success, False if the insert failed (never raises).
    """
    try:
        row: Dict[str, Any] = {
            "customer_id": customer_auth_id,
            "title":       title,
            "body":        body,
            "type":        notif_type,
            "is_read":     False,
            "created_at":  datetime.now(timezone.utc).isoformat(),
        }
        if data:
            row["data"] = data

        supabase.table("portal_notifications").insert(row).execute()
        logger.info(
            f"[notify] ✅ sent '{notif_type}' to customer {customer_auth_id[:8]}… | {title}"
        )
        return True

    except Exception as exc:
        # Never let a notification failure crash the main business action
        logger.warning(
            f"[notify] ⚠️  Failed to send notification to {customer_auth_id[:8]}…: {exc}"
        )
        return False


# ─── Customer lookup helpers ──────────────────────────────────────────────────

def get_customer_auth_id_from_profile(
    supabase: Any,
    profile_id: str,
) -> Optional[str]:
    """
    Resolve profiles.id → auth.users.id (profiles.user_id).
    Used when we have the CRM profile UUID and need the portal customer UUID.
    """
    try:
        r = (
            supabase.table("profiles")
            .select("user_id")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        return r.data[0]["user_id"] if r.data else None
    except Exception as exc:
        logger.warning(f"[notify] Profile→auth lookup failed for {profile_id}: {exc}")
        return None


def get_customer_auth_id_from_users_row(
    supabase: Any,
    crm_user_id: str,
) -> Optional[str]:
    """
    Resolve users.id (CRM table) → auth.users.id via users.auth_user_id.
    Used by crm_customers.py and crm_pipeline.py where entities carry user_id
    that points to the CRM 'users' table (not directly to auth.users).
    """
    try:
        r = (
            supabase.table("users")
            .select("auth_user_id")
            .eq("id", crm_user_id)
            .limit(1)
            .execute()
        )
        return r.data[0]["auth_user_id"] if r.data else None
    except Exception as exc:
        logger.warning(f"[notify] CRM users→auth lookup failed for {crm_user_id}: {exc}")
        return None


# ─── Pre-built notification factories ────────────────────────────────────────
# Each factory returns the kwargs dict so callers just do:
#   await notify_customer(supabase, auth_id, **visa_status_changed(app_id, 2))

def visa_status_changed(application_id: str, new_status: int) -> Dict[str, Any]:
    """Notification when CRM changes visa application status (int 1-7)."""
    label_ar = VISA_STATUS_AR.get(new_status, str(new_status))
    label_en = VISA_STATUS_EN.get(new_status, str(new_status))

    notif_type = STATUS_UPDATE
    if new_status == 5:
        notif_type = DOC_APPROVED   # re-use approved type for visa approval
    elif new_status == 6:
        notif_type = DOC_REJECTED

    return dict(
        title=f"تحديث على طلب التأشيرة",
        body=f"تم تحديث حالة طلبك إلى: {label_ar}",
        notif_type=notif_type,
        data={
            "application_id": application_id,
            "new_status":     new_status,
            "status_label_ar": label_ar,
            "status_label_en": label_en,
        },
    )


def visa_status_str_changed(application_id: str, new_status: str) -> Dict[str, Any]:
    """Notification when pipeline router changes visa status (string variant)."""
    label_ar = VISA_STATUS_STR_AR.get(new_status, new_status)

    notif_type = STATUS_UPDATE
    if new_status == "APPROVED":
        notif_type = DOC_APPROVED
    elif new_status == "REJECTED":
        notif_type = DOC_REJECTED

    return dict(
        title="تحديث على طلب التأشيرة",
        body=f"تم تحديث حالة طلبك إلى: {label_ar}",
        notif_type=notif_type,
        data={
            "application_id": application_id,
            "new_status":     new_status,
            "status_label_ar": label_ar,
        },
    )


def quotation_sent(quotation_id: str, total_amount: float, currency: str = "EGP") -> Dict[str, Any]:
    """Notification when CRM sends a price quotation to the customer."""
    return dict(
        title="عرض سعر جديد",
        body=f"تم إرسال عرض سعر بقيمة {total_amount:,.0f} {currency}. راجعه وقبله من حسابك.",
        notif_type=STATUS_UPDATE,
        data={
            "quotation_id":  quotation_id,
            "total_amount":  total_amount,
            "currency":      currency,
            "action":        "review_quotation",
        },
    )


def quotation_status_changed(quotation_id: str, new_status: str) -> Dict[str, Any]:
    """Notification for any quotation status change."""
    label_ar = QUOTATION_STATUS_AR.get(new_status, new_status)
    return dict(
        title="تحديث على عرض السعر",
        body=f"حالة عرض السعر تغيرت إلى: {label_ar}",
        notif_type=STATUS_UPDATE,
        data={"quotation_id": quotation_id, "new_status": new_status, "label_ar": label_ar},
    )


def booking_confirmed(booking_id: str, booking_reference: str) -> Dict[str, Any]:
    """Notification when a booking is confirmed after full payment."""
    return dict(
        title="تم تأكيد حجزك ✅",
        body=f"حجزك برقم {booking_reference} تم تأكيده. يمكنك تحميل الفاوتشر من حسابك.",
        notif_type=PAYMENT_CONFIRMED,
        data={"booking_id": booking_id, "booking_reference": booking_reference},
    )


def booking_status_changed(booking_id: str, new_status: str) -> Dict[str, Any]:
    """Notification for any booking status change."""
    label_ar = BOOKING_STATUS_AR.get(new_status, new_status)
    notif_type = PAYMENT_CONFIRMED if new_status == "CONFIRMED" else STATUS_UPDATE
    return dict(
        title="تحديث على حجزك",
        body=f"حالة حجزك تغيرت إلى: {label_ar}",
        notif_type=notif_type,
        data={"booking_id": booking_id, "new_status": new_status, "label_ar": label_ar},
    )


def payment_received(booking_id: str, amount_paid: float, remaining: float, currency: str = "EGP") -> Dict[str, Any]:
    """Notification when a payment is recorded."""
    if remaining <= 0:
        body = f"تم استلام دفعة {amount_paid:,.0f} {currency}. تم سداد المبلغ كاملاً ✅"
        notif_type = PAYMENT_CONFIRMED
    else:
        body = f"تم استلام دفعة {amount_paid:,.0f} {currency}. المتبقي: {remaining:,.0f} {currency}"
        notif_type = STATUS_UPDATE
    return dict(
        title="تم استلام دفعتك",
        body=body,
        notif_type=notif_type,
        data={
            "booking_id":   booking_id,
            "amount_paid":  amount_paid,
            "remaining":    remaining,
            "currency":     currency,
        },
    )


def document_reviewed(doc_id: str, doc_type: str, new_status: str, staff_notes: Optional[str] = None) -> Dict[str, Any]:
    """Notification when CRM reviews a portal document."""
    if new_status == "approved":
        title = f"تم قبول مستندك ✅"
        body  = f"تم قبول مستند ({doc_type}) بنجاح."
        notif_type = DOC_APPROVED
    else:
        title = f"تم رفض مستندك ❌"
        body  = f"تم رفض مستند ({doc_type})."
        if staff_notes:
            body += f" السبب: {staff_notes}"
        notif_type = DOC_REJECTED

    return dict(
        title=title,
        body=body,
        notif_type=notif_type,
        data={
            "document_id": doc_id,
            "doc_type":    doc_type,
            "new_status":  new_status,
            "staff_notes": staff_notes,
        },
    )
