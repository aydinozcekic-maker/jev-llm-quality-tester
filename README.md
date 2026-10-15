# Jev LLM Quality Tester

A runnable GitHub-ready MVP to score LLM answers on **accuracy, relevance, completeness, clarity, and instruction following**. The FastAPI backend stores evaluations in SQLite, serves a responsive dashboard, and supports a live **Jev / TypeSafe** adapter and optional OpenAI answer generation.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\\Scripts\\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000. Demo evaluation works without keys, but is **only illustrative lexical heuristics**, not validated answer quality. To enable Jev and/or OpenAI, copy `.env.example` to `.env`, set credentials, and **export the variables** to the process (e.g. `set -a; source .env; set +a` on bash) before starting Uvicorn. The application does **not** automatically read `.env`. Alternatively run `uvicorn app.main:app --env-file .env` (requires `python-dotenv`) or `docker compose up --build` after populating `.env`.

## Run tests

```bash
python -m pytest -q
```

Tests mock the Jev network endpoint; they do **not** prove live Jev credentials, response quality, API billing, deployment, or external-provider connectivity. CI runs Python 3.11 and 3.12.

## API

- `GET /health`
- `POST /api/evaluate` accepts `{ "question": "...", "answer": "...", "reference": "...", "engine": "demo|jev", "generator": "manual|openai", "model": "gpt-4.1-mini" }`
- `GET /api/runs?limit=25`
- `GET /api/runs/{id}`
- `GET /docs` for interactive API documentation.

Example:

```bash
curl -X POST http://localhost:8000/api/evaluate -H 'Content-Type: application/json' -d '{"question":"Capital of France?","answer":"Paris.","reference":"Paris.","engine":"demo"}'
```

## Evaluation and safety model

- Jev is called via `POST https://api.typesafe.ai/v1/systemone` with five typed `score` questions on a 0–5 rubric. Scores are normalized to 0–100 and combined with explicit weights (accuracy 30%, relevance 25%, completeness 20%, clarity 10%, instruction following 15%).
- Jev scores are *subjective rubric assessments*, not established factual truth. Reference answers improve context but do not independently verify factual claims. Missing reference or low confidence moves status to `review`; it does not invent certainty.
- Demo mode uses transparent, simplistic lexical metrics and is always labeled `demo_only`. **Do not use demo scores for benchmarking or model selection.**
- API keys are server-only. Never commit `.env`. Configure rate limiting, authentication, PII retention rules, request size governance, TLS, and audit controls before exposing the service publicly.
- External API failures return errors; they do not silently switch to demo scores.

## Architecture

```
Browser dashboard ──→ FastAPI ──→ (manual answer OR OpenAI generator)
                            └──→ (deterministic demo OR Jev live scoring)
                            └──→ SQLite evaluations history
```

The MVP is single-process SQLite with synchronous persistence, suited for local prototyping. Scaling roadmap: Postgres migrations, Redis-backed job workers, provider abstraction, per-tenant auth, evaluation dataset/version tracking, golden-set calibration, benchmark comparisons, budget controls, observability, and pull-request quality gates.

## Jev reference

TypeSafe official documentation: https://docs.typesafe.ai/ — API endpoint and request format described at https://typesafe-jev.com/en/guides/api/ (independent documentation). Check vendor docs for future API changes.

## License

MIT; see LICENSE.
