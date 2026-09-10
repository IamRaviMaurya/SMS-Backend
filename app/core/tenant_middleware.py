"""
Backward-compatibility shim.

The old TenantResolutionMiddleware trusted the X-Tenant-ID header from the client,
which allowed any caller to read another school's data. Tenant resolution now lives
in app.core.security.TenantAuthGuard (derived from the JWT) and the scoping helpers
live in app.core.tenancy. This module only re-exports them so existing imports work.
"""
from app.core.tenancy import (  # noqa: F401
    get_current_tenant_id,
    set_current_tenant_id,
    require_tenant_id,
    tenant_scope,
    bypass_tenant_scope,
)
