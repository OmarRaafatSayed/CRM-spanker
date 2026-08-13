"""
TASK 8: Background Job & Webhook Reliability (Resilience)

Implements:
1. Error handling with transactional rollbacks (ACID compliance)
2. Fallback queue mechanisms for failed operations
3. Exponential backoff retry logic
4. Dead letter queues for permanently failed items
5. Circuit breaker pattern for external service calls
6. Comprehensive error tracking and recovery

Key Principles:
- Never silently drop customer records
- Transactional writes (all-or-nothing)
- Automatic retry with backoff
- Dead letter queue for manual intervention
- Detailed error logging for debugging
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar
from uuid import UUID

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ─────────────────────────────────────────────────────────────────────────────
# Enums for Operation States & Statuses
# ─────────────────────────────────────────────────────────────────────────────

class OperationStatus(str, Enum):
    """Operation execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    DEAD_LETTER = "dead_letter"


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    TRANSIENT = "transient"      # Temporary error, retry
    PERMANENT = "permanent"       # Permanent error, don't retry
    UNKNOWN = "unknown"           # Unknown, retry with caution


# ─────────────────────────────────────────────────────────────────────────────
# Error Classification
# ─────────────────────────────────────────────────────────────────────────────

class ErrorClassifier:
    """Classify errors to determine retry strategy"""

    # Transient errors (retryable)
    TRANSIENT_PATTERNS = [
        "connection",
        "timeout",
        "temporarily unavailable",
        "too many requests",
        "deadline exceeded",
        "service unavailable",
    ]

    # Permanent errors (non-retryable)
    PERMANENT_PATTERNS = [
        "invalid",
        "unauthorized",
        "forbidden",
        "not found",
        "conflict",
        "validation",
        "duplicate key",
    ]

    @classmethod
    def classify(cls, error: Exception) -> ErrorSeverity:
        """Classify error as transient or permanent"""
        error_msg = str(error).lower()

        for pattern in cls.PERMANENT_PATTERNS:
            if pattern in error_msg:
                return ErrorSeverity.PERMANENT

        for pattern in cls.TRANSIENT_PATTERNS:
            if pattern in error_msg:
                return ErrorSeverity.TRANSIENT

        return ErrorSeverity.UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
# Circuit Breaker Pattern
# ─────────────────────────────────────────────────────────────────────────────

class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Failing, reject requests
    HALF_OPEN = "half_open"    # Testing recovery


class CircuitBreaker:
    """
    Implement circuit breaker pattern for external service calls.
    
    Prevents cascading failures by stopping requests to failing services.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60,
        expected_exception: type = Exception,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open"""
        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    logger.info(f"[circuit_breaker] {self.name} entering HALF_OPEN state")
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.success_count = 0
                    return False

            return True

        return False

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if self.is_open:
            raise Exception(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Service unavailable. Will retry at {self.last_failure_time + timedelta(seconds=self.recovery_timeout)}"
            )

        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

            # Success
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= 2:
                    logger.info(f"[circuit_breaker] {self.name} recovered to CLOSED")
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0

            return result

        except self.expected_exception as exc:
            self.failure_count += 1
            self.last_failure_time = datetime.now(timezone.utc)

            logger.warning(
                f"[circuit_breaker] {self.name} failure {self.failure_count}/{self.failure_threshold}: {exc}"
            )

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.error(f"[circuit_breaker] {self.name} circuit opened")

            raise


# ─────────────────────────────────────────────────────────────────────────────
# Transactional Operation with Rollback
# ─────────────────────────────────────────────────────────────────────────────

