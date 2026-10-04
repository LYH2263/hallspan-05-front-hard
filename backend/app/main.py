from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def ensure_schema() -> None:
    """create_all 只管新表；这里为已存在的库补齐新增列（幂等）。"""
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    cols = {t: {c["name"] for c in insp.get_columns(t)} for t in insp.get_table_names()}
    with engine.begin() as conn:
        if "halls" in cols and "front_row_rows" not in cols["halls"]:
            conn.execute(text("ALTER TABLE halls ADD COLUMN front_row_rows INTEGER NOT NULL DEFAULT 0"))
        if "candidates" in cols and "special" not in cols["candidates"]:
            conn.execute(text("ALTER TABLE candidates ADD COLUMN special BOOLEAN NOT NULL DEFAULT FALSE"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_schema()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="HallSpan", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
