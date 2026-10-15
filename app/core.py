"""Evaluation rules and Jev adapter. Demo scores are illustrative, never model judgments."""
import os
from typing import Any
import httpx

DIMENSIONS = ("accuracy", "relevance", "completeness", "clarity", "instruction_following")
WEIGHTS = {"accuracy": .30, "relevance": .25, "completeness": .20, "clarity": .10, "instruction_following": .15}
LEVELS = ["0 - Does not meet criterion", "1 - Very poor", "2 - Poor", "3 - Partially meets", "4 - Good", "5 - Fully meets"]

class EvaluationError(Exception):
    pass

def questions() -> dict:
    descriptions = {
        "accuracy": "Factual accuracy compared with the supplied reference answer. If no reference exists, do not assume truth.",
        "relevance": "How directly the answer responds to the user question.",
        "completeness": "Whether necessary aspects of the question are addressed.",
        "clarity": "How understandable and well organized the answer is.",
        "instruction_following": "Whether explicit requirements in the question are followed.",
    }
    return {key: {"type": "score", "instructions": value, "criteria": LEVELS} for key, value in descriptions.items()}

def weighted_score(scores: dict[str, float]) -> float:
    if set(scores) != set(DIMENSIONS):
        raise ValueError("Exactly five dimension scores required")
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not 0 <= v <= 100 for v in scores.values()):
        raise ValueError("Scores must be between 0 and 100")
    return round(sum(scores[k] * WEIGHTS[k] for k in DIMENSIONS), 1)

def extract_scores(payload: dict[str, Any]) -> tuple[dict[str, float], float | None]:
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise EvaluationError("Jev response missing answers")
    scores = {}
    confidences = []
    for dimension in DIMENSIONS:
        answer = answers.get(dimension)
        if not isinstance(answer, dict) or answer.get("type") != "score":
            raise EvaluationError(f"Invalid Jev score field: {dimension}")
        raw = answer.get("score")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not 0 <= raw <= 5:
            raise EvaluationError(f"Jev score out of bounds: {dimension}")
        scores[dimension] = round(raw * 20, 1)
        confidence = answer.get("confidence")
        if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and 0 <= confidence <= 1:
            confidences.append(confidence)
    return scores, round(min(confidences), 3) if len(confidences) == len(DIMENSIONS) else None

def demo_evaluate(question: str, answer: str, reference: str | None) -> dict:
    """Deterministic preview, explicitly NOT a factual or Jev assessment."""
    qwords = set(question.lower().split())
    awords = set(answer.lower().split())
    overlap = len(qwords & awords) / max(len(qwords), 1)
    reference_words = set((reference or "").lower().split())
    ref_overlap = len(reference_words & awords) / max(len(reference_words), 1) if reference else 0
    scores = {
        "accuracy": round(ref_overlap * 100, 1) if reference else 0,
        "relevance": round(min(100, overlap * 100), 1),
        "completeness": round(min(100, len(awords) * 4), 1),
        "clarity": round(min(100, (60 if '.' in answer else 40) + min(len(awords), 20)), 1),
        "instruction_following": round(min(100, overlap * 100), 1),
    }
    return {"scores": scores, "overall": weighted_score(scores), "confidence": None, "status": "demo_only", "engine": "deterministic_demo", "note": "Illustrative lexical heuristics only; NOT validated quality, factual accuracy or a Jev result."}

async def jev_evaluate(question: str, answer: str, reference: str | None, *, client: httpx.AsyncClient | None = None) -> dict:
    key = os.getenv("TYPESAFE_API_KEY")
    if not key:
        raise EvaluationError("TYPESAFE_API_KEY not configured")
    payload = {"model": os.getenv("JEV_MODEL", "jev-latest"), "state": {"question": question, "answer": answer, "reference_answer": reference or "Not supplied; factual accuracy cannot be verified without evidence."}, "questions": questions()}
    url = os.getenv("JEV_API_URL", "https://api.typesafe.ai/v1/systemone")
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=30.0)
    try:
        response = await client.post(url, json=payload, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        response.raise_for_status()
        scores, confidence = extract_scores(response.json())
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise EvaluationError(f"Jev API failed or returned invalid data: {type(exc).__name__}") from exc
    finally:
        if owns_client:
            await client.aclose()
    status = "review" if confidence is None or confidence < float(os.getenv("REVIEW_CONFIDENCE", ".65")) or not reference else "evaluated"
    return {"scores": scores, "overall": weighted_score(scores), "confidence": confidence, "status": status, "engine": "jev", "note": "Rubric-based model judgment; factual correctness requires independent evidence."}

async def generate_openai(question: str, model: str) -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise EvaluationError("OPENAI_API_KEY not configured")
    allowed = {s.strip() for s in os.getenv("ALLOWED_OPENAI_MODELS", "gpt-4.1-mini,gpt-4.1").split(",")}
    if model not in allowed:
        raise EvaluationError("Model not in ALLOWED_OPENAI_MODELS")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            result = await client.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json={"model": model, "messages": [{"role": "user", "content": question}]})
            result.raise_for_status()
            return result.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise EvaluationError(f"Generation failed: {type(exc).__name__}") from exc
