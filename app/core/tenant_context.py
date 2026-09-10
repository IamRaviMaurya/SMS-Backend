"""
Low-level tenant context primitives with NO dependency on app models, so that
app.core.database can import them without creating an import cycle.

Higher-level helpers (tenant_scope, bypass_tenant_scope, the SQLAlchemy hooks)
live in app.core.tenancy and re-export everything defined here.
"""
import contextvars
from typing import Optional

from sqlalchemy.orm import Query

_tenant_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("sms_tenant_id", default=None)
_bypass_ctx: contextvars.ContextVar[bool] = contextvars.ContextVar("sms_tenant_bypass", default=False)


class TenantContextMissing(RuntimeError):
    """Raised when tenant-owned data is accessed without an active tenant context."""


class TenantViolation(RuntimeError):
    """Raised when code tries to write a row that belongs to another tenant."""


def get_current_tenant_id() -> Optional[str]:
    return _tenant_ctx.get()


def set_current_tenant_id(tenant_id: Optional[str]) -> contextvars.Token:
    return _tenant_ctx.set(tenant_id)


def reset_current_tenant_id(token: contextvars.Token) -> None:
    _tenant_ctx.reset(token)


def require_tenant_id() -> str:
    tenant_id = _tenant_ctx.get()
    if not tenant_id:
        raise TenantContextMissing("No active tenant context")
    return tenant_id


def is_scope_bypassed() -> bool:
    return _bypass_ctx.get()


def tenant_criteria(tenant_id: str):
    """`with_loader_criteria` option restricting every TenantMixin entity to one tenant."""
    from sqlalchemy.orm import with_loader_criteria
    from app.models.tenant import TenantMixin  # lazy: models import database

    return with_loader_criteria(
        TenantMixin,
        lambda cls: cls.tenant_id == tenant_id,
        include_aliases=True,
        propagate_to_loaders=True,
    )


class TenantQuery(Query):
    """
    Session query class that closes the one hole `with_loader_criteria` leaves open:
    `Query.count()` wraps the query in a column-only subquery, which the
    `do_orm_execute` hook cannot see as an entity load. We therefore attach the
    tenant criteria to the query itself (it survives into the subquery) and apply
    the same fail-closed rule as the hook.
    """

    def _touches_tenant_entity(self) -> bool:
        from app.models.tenant import TenantMixin  # lazy

        for desc in self.column_descriptions:
            entity = desc.get("entity")
            if isinstance(entity, type) and issubclass(entity, TenantMixin):
                return True
        for from_obj in getattr(self, "_from_obj", ()) or ():
            entity = getattr(from_obj, "entity_namespace", None)
            if isinstance(entity, type) and issubclass(entity, TenantMixin):
                return True
        for join in getattr(self, "_setup_joins", ()) or ():
            target = join[0] if isinstance(join, tuple) else join
            cls = getattr(target, "class_", None) or getattr(getattr(target, "entity", None), "class_", None)
            if isinstance(cls, type) and issubclass(cls, TenantMixin):
                return True
        return False

    def count(self) -> int:
        if is_scope_bypassed():
            return super().count()
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            if self._touches_tenant_entity():
                raise TenantContextMissing("count() on tenant-owned data without an active tenant context")
            return super().count()
        return Query.count(self.options(tenant_criteria(tenant_id)))
