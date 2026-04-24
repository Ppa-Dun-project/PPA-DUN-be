import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from vertexai import init as vertexai_init
from vertexai.generative_models import GenerativeModel

load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
VERTEX_AI_MODEL = os.getenv("VERTEX_AI_MODEL", "gemini-2.5-flash")

router = APIRouter(prefix="/api/compare", tags=["ai"])

_model: Optional[GenerativeModel] = None


def _get_model() -> GenerativeModel:
    global _model
    if _model is None:
        if not GCP_PROJECT_ID:
            raise HTTPException(status_code=500, detail="GCP_PROJECT_ID not configured")
        vertexai_init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
        _model = GenerativeModel(VERTEX_AI_MODEL)
    return _model


class PlayerInput(BaseModel):
    name: str
    ppaValue: float
    recommendedBid: int
    stats: dict


class CompareRequest(BaseModel):
    playerA: PlayerInput
    playerB: PlayerInput


class CompareResponse(BaseModel):
    recommendation: str


def _value_per_dollar(p: PlayerInput) -> Optional[float]:
    if p.recommendedBid <= 0:
        return None
    return round(p.ppaValue / p.recommendedBid, 3)


def _build_prompt(a: PlayerInput, b: PlayerInput) -> str:
    return (
        "Compare these two MLB fantasy baseball players and recommend which is the "
        "better draft pick in 2-3 concise sentences. Focus on value per dollar "
        "and key stats.\n\n"
        f"Player A: {a.name}\n"
        f"  PPA Value: {a.ppaValue}\n"
        f"  Recommended Bid: ${a.recommendedBid}\n"
        f"  Value Per Dollar: {_value_per_dollar(a)}\n"
        f"  Stats: {a.stats}\n\n"
        f"Player B: {b.name}\n"
        f"  PPA Value: {b.ppaValue}\n"
        f"  Recommended Bid: ${b.recommendedBid}\n"
        f"  Value Per Dollar: {_value_per_dollar(b)}\n"
        f"  Stats: {b.stats}\n"
    )


@router.post("/ai-recommend", response_model=CompareResponse)
def ai_recommend(payload: CompareRequest) -> CompareResponse:
    model = _get_model()
    prompt = _build_prompt(payload.playerA, payload.playerB)
    try:
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Vertex AI error: {exc}") from exc

    if not text:
        raise HTTPException(status_code=502, detail="Vertex AI returned empty response")

    return CompareResponse(recommendation=text)
