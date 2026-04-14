# FastAPI application entry point.
# Registers all page routers (draft, home, myteam, players, ppa) and
# configures CORS middleware so the frontend dev server can reach the backend.
from draft import router as draft_router
from home import router as home_router

from myteam import router as myteam_router
from ppa_api.ppa_router import router as ppa_router
from players import router as players_router

from core.config import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="PPA-Dun API")

# Register all data routers. Frontend can switch from mock.ts to these APIs.
app.include_router(players_router)
app.include_router(home_router)
app.include_router(myteam_router)
app.include_router(draft_router)
app.include_router(ppa_router)


# Basic liveness check: verifies API process is running.
@app.get("/")
def root():
    return {"message": "PPA-Dun backend is running"}


def _parse_cors_origins(raw_origins: str) -> list[str]:
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


@app.get("/health")
def health():
    return {"ok": True}

# CORS: allows the frontend dev server to reach the backend API.
# The frontend still needs VITE_API_BASE_URL configured until cloud deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
