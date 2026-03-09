from draft import router as draft_router
from home import router as home_router
from myteam import router as myteam_router
from ppa_router import router as ppa_router
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
