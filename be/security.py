# JWT utilities: issuing access tokens at login and verifying them on protected routes.
# Used by auth router (token issuance) and any router that depends on `get_current_user_id`.
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXP_MINUTES = int(os.environ.get("JWT_EXP_MINUTES", "10080"))

# 프론트의 HTTP 요청 헤더 중 Authorization 헤더를 검사하여 토큰 추출.
# 즉, "Bearer" 접두사 검수 후, 접두사와 토큰 문자열을 분리하여 저장.
# auto_error = False -> Authorization 헤더가 없거나 Bearer 접두사가 아니면 FastAPI가 자동으로 403 Forbidden을 던짐
bearer_scheme = HTTPBearer(auto_error=False)


# user id를 넣으면 JWT 토큰을 발급해주는 함수
# 로그인이 성공했을 때 서버가 이 함수로 토큰을 만들어 프론트로 돌려줌
def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    
    # JWT 토큰 구조: 헤더 + payload + 서명
    payload = {
        "sub": str(user_id),                                                # 유저 식별자
        "iat": int(now.timestamp()),                                        # 발급 시각
        "exp": int((now + timedelta(minutes=JWT_EXP_MINUTES)).timestamp()), # 만료 시각
    }
    
    # 실제 토큰 문자열을 만든다. PyJWT 라이브러리가 알아서 헤더와 서명을 붙여줌.
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_user_id(credentials: str) -> int:
    try:
        payload = jwt.decode(
            credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        return int(payload["sub"])  # 유저 식별자 반환
    
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token elements (sub)")


# 요청 헤더의 JWT를 검증하고 유저 ID를 뽑아냄 (즉, 토큰을 풀어내는 함수) / 보호된 엔드포인트마다 이 함수가 매 요청 앞에 끼어들어서 검증함.
# HTTPAuthorizationCredentials: HTTPBearer가 요청 헤더에서 분리해놓은 인증 정보를 담아두는 데이터 객체
# Depends(): 이 함수가 콜 되면 자동으로 괄호 안의 변수 및 함수 실행
def get_user_id( auth: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),) -> int:
    # auth.scheme      -> "Bearer" 문자열 / auth.credentials -> 실제 토큰 문자열 (xxxxx.yyyyy.zzzzz)
    # "Bearer" + 토큰 = 헤더


    # 토큰 없으면 error raise
    # 로그인 된 사용자만 이용할수 있는 기능 위함
    if auth is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    return decode_user_id(auth.credentials)
