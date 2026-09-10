from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings
from app.core.tenant_context import TenantQuery

# Handle sqlite specific connect args if needed
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

# TenantQuery makes Query.count() honour the active tenant (see app.core.tenancy).
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, query_cls=TenantQuery)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
