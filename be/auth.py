import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests
from pydantic import BaseModel
from dotenv import load_dotenv

from db.session import get_db
from db.models import User
from security import create_access_token

load_dotenv()
router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")


# ── Request / Response Models ─────────────────────────────────────────────────

class GoogleLoginRequest(BaseModel):
    # Google ID token from the frontend
    credential: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str

    class Config:
        from_attributes = True


# 사용자가 기존인지, 신규인지 확인 후, 우리 서버에서 발급한 JWT + 사용자 정보를 함께 담아 프론트로 보냄
class OurJwtToFront(BaseModel):
    access_token: str           # 우리 서버가 발급한 JWT (프론트가 localStorage에 저장)
    token_type: str = "bearer"  # Authorization 헤더 스킴 ("Bearer <token>" 형식으로 보내라는 의미)
    user: UserResponse          # 사용자 기본 정보




# ── Helper: verify Google token ───────────────────────────────────────────────
# 구글 ID 토큰을 검증하는 함수. (구글 ID 토큰 = "구글이 프론트에 발급해준" JWT 형식 토큰)
def _verify_google_token(token: str) -> dict:
    try:
        return id_token.verify_oauth2_token(
            token,               # 프론트에서 받은 구글 ID 토큰 문자열 
            requests.Request(),  # 토큰의 디지털 서명 유효성 검사 (백엔드와 구글 서버가 통신)
            GOOGLE_CLIENT_ID     # 토큰이 우리 앱을 위해 발급된 것이 맞는지 확인
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")


# ── POST /api/auth/google/verify ──────────────────────────────────────────────
# 프론트로부터 전달받은 인증 정보를 바탕으로 DB에서 사용자 조회 또는 생성 후, 사용자 정보 반환
# GoogleLoginRequest: 구글 로그인 후 발급받은 토큰 포함
@router.post("/google/verify", response_model=OurJwtToFront)
def google_login(req: GoogleLoginRequest, db: Session = Depends(get_db)):

    # 토큰 유효성 검사
    idinfo = _verify_google_token(req.credential)

    google_id = idinfo["sub"]       # 구글에서 발급하는 사용자 고유 식별자
    email = idinfo["email"]         # 사용자 이메일 정보
    name = idinfo.get("name", "")   # 사용자 이름 정보 (이름 정보 누락 대비)

    # 사용자 고유 식별자 값이 DB에 이미 있는지 확인 (기존 사용자 여부)
    user = db.query(User).filter(User.google_id == google_id).first()

    # 새 사용자 라고 하면 바로 db에 추가 (회원가입)
    if not user:
        user = User(google_id=google_id, email=email, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)

    # 우리 서버의 JWT 발급 (이 토큰은 이후 보호된 엔드포인트 호출 시 Authorization 헤더에 실려 돌아옴)
    access_token = create_access_token(user.id)

    # 이 반환 후 get_db의 finally 실행
    return OurJwtToFront(
        access_token=access_token,
        token_type="bearer",
        user=user,  # Pydantic이 User ORM 객체를 UserResponse로 자동 변환 (from_attributes=True)
    )
