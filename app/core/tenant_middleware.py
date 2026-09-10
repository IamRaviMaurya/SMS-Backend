import contextvars
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Thread-safe global request tenant context
_tenant_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("tenant_id", default=None)


def get_current_tenant_id() -> Optional[str]:
    return _tenant_context.get()


def set_current_tenant_id(tenant_id: Optional[str]):
    _tenant_context.set(tenant_id)


class TenantResolutionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = None

        # 1. Resolve from X-Tenant-ID Header
        header_tenant = request.headers.get("X-Tenant-ID")
        if header_tenant:
            tenant_id = header_tenant

        # 2. Fallback to Subdomain (e.g. greenwood.sms.com -> greenwood)
        elif request.headers.get("host"):
            host = request.headers.get("host").split(":")[0]
            parts = host.split(".")
            if len(parts) > 2 and parts[0] not in ["www", "api", "app", "localhost"]:
                tenant_id = parts[0]  # Slug identifier

        set_current_tenant_id(tenant_id)
        request.state.tenant_id = tenant_id

        response = await call_next(request)
        return response
