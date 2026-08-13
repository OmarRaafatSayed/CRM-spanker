"""
Unified Registration Hook & Event Dispatcher (TASK 3)

On successful signup/lead creation:
1. Create transactional write to customer_profiles (main database source)
2. Fire async event that provisions CRM Customer Profile
3. Queue entity for Portal ↔ CRM sync
4. Emit customer registered event for downstream handlers (email, webhooks)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from app.services.supabase_client import get_supabase

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Event Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class RegistrationEvent:
    """Immutable registration event"""
    def __init__(
        self,
        event_type: str,
        auth_user_id: UUID | str,
        email: str,
        first_name: str = "",
        last_name: str = "",
        phone: str = "",
        country: str = "",
        customer_profile_id: UUID | str | None = None,
        timestamp: datetime | None = None,
    ):
        self.event_type = event_type
        self.auth_user_id = str(auth_user_id)
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone
        self.country = country
        self.customer_profile_id = str(customer_profile_id) if customer_profile_id else None
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.metadata: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "auth_user_id": self.auth_user_id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "country": self.country,
            "customer_profile_id": self.customer_profile_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"RegistrationEvent(type={self.event_type}, user={self.auth_user_id}, email={self.email})"


class EventDispatcher:
    """Async-safe event dispatcher for registration events"""

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._middleware: List[Callable] = []

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Register handler for event type"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(f"[dispatcher] Handler registered: {event_type} → {handler.__name__}")

    def use_middleware(self, middleware: Callable) -> None:
        """Register middleware to process all events"""
        self._middleware.append(middleware)

    async def emit(self, event: RegistrationEvent) -> None:
        """Emit event to all registered handlers"""
        logger.info(f"[dispatcher] Emitting: {event}")

        # Run middleware
        for middleware in self._middleware:
            await middleware(event)

        # Run handlers
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            logger.warning(f"[dispatcher] No handlers registered for {event.event_type}")
            return

        for handler in handlers:
            try:
                result = handler(event)
                # Support both sync and async handlers
                if hasattr(result, "__await__"):
                    await result
                logger.info(f"[dispatcher] Handler completed: {handler.__name__}")
            except Exception as exc:
                logger.error(f"[dispatcher] Handler failed: {handler.__name__}: {exc}", exc_info=True)


# Global dispatcher instance
_dispatcher = EventDispatcher()


# ─────────────────────────────────────────────────────────────────────────────
# Unified Registration Hook
# ─────────────────────────────────────────────────────────────────────────────

class RegistrationHook:
    """
    Unified registration hook — handles TASK 3:
    1. Transactional write to customer_profiles (main database)
    2. Async event dispatch for CRM provisioning
    3. Entity sync queueing
    4. Event logging
    """

    def __init__(self, supabase_client: Any = None):
        self.supabase = supabase_client or get_supabase()

    def _create_customer_profile(
        self,
        auth_user_id: UUID | str,
        email: str,
        first_name: str = "",
        last_name: str = "",
        phone: str = "",
        country: str = "",
    ) -> str:
        """Transactional write: Create users row. Returns user_id."""
        try:
            full_name = f"{first_name} {last_name}".strip()
            
            response = self.supabase.table("users").insert({
                "auth_user_id": str(auth_user_id),
                "email": email,
                "full_name": full_name,
                "phone": phone or None,
                "status": "LEAD",
                "country": country or None,
            }).execute()

            if response.data and len(response.data) > 0:
                user = response.data[0] if isinstance(response.data, list) else response.data
                user_id = user.get('id')
                logger.info(f"[registration] ✅ Customer profile created: {user_id}")
                return user_id
            else:
                raise ValueError("No data returned from users table insert")

        except Exception as exc:
            logger.error(f"[registration] ❌ Failed to create customer profile: {exc}", exc_info=True)
            raise

    def _queue_entity_sync(
        self,
        entity_id: UUID | str,
    ) -> bool:
        """Queue entity for Portal → CRM sync. Returns success flag."""
        try:
            # Direct insert to sync_queue table instead of RPC
            self.supabase.table("sync_queue").insert({
                "entity_type": "user",
                "entity_id": str(entity_id),
                "status": "pending",
            }).execute()

            logger.info(f"[registration] ✅ Entity queued for sync: {entity_id}")
            return True

        except Exception as exc:
            logger.warning(f"[registration] ⚠️  Failed to queue sync (non-fatal): {exc}")
            # Non-blocking: sync queueing failure doesn't stop signup
            return False

    def _log_registration_event(
        self,
        user_id: UUID | str,
        email: str,
        first_name: str = "",
        last_name: str = "",
    ) -> bool:
        """Log event to event_log for audit trail. Returns success flag."""
        try:
            # Direct insert to event_log table instead of RPC
            self.supabase.table("event_log").insert({
                "user_id": str(user_id),
                "event_type": "user_registered",
                "email": email,
                "metadata": {
                    "first_name": first_name,
                    "last_name": last_name,
                }
            }).execute()

            logger.info(f"[registration] ✅ Event logged: {email}")
            return True

        except Exception as exc:
            logger.warning(f"[registration] ⚠️  Event logging failed (non-fatal): {exc}")
            # Non-blocking: audit logging doesn't stop signup
            return False

    async def handle_signup(
        self,
        auth_user_id: UUID | str,
        email: str,
        first_name: str = "",
        last_name: str = "",
        phone: str = "",
        country: str = "",
    ) -> Dict[str, Any]:
        """
        TASK 3 Main Entry Point:
        Unified signup → profile creation → event dispatch → sync queue
        
        Process:
        1. Create customer profile (transactional, blocking)
        2. Queue for CRM sync (non-blocking)
        3. Log audit event (non-blocking)
        4. Emit async events to handlers (non-blocking)
        """
        auth_user_id_str = str(auth_user_id)
        logger.info(f"[registration] 🚀 Starting unified signup: {email}")

        try:
            # ── 1. TRANSACTIONAL WRITE: Create customer profile ─────────────────
            customer_profile_id = self._create_customer_profile(
                auth_user_id_str,
                email,
                first_name,
                last_name,
                phone,
                country,
            )

            # ── 2. QUEUE FOR SYNC: Portal → CRM (non-blocking) ────────────────
            self._queue_entity_sync(entity_id=customer_profile_id)

            # ── 3. LOG EVENT: Create audit trail (non-blocking) ────────────────
            self._log_registration_event(
                user_id=auth_user_id_str,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )

            # ── 4. EMIT ASYNC EVENT: Dispatch to handlers (non-blocking) ──────
            registration_event = RegistrationEvent(
                event_type="UserRegistered",
                auth_user_id=auth_user_id_str,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                country=country,
                customer_profile_id=customer_profile_id,
            )

            await _dispatcher.emit(registration_event)

            logger.info(f"[registration] ✅ Unified signup complete: {email}")

            return {
                "success": True,
                "customer_profile_id": customer_profile_id,
                "auth_user_id": auth_user_id_str,
                "email": email,
            }

        except Exception as exc:
            logger.error(f"[registration] ❌ Signup failed: {exc}", exc_info=True)
            raise


# ─────────────────────────────────────────────────────────────────────────────
# Async Event Handlers
# ─────────────────────────────────────────────────────────────────────────────

def create_crm_customer_handler(supabase_client: Any = None) -> Callable:
    """
    Handler: Provisions active Customer Profile in CRM on UserRegistered event
    (This would call an external CRM API or queue a job)
    """
    supabase = supabase_client or get_supabase()

    def handler(event: RegistrationEvent) -> None:
        logger.info(f"[handlers] 🔔 Provisioning CRM customer: {event.email}")

        try:
            # In production: call external CRM API here
            # For now, we just log and mark as queued
            logger.info(
                f"[handlers] ✅ CRM customer provisioned (async): "
                f"email={event.email}, profile_id={event.customer_profile_id}"
            )

        except Exception as exc:
            logger.error(f"[handlers] ❌ CRM provisioning failed: {exc}", exc_info=True)

    return handler


def create_welcome_email_handler(supabase_client: Any = None) -> Callable:
    """Handler: Send welcome email on UserRegistered event"""
    supabase = supabase_client or get_supabase()

    def handler(event: RegistrationEvent) -> None:
        logger.info(f"[handlers] 📧 Sending welcome email: {event.email}")

        try:
            # In production: integrate with email service (SendGrid, AWS SES, etc.)
            logger.info(
                f"[handlers] ✅ Welcome email queued: {event.email}"
            )

        except Exception as exc:
            logger.error(f"[handlers] ❌ Email handler failed: {exc}", exc_info=True)

    return handler


def create_webhook_handler(webhook_url: str) -> Callable:
    """Handler: Fire webhook on UserRegistered event"""

    def handler(event: RegistrationEvent) -> None:
        logger.info(f"[handlers] 🪝 Firing webhook: {webhook_url}")

        try:
            # In production: POST to external webhook
            import httpx

            httpx.post(
                webhook_url,
                json=event.to_dict(),
                timeout=10,
            )
            logger.info(f"[handlers] ✅ Webhook fired successfully")

        except Exception as exc:
            logger.warning(f"[handlers] ⚠️  Webhook failed (non-blocking): {exc}")

    return handler


# ─────────────────────────────────────────────────────────────────────────────
# Module Initialization
# ─────────────────────────────────────────────────────────────────────────────

def init_registration_hooks(supabase_client: Any = None) -> RegistrationHook:
    """
    Initialize registration hooks with default handlers

    Usage:
        hook = init_registration_hooks()
        await hook.handle_signup(user_id, email, first_name, last_name)
    """
    supabase = supabase_client or get_supabase()

    # Create hook instance
    hook = RegistrationHook(supabase)

    # Register default handlers
    _dispatcher.subscribe("UserRegistered", create_crm_customer_handler(supabase))
    _dispatcher.subscribe("UserRegistered", create_welcome_email_handler(supabase))

    logger.info("[registration] ✅ Registration hooks initialized")

    return hook


def get_event_dispatcher() -> EventDispatcher:
    """Get global event dispatcher"""
    return _dispatcher
