"""FastAPI app and SQLite persistence. One-process MVP; use Postgres/queue for high-scale deployment."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from .core import EvaluationError, demo_evaluate, jev_evaluate, generate_openai

BASE = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(BASE / "evaluations.db")))
app = FastAPI(title="Jev LLM Quality Tester", version="0.1.0")

class EvaluateRequest(BaseModel):
    question: str = Field(min_length=3, max_length=10000)
    answer: str | None = Field(default=None, max_length=20000)
    reference: str | None = Field(default=None, max_length=20000)
    engine: str = Field(default="demo", pattern="^(demo|jev)$")
    generator: str = Field(default="manual", pattern="^(manual|openai)$")
    model: str = Field(default="gpt-4.1-mini", max_length=100)

    @model_validator(mode="after")
    def check_answer(self):
        if self.generator == "manual" and not self.answer:
            raise ValueError("Answer is required for manual testing")
        return self

@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()

def initialize():
    with connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            question TEXT NOT NULL, answer TEXT NOT NULL, reference TEXT,
            generator TEXT NOT NULL, model TEXT, engine TEXT NOT NULL,
            scores TEXT NOT NULL, overall REAL NOT NULL, confidence REAL,
            status TEXT NOT NULL, note TEXT NOT NULL)""")

@app.on_event("startup")
def startup():
    initialize()

@app.get("/")
def index():
    return FileResponse(BASE / "web" / "index.html")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/evaluate")
async def evaluate(request: EvaluateRequest):
    try:
        answer = request.answer if request.generator == "manual" else await generate_openai(request.question, request.model)
        result = demo_evaluate(request.question, answer, request.reference) if request.engine == "demo" else await jev_evaluate(request.question, answer, request.reference)
    except EvaluationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    run_id = str(uuid.uuid4())
    with connection() as db:
        db.execute("""INSERT INTO runs (id, question, answer, reference, generator, model, engine, scores, overall, confidence, status, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (run_id, request.question, answer, request.reference, request.generator, request.model if request.generator == "openai" else "manual", result["engine"], json.dumps(result["scores"]), result["overall"], result["confidence"], result["status"], result["note"]))
    return {"id": run_id, "question": request.question, "answer": answer, "reference": request.reference, **result}

@app.get("/api/runs")
def runs(limit: int = 25):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    with connection() as db:
        data = db.execute("SELECT * FROM runs ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
    return [{**dict(item), "scores": json.loads(item["scores"])} for item in data]

@app.get("/api/runs/{run_id}")
def run(run_id: str):
    with connection() as db:
        value = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if value is None:
        raise HTTPException(status_code=404, detail="Unknown evaluation")
    return {**dict(value), "scores": json.loads(value["scores"])}
