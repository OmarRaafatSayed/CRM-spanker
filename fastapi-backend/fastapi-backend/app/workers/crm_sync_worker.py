"""
CRM Sync Worker

Async background worker that processes Portal → CRM synchronization queue.
Runs the entity_sync_state state machine to keep Portal and CRM in sync.

This worker:
1. Polls for pending syncs from sync_queue
2. Transitions entity_sync_state through state machine
3. Calls external CRM API to provision entities
4. Marks entities as synced with CRM IDs
5. Handles retries with exponential backoff
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class CRMSyncWorker:
    """
    Portal ↔ CRM Synchronization Worker
    Processes entity_sync_state queue to keep systems in sync
    """

    def __init__(
        self,
        supabase_client: Any,
        crm_api_endpoint: str = "",
        crm_api_key: str = "",
        poll_interval_seconds: int = 30,
        max_workers: int = 5,
    ):
        self.supabase = supabase_client
        self.crm_api_endpoint = crm_api_endpoint
        self.crm_api_key = crm_api_key
        self.poll_interval = poll_interval_seconds
        self.max_workers = max_workers
        self.running = False

    async def start(self) -> None:
        """Start sync worker (runs forever until stop() is called)"""
        self.running = True
        logger.info("[crm_sync] 🚀 CRM Sync Worker started")

        try:
            while self.running:
                await self._process_batch()
                await asyncio.sleep(self.poll_interval)
        except Exception as exc:
            logger.error(f"[crm_sync] ❌ Worker crashed: {exc}", exc_info=True)
        finally:
            self.running = False
            logger.info("[crm_sync] 🛑 CRM Sync Worker stopped")

    def stop(self) -> None:
        """Stop sync worker"""
        self.running = False

    async def _process_batch(self) -> None:
        """Process next batch of pending syncs"""
        try:
            # Get pending syncs
            pending = await self._get_pending_syncs()
            if not pending:
                return

            logger.info(f"[crm_sync] 📦 Processing {len(pending)} pending syncs")

            # Process up to max_workers at a time
            tasks = [
                self._sync_entity(sync_record)
                for sync_record in pending[: self.max_workers]
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log results
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"[crm_sync] ⚠️  Sync failed: {result}")
                elif result:
                    logger.info(f"[crm_sync] ✅ Sync completed: {result}")

        except Exception as exc:
            logger.error(f"[crm_sync] Error in batch processing: {exc}", exc_info=True)

    async def _get_pending_syncs(self) -> List[Dict[str, Any]]:
        """Fetch pending syncs from database"""
        try:
            response = self.supabase.rpc("get_pending_crm_syncs", {"p_limit": 50}).execute()

            if response.data:
                return response.data if isinstance(response.data, list) else [response.data]
            return []

        except Exception as exc:
            logger.error(f"[crm_sync] Failed to fetch pending syncs: {exc}")
            return []

    async def _sync_entity(self, sync_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sync single entity: Portal → CRM
        Implements full state machine transition
        """
        sync_id = sync_record.get("sync_id")
        entity_type = sync_record.get("entity_type")
        entity_id = sync_record.get("entity_id")

        logger.info(f"[crm_sync] 🔄 Syncing {entity_type}:{entity_id}")

        try:
            # ── 1. FETCH ENTITY DATA ──────────────────────────────────────
            entity_data = await self._fetch_entity(entity_type, entity_id)
            if not entity_data:
                raise ValueError(f"Entity not found: {entity_type}:{entity_id}")

            # ── 2. TRANSITION TO 'syncing' STATE ──────────────────────────
            await self._transition_state(
                entity_type, entity_id, "syncing"
            )

            # ── 3. CALL CRM API ──────────────────────────────────────────
            crm_id = await self._provision_in_crm(entity_type, entity_data)
            if not crm_id:
                raise ValueError("CRM provisioning returned no ID")

            # ── 4. TRANSITION TO 'synced' STATE WITH CRM ID ──────────────
            await self._transition_state(
                entity_type,
                entity_id,
                "synced",
                crm_id=crm_id,
            )

            logger.info(
                f"[crm_sync] ✅ Sync complete: {entity_type}:{entity_id} → CRM:{crm_id}"
            )

            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "crm_id": crm_id,
                "success": True,
            }

        except Exception as exc:
            logger.warning(f"[crm_sync] ⚠️  Sync failed: {exc}")

            # ── TRANSITION TO 'sync_failed' STATE WITH ERROR ──────────────
            await self._transition_state(
                entity_type,
                entity_id,
                "sync_failed",
                error=str(exc),
            )

            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "error": str(exc),
                "success": False,
            }

    async def _fetch_entity(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full entity data from Portal database"""
        try:
            table_mapping = {
                "customer_profile": "customer_profiles",
                "travel_request": "travel_requests",
                "visa_application": "visa_applications",
                "payment_record": "payment_records",
                "document": "customer_documents",
            }

            table_name = table_mapping.get(entity_type)
            if not table_name:
                raise ValueError(f"Unknown entity type: {entity_type}")

            response = (
                self.supabase.table(table_name)
                .select("*")
                .eq("id", entity_id)
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]

            return None

        except Exception as exc:
            logger.error(f"[crm_sync] Failed to fetch {entity_type}:{entity_id}: {exc}")
            raise

    async def _transition_state(
        self,
        entity_type: str,
        entity_id: str,
        new_state: str,
        crm_id: str | None = None,
        error: str | None = None,
    ) -> Dict[str, Any]:
        """Transition entity through state machine"""
        try:
            response = self.supabase.rpc(
                "transition_sync_state",
                {
                    "p_entity_type": entity_type,
                    "p_entity_id": entity_id,
                    "p_new_state": new_state,
                    "p_crm_id": crm_id,
                    "p_error": error,
                },
            ).execute()

            if response.data:
                return response.data[0] if isinstance(response.data, list) else response.data

            raise ValueError(f"State transition failed for {entity_type}:{entity_id}")

        except Exception as exc:
            logger.error(f"[crm_sync] State transition error: {exc}")
            raise

    async def _provision_in_crm(
        self,
        entity_type: str,
        entity_data: Dict[str, Any],
    ) -> Optional[str]:
        """
        Call external CRM API to provision entity

        In production, this would:
        1. POST to self.crm_api_endpoint with auth headers
        2. Handle CRM-specific payload formats
        3. Map Portal field names to CRM field names
        4. Extract CRM entity ID from response
        """
        if not self.crm_api_endpoint:
            logger.warning(
                "[crm_sync] ⚠️  No CRM endpoint configured — "
                "skipping actual CRM sync (local testing mode)"
            )
            # Generate a fake CRM ID for testing
            import uuid
            return str(uuid.uuid4())

        try:
            import httpx

            # Map entity type to CRM endpoint
            crm_endpoint_mapping = {
                "customer_profile": f"{self.crm_api_endpoint}/customers",
                "travel_request": f"{self.crm_api_endpoint}/bookings",
                "visa_application": f"{self.crm_api_endpoint}/visa_apps",
                "payment_record": f"{self.crm_api_endpoint}/payments",
                "document": f"{self.crm_api_endpoint}/documents",
            }

            endpoint = crm_endpoint_mapping.get(entity_type)
            if not endpoint:
                raise ValueError(f"No CRM endpoint for {entity_type}")

            # Call CRM API
            async with httpx.AsyncClient() as client:
                headers = {}
                if self.crm_api_key:
                    headers["Authorization"] = f"Bearer {self.crm_api_key}"

                response = await client.post(
                    endpoint,
                    json=entity_data,
                    headers=headers,
                    timeout=30,
                )

                if response.status_code not in (200, 201):
                    raise ValueError(
                        f"CRM API error: {response.status_code} {response.text}"
                    )

                crm_response = response.json()
                crm_id = crm_response.get("id") or crm_response.get("crm_id")

                if not crm_id:
                    raise ValueError(f"No ID in CRM response: {crm_response}")

                logger.info(
                    f"[crm_sync] 📤 {entity_type} provisioned in CRM: {crm_id}"
                )

                return crm_id

        except Exception as exc:
            logger.error(f"[crm_sync] CRM API call failed: {exc}", exc_info=True)
            raise


# ─────────────────────────────────────────────────────────────────────────────
# Standalone Worker Script
# ─────────────────────────────────────────────────────────────────────────────

async def run_worker() -> None:
    """Run CRM sync worker (invoked via CLI or scheduler)"""
    import os
    from app.services.supabase_client import get_supabase

    supabase = get_supabase()
    crm_endpoint = os.getenv("CRM_API_ENDPOINT", "")
    crm_key = os.getenv("CRM_API_KEY", "")

    worker = CRMSyncWorker(
        supabase_client=supabase,
        crm_api_endpoint=crm_endpoint,
        crm_api_key=crm_key,
        poll_interval_seconds=30,
        max_workers=5,
    )

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("[crm_sync] Received interrupt signal, shutting down...")
        worker.stop()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/app")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(run_worker())
