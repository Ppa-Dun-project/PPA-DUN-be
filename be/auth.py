import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests
from pydantic import BaseModel
from dotenv import load_dotenv

from db.session import get_db
from db.models import User

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


# ── Helper: verify Google token ───────────────────────────────────────────────

def _verify_google_token(token: str) -> dict:
    """
    Verify a Google ID token and return the decoded payload.
    Raises HTTP 401 if the token is invalid or expired.
    """
    try:
        return id_token.verify_oauth2_token(
            token, requests.Request(), GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")


# ── POST /api/auth/google/verify ──────────────────────────────────────────────

@router.post("/google/verify", response_model=UserResponse)
def google_login(req: GoogleLoginRequest, db: Session = Depends(get_db)):
    """
    Verify a Google ID token and return the corresponding user record.
    If the user does not exist yet, create a new record (upsert pattern).
    """
    idinfo = _verify_google_token(req.credential)

    google_id = idinfo["sub"]
    email = idinfo["email"]
    name = idinfo.get("name", "")

    # Look up by google_id — stable unique ID from Google
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = User(google_id=google_id, email=email, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
