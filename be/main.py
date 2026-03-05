from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from core.config import settings
from db.session import engine, SessionLocal

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True, "env": settings.ENV}

@app.get("/health/db")
def health_db():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"ok": True, "db": "connected"}

@app.on_event("startup")
def startup_check():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))