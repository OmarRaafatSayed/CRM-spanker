"""
Webhook Delivery Worker

Async background worker that delivers queued webhook events to external systems.
Handles:
- Polling webhook_queue for pending deliveries
- Filtering by active subscriptions
- HTTP POST delivery with retries
- Exponential backoff on failures
- Statistics tracking
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class WebhookDeliveryWorker:
    """
    Webhook Event Delivery Worker
    Delivers queued webhook events to subscribed external endpoints
    """

    def __init__(
        self,
        supabase_client: Any,
        poll_interval_seconds: int = 10,
        max_workers: int = 10,
        delivery_timeout_seconds: int = 30,
    ):
        self.supabase = supabase_client
        self.poll_interval = poll_interval_seconds
        self.max_workers = max_workers
        self.delivery_timeout = delivery_timeout_seconds
        self.running = False

    async def start(self) -> None:
        """Start webhook delivery worker (runs forever until stop() is called)"""
        self.running = True
        logger.info("[webhook] 🚀 Webhook Delivery Worker started")

        try:
            while self.running:
                await self._process_batch()
                await asyncio.sleep(self.poll_interval)
        except Exception as exc:
            logger.error(f"[webhook] ❌ Worker crashed: {exc}", exc_info=True)
        finally:
            self.running = False
            logger.info("[webhook] 🛑 Webhook Delivery Worker stopped")

    def stop(self) -> None:
        """Stop webhook delivery worker"""
        self.running = False

    async def _process_batch(self) -> None:
        """Process next batch of pending webhooks"""
        try:
            # Get pending webhooks
            pending = await self._get_pending_webhooks()
            if not pending:
                return

            logger.info(f"[webhook] 📨 Processing {len(pending)} pending webhook events")

            # Group by webhook_id for efficient delivery
            webhooks_by_id = {}
            for webhook in pending:
                webhook_id = webhook.get("webhook_id")
                if webhook_id not in webhooks_by_id:
                    webhooks_by_id[webhook_id] = webhook

            # Deliver up to max_workers at a time
            tasks = [
                self._deliver_webhook(webhook)
                for webhook in list(webhooks_by_id.values())[: self.max_workers]
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log results
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"[webhook] ⚠️  Delivery failed: {result}")

        except Exception as exc:
            logger.error(f"[webhook] Error in batch processing: {exc}", exc_info=True)

    async def _get_pending_webhooks(self) -> List[Dict[str, Any]]:
        """Fetch pending webhook events from database"""
        try:
            response = self.supabase.rpc("get_pending_webhooks", {"p_limit": 100}).execute()

            if response.data:
                return response.data if isinstance(response.data, list) else [response.data]
            return []

        except Exception as exc:
            logger.error(f"[webhook] Failed to fetch pending webhooks: {exc}")
            return []

    async def _deliver_webhook(self, webhook: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deliver webhook event to all subscribed endpoints
        """
        webhook_id = webhook.get("webhook_id")
        event_type = webhook.get("event_type")
        payload = webhook.get("payload", {})
        subscriptions = webhook.get("subscriptions", [])

        logger.info(f"[webhook] 📤 Delivering {event_type} to {len(subscriptions)} subscribers")

        if not subscriptions:
            # No subscribers for this event type — mark as delivered
            await self._mark_delivered(webhook_id, success=True)
            return {"webhook_id": webhook_id, "delivered_to": 0}

        delivered_count = 0
        failed_count = 0

        for subscription in subscriptions:
            try:
                sub_url = subscription.get("url")
                sub_headers = subscription.get("headers", {})

                success = await self._post_to_endpoint(
                    sub_url,
                    payload,
                    sub_headers,
                )

                if success:
                    delivered_count += 1
                else:
                    failed_count += 1

            except Exception as exc:
                logger.warning(f"[webhook] ⚠️  Failed to deliver to {subscription.get('url')}: {exc}")
                failed_count += 1

        # Mark webhook as delivered if at least one subscription succeeded
        await self._mark_delivered(
            webhook_id,
            success=(delivered_count > 0),
            error=f"Failed subscriptions: {failed_count}/{len(subscriptions)}" if failed_count > 0 else None,
        )

        logger.info(
            f"[webhook] ✅ {event_type} delivered to {delivered_count}/{len(subscriptions)} endpoints"
        )

        return {
            "webhook_id": webhook_id,
            "event_type": event_type,
            "delivered_to": delivered_count,
            "failed": failed_count,
        }

    async def _post_to_endpoint(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str] | None = None,
    ) -> bool:
        """
        POST webhook payload to external endpoint
        Returns True if successful (2xx response)
        """
        try:
            import httpx

            # Build request headers
            request_headers = {
                "Content-Type": "application/json",
                "User-Agent": "TravelAgency-WebhookWorker/1.0",
                "X-Webhook-Timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if headers:
                request_headers.update(headers)

            async with httpx.AsyncClient(timeout=self.delivery_timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=request_headers,
                )

                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(f"[webhook] ✅ Webhook delivered: {url} → {response.status_code}")
                    return True
                else:
                    logger.warning(
                        f"[webhook] ⚠️  Webhook delivery failed: {url} → {response.status_code} {response.text[:200]}"
                    )
                    return False

        except asyncio.TimeoutError:
            logger.warning(f"[webhook] ⏱️  Webhook delivery timeout: {url}")
            return False
        except Exception as exc:
            logger.error(f"[webhook] ❌ Webhook delivery error: {exc}", exc_info=True)
            return False

    async def _mark_delivered(
        self,
        webhook_id: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Mark webhook delivery attempt in database"""
        try:
            self.supabase.rpc(
                "mark_webhook_delivered",
                {
                    "p_webhook_id": webhook_id,
                    "p_success": success,
                    "p_error": error,
                },
            ).execute()

        except Exception as exc:
            logger.error(f"[webhook] Failed to mark webhook delivered: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Standalone Worker Script
# ─────────────────────────────────────────────────────────────────────────────

async def run_worker() -> None:
    """Run webhook delivery worker (invoked via CLI or scheduler)"""
    from app.services.supabase_client import get_supabase

    supabase = get_supabase()

    worker = WebhookDeliveryWorker(
        supabase_client=supabase,
        poll_interval_seconds=10,
        max_workers=10,
        delivery_timeout_seconds=30,
    )

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("[webhook] Received interrupt signal, shutting down...")
        worker.stop()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/app")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(run_worker())
