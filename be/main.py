from draft import router as draft_router
from home import router as home_router
from myteam import router as myteam_router
from players import router as players_router

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="PPA-Dun API")

# Register all data routers. Frontend can switch from mock.ts to these APIs.
app.include_router(players_router)
app.include_router(home_router)
app.include_router(myteam_router)
app.include_router(draft_router)


# Basic liveness check: verifies API process is running.
@app.get("/")
def root():
    return {"message": "PPA-Dun backend is running"}


@app.get("/health")
def health():
    return {"ok": True}

# CORS 설정: 프론트엔드 개발 서버에서 백엔드 API에 요청할 수 있도록 허용 (프론트 주소에서 백 주소로 접근을 허용)
# 그렇다고 해서 프론트의 VITE_API_BASE_URL가 필요 없는 것은 아님. 클라우드에 올리기 전까지는 프론트가 그렇게 설정해야 함.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # [CHANGED] Frontend Vite dev server origins.
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
