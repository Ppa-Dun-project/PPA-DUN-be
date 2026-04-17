# FastAPI application entry point.
# Registers all page routers (draft, home, myteam, players, ppa) and
# configures CORS middleware so the frontend dev server can reach the backend.
from auth import router as auth_router
from draft import router as draft_router
from home import router as home_router
from myteam import router as myteam_router
from players import router as players_router

from core.config import settings
from db.session import engine, Base
from db.models import User  # noqa: F401 — import so SQLAlchemy registers the table

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Auto-create all DB tables on startup (if they don't exist yet)
Base.metadata.create_all(bind=engine)

# 백엔드 서버를 uvicorn main:app으로 실행하면 시작되는 것.
# app이 요청을 받아서 알맞은 함수로 연결해줌
# app은 모든 엔드포인트, 라우터, 미들웨어 (CORS)를 한번에 관리함
app = FastAPI(title="PPA-Dun API")

# 각 파일에서 정의한 엔드포인트들을 하나의 앱에 합침
# app - 서버 자체 / router - 각 파일의 엔드포인트 묶음
app.include_router(auth_router)
app.include_router(players_router)
app.include_router(home_router)
app.include_router(myteam_router)
app.include_router(draft_router)


# 메인 백엔드 서버의 상태 확인.
@app.get("/")
def root():
    return {"message": "PPA-Dun backend is running"}

#.env의 CORS_ORIGINS 값(예: "http://localhost:5173, http://127.0.0.1:5173")
# 쉼표로 분리해서 리스트로 만듦
def _parse_cors_origins(raw_origins: str) -> list[str]:
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


@app.get("/health")
def health():
    return {"ok": True}

# CORS (Cross-Origin Resource Sharing): allows the frontend dev server to reach the backend API.
# CORS는 브라우저 보안 정책이므로 서버 간에는 상관이 없음.
app.add_middleware(
    CORSMiddleware,
    # 어떤 출처에서 오는 요청을 허용할지
    allow_origins=_parse_cors_origins(settings.CORS_ORIGINS),

    # 쿠키/인증 정보 포함 허용 여부
    allow_credentials=True,

    # 어떤 HTTP 메서드를 허용할지 (GET, POST, PUT, DELETE 등)
    allow_methods=["*"],

    # 어떤 HTTP 헤더를 허용할지 (커스텀 헤더 or "Content-Type", "Authorization" 등만 허용)
    allow_headers=["*"],
)
