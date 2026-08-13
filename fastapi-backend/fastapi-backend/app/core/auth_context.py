"""
TASK 6: Unified Authentication & Authorization Context

Centralized auth context that:
1. Resolves JWT tokens from Portal or CRM users
2. Maps user roles to permissions (Customer, Staff, Admin)
3. Provides unified identity across Portal ↔ CRM
4. Validates customer record ownership
5. Prevents ID mismatch errors

Auth Context Flow:
  auth.users (Supabase Auth)
      ↓
  JWT Token (ES256 or HS256)
      ↓
  AuthContext (identity + roles + permissions)
      ↓
  Permission checks (require_auth, require_staff, etc.)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Set
from uuid import UUID

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Enums for Roles and Permissions
# ─────────────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    """User roles in the system"""
    CUSTOMER = "customer"          # Portal customer
    STAFF = "staff"                # CRM staff member
    ADMIN = "admin"                # System administrator
    SUPER_ADMIN = "super_admin"    # Super admin (CRM only)


class AuthContext:
    """
    Unified authentication & authorization context.
    
    Represents a single authenticated user with:
    - Identity (user_id, email)
    - Role (customer, staff, admin, super_admin)
    - Permissions (inferred from role)
    - Associated resources (customer_profile_id, organization_id)
    """

    def __init__(
        self,
        user_id: str | UUID,
        email: str,
        role: UserRole | str = UserRole.CUSTOMER,
        customer_profile_id: Optional[str | UUID] = None,
        organization_id: Optional[str | UUID] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ):
        self.user_id = str(user_id)
        self.email = email
        self.role = UserRole(role) if isinstance(role, str) else role
        self.customer_profile_id = str(customer_profile_id) if customer_profile_id else None
        self.organization_id = str(organization_id) if organization_id else None
        self.first_name = first_name
        self.last_name = last_name

    @property
    def is_customer(self) -> bool:
        """Is this a Portal customer?"""
        return self.role == UserRole.CUSTOMER

    @property
    def is_staff(self) -> bool:
        """Is this CRM staff or admin?"""
        return self.role in (UserRole.STAFF, UserRole.ADMIN, UserRole.SUPER_ADMIN)

    @property
    def is_admin(self) -> bool:
        """Is this system admin?"""
        return self.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)

    @property
    def is_super_admin(self) -> bool:
        """Is this super admin?"""
        return self.role == UserRole.SUPER_ADMIN

    @property
    def permissions(self) -> Set[str]:
        """Get inferred permissions from role"""
        permissions = set()

        if self.is_customer:
            permissions.update({
                "view_own_profile",
                "update_own_profile",
                "create_travel_request",
                "view_own_travel_requests",
                "upload_document",
                "view_own_documents",
            })

        if self.is_staff:
            permissions.update({
                "view_all_customers",
                "view_customer_profiles",
                "view_travel_requests",
                "view_documents",
                "update_document_status",
                "update_travel_request_status",
                "assign_staff_to_request",
                "view_crm_metrics",
                "manage_webhooks",
            })

        if self.is_admin:
            permissions.update({
                "manage_users",
                "manage_staff",
                "manage_organizations",
                "view_audit_logs",
                "manage_settings",
            })

        if self.is_super_admin:
            permissions.add("*")  # All permissions

        return permissions

    def has_permission(self, permission: str) -> bool:
        """Check if user has permission"""
        perms = self.permissions
        return "*" in perms or permission in perms

    def can_view_customer(self, target_customer_id: str | UUID) -> bool:
        """
        Check if user can view another customer's profile.
        
        Rules:
        - Customers can only view their own profile
        - Staff/Admin can view any customer
        """
        target_id = str(target_customer_id)

        if self.is_customer:
            # Customer can only view their own profile
            return self.customer_profile_id == target_id

        if self.is_staff:
            # Staff can view any customer
            return True

        return False

    def can_view_travel_request(self, travel_request_id: str | UUID, client_user_id: str | UUID) -> bool:
        """
        Check if user can view a travel request.
        
        Rules:
        - Customers can only view their own requests
        - Staff can view any request
        """
        if self.is_customer:
            # Customer can only view their own requests
            return str(client_user_id) == self.user_id

        if self.is_staff:
            # Staff can view any request
            return True

        return False

    def can_view_document(self, doc_client_user_id: str | UUID) -> bool:
        """
        Check if user can view a document.
        
        Rules:
        - Customers can only view their own documents
        - Staff can view any document
        """
        if self.is_customer:
            # Customer can only view their own documents
            return str(doc_client_user_id) == self.user_id

        if self.is_staff:
            # Staff can view any document
            return True

        return False

    def __repr__(self) -> str:
        return (
            f"AuthContext(user_id={self.user_id[:8]}..., "
            f"email={self.email}, role={self.role.value})"
        )

    def to_dict(self) -> dict:
        """Serialize to dict for logging/debugging"""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "role": self.role.value,
            "customer_profile_id": self.customer_profile_id,
            "organization_id": self.organization_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "permissions": list(self.permissions),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Auth Context Builder
# ─────────────────────────────────────────────────────────────────────────────

class AuthContextBuilder:
    """
    Build AuthContext from JWT token payload + database lookups.
    
    Handles:
    - Role detection (from profiles table)
    - Customer profile ID resolution
    - Organization ID resolution
    """

    def __init__(self, supabase_client: object):
        self.supabase = supabase_client

    def build_from_token(
        self,
        user_id: str,
        email: str,
        token_role: Optional[str] = None,
    ) -> AuthContext:
        """
        Build AuthContext from JWT token payload.
        
        Falls back to database lookups for role + customer_profile_id.
        """
        logger.info(f"[auth_context] Building context for user={user_id[:8]}... email={email}")

        # Try to resolve role + customer_profile from profiles table
        try:
            response = (
                self.supabase.table("profiles")
                .select("id, role, organization_id")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                profile = response.data[0]
                role = profile.get("role", token_role or "customer")
                customer_profile_id = profile.get("id")
                organization_id = profile.get("organization_id")

                logger.info(
                    f"[auth_context] ✅ Context built from profiles: "
                    f"role={role}, customer_profile_id={customer_profile_id}"
                )

                return AuthContext(
                    user_id=user_id,
                    email=email,
                    role=role,
                    customer_profile_id=customer_profile_id,
                    organization_id=organization_id,
                )

        except Exception as exc:
            logger.warning(f"[auth_context] Profile lookup failed: {exc}")

        # Fallback: try customer_profiles table
        try:
            response = (
                self.supabase.table("customer_profiles")
                .select("id, status, kyc_status")
                .eq("auth_user_id", user_id)
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                customer = response.data[0]
                customer_profile_id = customer.get("id")

                logger.info(
                    f"[auth_context] ✅ Context built from customer_profiles: "
                    f"customer_profile_id={customer_profile_id}"
                )

                return AuthContext(
                    user_id=user_id,
                    email=email,
                    role=token_role or "customer",
                    customer_profile_id=customer_profile_id,
                )

        except Exception as exc:
            logger.warning(f"[auth_context] Customer profile lookup failed: {exc}")

        # Fallback: basic context with token role
        logger.info(f"[auth_context] ⚠️  Using fallback context (no profile found)")

        return AuthContext(
            user_id=user_id,
            email=email,
            role=token_role or "customer",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Permission Check Functions (for use in FastAPI dependencies)
# ─────────────────────────────────────────────────────────────────────────────

def check_permission(context: AuthContext, permission: str) -> bool:
    """Check if user has permission"""
    if not context.has_permission(permission):
        logger.warning(
            f"[auth_context] ❌ Permission denied: user={context.user_id}, "
            f"permission={permission}, role={context.role.value}"
        )
        return False
    return True


def check_customer_access(context: AuthContext, customer_id: str) -> bool:
    """Check if user can access customer profile"""
    if not context.can_view_customer(customer_id):
        logger.warning(
            f"[auth_context] ❌ Customer access denied: user={context.user_id}, "
            f"target_customer={customer_id}, role={context.role.value}"
        )
        return False
    return True


def check_travel_request_access(
    context: AuthContext,
    travel_request_id: str,
    client_user_id: str,
) -> bool:
    """Check if user can access travel request"""
    if not context.can_view_travel_request(travel_request_id, client_user_id):
        logger.warning(
            f"[auth_context] ❌ Travel request access denied: user={context.user_id}, "
            f"request={travel_request_id}, client={client_user_id}, role={context.role.value}"
        )
        return False
    return True


def check_document_access(context: AuthContext, doc_client_user_id: str) -> bool:
    """Check if user can access document"""
    if not context.can_view_document(doc_client_user_id):
        logger.warning(
            f"[auth_context] ❌ Document access denied: user={context.user_id}, "
            f"doc_client={doc_client_user_id}, role={context.role.value}"
        )
        return False
    return True
