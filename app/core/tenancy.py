"""
Central tenant-isolation layer.

Design goals
------------
1. Tenant identity is derived from the authenticated JWT (see app.core.security),
   never trusted from a client-supplied header alone.
2. Scoping is FAIL-CLOSED: any ORM query that touches a tenant-owned table while no
   tenant context is active raises TenantContextMissing instead of silently returning
   platform-wide data.
3. Scoping is CENTRALISED: a SQLAlchemy `do_orm_execute` hook automatically appends
   `tenant_id = :current_tenant` to every SELECT / UPDATE / DELETE against any model
   that inherits TenantMixin, so a forgotten `.filter(Model.tenant_id == ...)` in a
   route can no longer leak data. `Query.count()` is covered by TenantQuery
   (app.core.tenant_context), which the session factory uses as its query class.
4. Writes are guarded too: a `before_flush` hook stamps `tenant_id` on new rows and
   refuses to persist a row that belongs to a different tenant than the active one.
5. Platform-level (Super Admin) code that legitimately needs cross-tenant access must
   opt in explicitly with `bypass_tenant_scope()`.

Known limitation: 2.0-style `select(...).subquery()` wrappers are opaque to the hook.
Use `db.query(...)` (or apply `tenant_criteria()` yourself) for tenant-owned tables.
"""
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.tenant_context import (  # noqa: F401  (re-exported public API)
    TenantContextMissing,
    TenantQuery,
    TenantViolation,
    _bypass_ctx,
    _tenant_ctx,
    get_current_tenant_id,
    is_scope_bypassed,
    require_tenant_id,
    reset_current_tenant_id,
    set_current_tenant_id,
    tenant_criteria,
)
from app.models.tenant import TenantMixin


@contextmanager
def tenant_scope(tenant_id: str) -> Iterator[str]:
    """Run a block of code as the given tenant (scripts, login, background jobs)."""
    if not tenant_id:
        raise TenantContextMissing("tenant_scope() requires a tenant id")
    token = _tenant_ctx.set(tenant_id)
    try:
        yield tenant_id
    finally:
        _tenant_ctx.reset(token)


@contextmanager
def bypass_tenant_scope() -> Iterator[None]:
    """Explicit opt-out for platform-wide (Super Admin) queries and migrations."""
    token = _bypass_ctx.set(True)
    try:
        yield
    finally:
        _bypass_ctx.reset(token)


# ────────── SQLAlchemy hooks ──────────

def _touches_tenant_entity(execute_state) -> bool:
    try:
        mappers = execute_state.all_mappers
    except Exception:  # pragma: no cover - defensive
        return False
    return any(issubclass(m.class_, TenantMixin) for m in mappers)


def install_tenant_scoping(session_factory) -> None:
    """Attach automatic tenant filtering + write guards to a sessionmaker."""

    @event.listens_for(session_factory, "do_orm_execute")
    def _apply_tenant_filter(execute_state):
        if is_scope_bypassed():
            return
        # Relationship / column lazy-loads inherit the criteria from their parent
        # statement (propagate_to_loaders=True), so only top-level statements matter.
        if execute_state.is_column_load or execute_state.is_relationship_load:
            return
        if not (execute_state.is_select or execute_state.is_update or execute_state.is_delete):
            return
        if not _touches_tenant_entity(execute_state):
            return

        tenant_id = get_current_tenant_id()
        if not tenant_id:
            raise TenantContextMissing(
                "Tenant-owned data was queried without an active tenant context. "
                "Authenticate through TenantAuthGuard or wrap the call in tenant_scope()/bypass_tenant_scope()."
            )
        execute_state.statement = execute_state.statement.options(tenant_criteria(tenant_id))

    @event.listens_for(session_factory, "before_flush")
    def _guard_writes(session: Session, flush_context, instances):
        if is_scope_bypassed():
            return
        tenant_id = get_current_tenant_id()

        for obj in session.new:
            if not isinstance(obj, TenantMixin):
                continue
            if obj.tenant_id is None:
                if not tenant_id:
                    raise TenantContextMissing(
                        f"Cannot insert {type(obj).__name__} without an active tenant context"
                    )
                obj.tenant_id = tenant_id
            elif tenant_id and obj.tenant_id != tenant_id:
                raise TenantViolation(
                    f"Attempted to insert {type(obj).__name__} for tenant {obj.tenant_id!r} "
                    f"while acting as tenant {tenant_id!r}"
                )

        for obj in list(session.dirty) + list(session.deleted):
            if isinstance(obj, TenantMixin) and tenant_id and obj.tenant_id not in (None, tenant_id):
                raise TenantViolation(
                    f"Attempted to modify {type(obj).__name__} owned by tenant {obj.tenant_id!r} "
                    f"while acting as tenant {tenant_id!r}"
                )


# Install once on the application's session factory (idempotent per process).
from app.core.database import SessionLocal  # noqa: E402

if not getattr(SessionLocal, "_sms_tenant_scoping_installed", False):
    install_tenant_scoping(SessionLocal)
    SessionLocal._sms_tenant_scoping_installed = True
