# JWT utilities: issuing access tokens at login and verifying them on protected routes.
# Used by auth router (token issuance) and any router that depends on `get_current_user_id`.
import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXP_MINUTES = int(os.environ.get("JWT_EXP_MINUTES", "10080"))

# FastAPI가 내장으로 제공하는 Authorization 헤더 parser
# 즉, "Bearer" 접두사를 떼고 토큰 문자열만 뽑아줌.
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


# 요청 헤더의 JWT를 검증하고 유저 ID를 뽑아냄 (즉, 토큰을 풀어내는 함수)
# 보호된 엔드포인트마다 이 함수가 매 요청 앞에 끼어들어서 검증함.
# Depends(): 이 함수가 콜 되면 자동으로 괄호 안의 변수 및 함수 실행
def get_current_user_id(
    auth: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> int:
    # auth는 Authorization 헤더를 읽어서 만든 값이 들어감. HTTPAuthorizationCredentials 타입이거나 None일 수 있음.
    # auth.scheme      -> "Bearer" 문자열
    # auth.credentials -> 실제 토큰 문자열 (xxxxx.yyyyy.zzzzz)
    # "Bearer" + 토큰 = 헤더

    if auth is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    try:
        payload = jwt.decode(
            auth.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return int(payload["sub"])