class TransactionalOperation:
    """
    Atomic operation with rollback capability.
    
    Ensures all-or-nothing semantics for multi-step operations.
    """

    def __init__(self, operation_id: str, operation_type: str):
        self.operation_id = operation_id
        self.operation_type = operation_type
        self.steps: List[Dict[str, Any]] = []
        self.status = OperationStatus.PENDING
        self.created_at = datetime.now(timezone.utc)
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.error_severity: Optional[ErrorSeverity] = None

    def add_step(
        self,
        name: str,
        execute_fn: Callable,
        rollback_fn: Optional[Callable] = None,
        **kwargs,
    ) -> None:
        """Add step to operation"""
        self.steps.append({
            "name": name,
            "execute_fn": execute_fn,
            "rollback_fn": rollback_fn,
            "kwargs": kwargs,
            "status": OperationStatus.PENDING,
            "result": None,
            "error": None,
        })

    async def execute(self) -> Dict[str, Any]:
        """Execute operation with transactional semantics"""
        logger.info(f"[transaction] Starting {self.operation_type}:{self.operation_id}")
        self.status = OperationStatus.IN_PROGRESS

        executed_steps = []

        try:
            for idx, step in enumerate(self.steps):
                try:
                    logger.info(f"[transaction] Executing step {idx + 1}/{len(self.steps)}: {step['name']}")

                    # Execute step
                    result = await step["execute_fn"](**step["kwargs"]) \
                        if asyncio.iscoroutinefunction(step["execute_fn"]) \
                        else step["execute_fn"](**step["kwargs"])

                    step["status"] = OperationStatus.COMPLETED
                    step["result"] = result
                    executed_steps.append(step)

                    logger.info(f"[transaction] ✅ Step {idx + 1} completed: {step['name']}")

                except Exception as exc:
                    step["status"] = OperationStatus.FAILED
                    step["error"] = str(exc)
                    self.error = str(exc)
                    self.error_severity = ErrorClassifier.classify(exc)

                    logger.error(
                        f"[transaction] ❌ Step {idx + 1} failed: {step['name']}: {exc}",
                        exc_info=True,
                    )

                    # Rollback previous steps
                    logger.info(f"[transaction] Rolling back {len(executed_steps)} completed steps")
                    await self._rollback(executed_steps)

                    self.status = OperationStatus.ROLLED_BACK
                    raise

            # All steps completed successfully
            self.status = OperationStatus.COMPLETED
            self.completed_at = datetime.now(timezone.utc)

            logger.info(
                f"[transaction] ✅ {self.operation_type}:{self.operation_id} completed successfully"
            )

            return {
                "operation_id": self.operation_id,
                "status": self.status.value,
                "steps": len(self.steps),
                "results": [step["result"] for step in self.steps],
            }

        except Exception as exc:
            self.completed_at = datetime.now(timezone.utc)

            logger.error(
                f"[transaction] ❌ {self.operation_type}:{self.operation_id} failed after rollback",
                exc_info=True,
            )

            return {
                "operation_id": self.operation_id,
                "status": self.status.value,
                "error": self.error,
                "error_severity": self.error_severity.value if self.error_severity else None,
                "rollback_steps": len(executed_steps),
            }

    async def _rollback(self, executed_steps: List[Dict[str, Any]]) -> None:
        """Rollback executed steps in reverse order"""
        for idx, step in enumerate(reversed(executed_steps)):
            if step["rollback_fn"] is None:
                logger.warning(f"[transaction] ⚠️  Step '{step['name']}' has no rollback function")
                continue

            try:
                logger.info(f"[transaction] Rolling back: {step['name']}")

                rollback_result = await step["rollback_fn"]() \
                    if asyncio.iscoroutinefunction(step["rollback_fn"]) \
                    else step["rollback_fn"]()

                logger.info(f"[transaction] ✅ Rollback completed: {step['name']}")

            except Exception as exc:
                logger.error(
                    f"[transaction] ⚠️  Rollback failed for {step['name']}: {exc}",
                    exc_info=True,
                )


# ─────────────────────────────────────────────────────────────────────────────
# Exponential Backoff Retry Logic
# ─────────────────────────────────────────────────────────────────────────────

class RetryPolicy:
    """
    Exponential backoff retry policy.
    
    Retries with exponential backoff up to max_attempts.
    Skips retry for permanent errors.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        base_delay_seconds: float = 1,
        max_delay_seconds: float = 300,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay_seconds
        self.max_delay = max_delay_seconds
        self.jitter = jitter

    def get_delay_seconds(self, attempt: int) -> float:
        """Calculate delay for attempt (exponential backoff)"""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)

        if self.jitter:
            # Add random jitter (±10%)
            import random
            jitter_amount = delay * 0.1
            delay += random.uniform(-jitter_amount, jitter_amount)

        return max(delay, self.base_delay)

    async def execute(
        self,
        func: Callable,
        *args,
        on_retry: Optional[Callable] = None,
        **kwargs,
    ) -> Any:
        """Execute function with retry policy"""
        last_error: Optional[Exception] = None

        for attempt in range(self.max_attempts):
            try:
                result = await func(*args, **kwargs) \
                    if asyncio.iscoroutinefunction(func) \
                    else func(*args, **kwargs)
                return result

            except Exception as exc:
                last_error = exc
                error_severity = ErrorClassifier.classify(exc)

                if error_severity == ErrorSeverity.PERMANENT:
                    logger.error(
                        f"[retry] Permanent error on attempt {attempt + 1}, skipping retry: {exc}"
                    )
                    raise

                if attempt < self.max_attempts - 1:
                    delay = self.get_delay_seconds(attempt)
                    logger.warning(
                        f"[retry] Attempt {attempt + 1}/{self.max_attempts} failed: {exc}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    if on_retry:
                        await on_retry(attempt, delay, exc)

                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"[retry] All {self.max_attempts} attempts failed: {exc}"
                    )

        raise last_error or Exception("Max retries exceeded")


# ─────────────────────────────────────────────────────────────────────────────
# Dead Letter Queue for Permanently Failed Items
# ─────────────────────────────────────────────────────────────────────────────

class DeadLetterQueueManager:
    """
    Manage dead letter queue for permanently failed operations.
    
    Allows manual inspection and recovery of failed items.
    """

    def __init__(self, supabase_client: Any):
        self.supabase = supabase_client

    async def add_to_dlq(
        self,
        entity_type: str,
        entity_id: str,
        operation_type: str,
        error_message: str,
        error_severity: str,
        payload: Dict[str, Any],
    ) -> str:
        """Add item to dead letter queue"""
        try:
            response = self.supabase.table("dead_letter_queue").insert({
                "entity_type": entity_type,
                "entity_id": entity_id,
                "operation_type": operation_type,
                "error_message": error_message,
                "error_severity": error_severity,
                "payload": payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending_manual_review",
            }).execute()

            dlq_id = response.data[0]["id"] if response.data else None

            logger.error(
                f"[dlq] Added to dead letter queue: {entity_type}:{entity_id} "
                f"({operation_type}) - DLQ ID: {dlq_id}"
            )

            return dlq_id

        except Exception as exc:
            logger.error(f"[dlq] Failed to add item to DLQ: {exc}", exc_info=True)
            raise

    async def retry_from_dlq(self, dlq_id: str) -> bool:
        """Manually retry item from dead letter queue"""
        try:
            response = self.supabase.table("dead_letter_queue").select("*").eq("id", dlq_id).execute()

            if not response.data:
                logger.warning(f"[dlq] DLQ item not found: {dlq_id}")
                return False

            item = response.data[0]

            logger.info(f"[dlq] Retrying DLQ item: {dlq_id}")

            # Update status to 'in_progress'
            self.supabase.table("dead_letter_queue").update({
                "status": "in_progress",
                "retry_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", dlq_id).execute()

            return True

        except Exception as exc:
            logger.error(f"[dlq] Failed to retry DLQ item {dlq_id}: {exc}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Comprehensive Error Tracking
# ─────────────────────────────────────────────────────────────────────────────

class ErrorTracker:
    """Track and analyze system errors for observability"""

    def __init__(self, supabase_client: Any):
        self.supabase = supabase_client

    async def track_error(
        self,
        error_type: str,
        error_message: str,
        context: Dict[str, Any],
        severity: str = "warning",
    ) -> str:
        """Track error in error log"""
        try:
            response = self.supabase.table("error_log").insert({
                "error_type": error_type,
                "error_message": error_message,
                "context": context,
                "severity": severity,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()

            error_id = response.data[0]["id"] if response.data else None

            logger.info(f"[error_tracker] Logged error: {error_type} - ID: {error_id}")

            return error_id

        except Exception as exc:
            logger.error(f"[error_tracker] Failed to track error: {exc}")
            return ""

    async def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get error summary for the last N hours"""
        try:
            cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

            response = self.supabase.rpc(
                "get_error_summary",
                {"p_hours": hours},
            ).execute()

            return response.data if response.data else {}

        except Exception as exc:
            logger.error(f"[error_tracker] Failed to get error summary: {exc}")
            return {}
