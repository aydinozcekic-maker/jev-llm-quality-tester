# Jev LLM Quality Tester

**A runnable, GitHub-ready MVP for testing the quality of LLM-generated answers.**

The project provides a browser-based dashboard, a Python/FastAPI REST API, SQLite-backed evaluation history, an optional OpenAI answer generator, and a Jev/TypeSafe structured-scoring adapter. It also includes a no-key, deterministic **demonstration mode**, automated tests, Docker support, and GitHub Actions continuous integration.

> [!IMPORTANT]
> This is a **prototype**, not a calibrated quality benchmark or a production SaaS platform. The demonstration scores are lexical heuristics, not factual judgments. Jev scores are model-based rubric judgments, not independently verified truth. The available tests exercise application logic and mocked integrations; they do **not** validate production credentials, vendor availability, or evaluation accuracy.

## Contents

1. [What the product does](#what-the-product-does)
2. [Current scope and limitations](#current-scope-and-limitations)
3. [System architecture](#system-architecture)
4. [Requirements](#requirements)
5. [Quick start](#quick-start)
6. [Environment variables and keys](#environment-variables-and-keys)
7. [How to use the dashboard](#how-to-use-the-dashboard)
8. [REST API reference](#rest-api-reference)
9. [Scoring system and Jev integration](#scoring-system-and-jev-integration)
10. [Run tests and continuous integration](#run-tests-and-continuous-integration)
11. [Docker and deployment](#docker-and-deployment)
12. [Repository structure](#repository-structure)
13. [Security, privacy, and operational considerations](#security-privacy-and-operational-considerations)
14. [Troubleshooting](#troubleshooting)
15. [Production scalability roadmap](#production-scalability-roadmap)
16. [Updating and contributing](#updating-and-contributing)
17. [License and references](#license-and-references)

## What the product does

The goal is to make it easy for developers to examine answers produced by language models and assess them against explicit criteria.

Typical workflow:

1. Enter a user question (the test prompt).
2. Either paste an answer or generate an answer with the configured OpenAI model.
3. Optionally supply a reference answer for context.
4. Choose either **Demo** or **Jev** evaluation.
5. Review five dimension scores, the weighted overall score, review status, and evaluator confidence when available.
6. Inspect stored evaluation history through the dashboard/API.

Example use cases include experimenting with evaluation rubrics, testing integration of a structured judge, reviewing an individual response, and building a foundation for regression testing. Real cross-model leaderboards will require more work (see [roadmap](#production-scalability-roadmap)).

## Current scope and limitations

| Capability | MVP status | Notes |
| --- | --- | --- |
| Web dashboard | Implemented | Served directly by FastAPI as a static HTML page |
| Evaluate a pasted answer | Implemented | `generator: "manual"` |
| Generate an answer via OpenAI | Implemented, key required | Allowlisted Chat Completions model IDs |
| Jev rubric evaluation | Implemented adapter, key required | Vendor API schema must remain compatible |
| Demo evaluation without keys | Implemented | Illustrative lexical heuristics only |
| Five quality dimensions | Implemented | Accuracy, relevance, completeness, clarity, instruction following |
| SQLite evaluation history | Implemented | Single-instance prototype storage |
| REST API and OpenAPI docs | Implemented | `/docs` |
| Automated tests and CI | Implemented | Jev endpoint is mocked in unit tests |
| Live Claude/Gemini integrations | Not implemented | Future adapters |
| Automated multi-model comparison | Not implemented | Future benchmark-run orchestration |
| Validated factual verification / hallucination detection | Not implemented | Requires evidence and calibration |
| Authentication, multi-tenancy, rate limiting | Not implemented | Do not expose publicly as-is |
| Background job workers / PostgreSQL | Not implemented | Required for larger scale |

## System architecture

```text
Browser (web/index.html)
    |
    | HTTP
    v
FastAPI application (app/main.py)
    |-- GET /            -> dashboard
    |-- GET /health      -> health check
    |-- POST /api/evaluate
    |       |-- manual answer OR OpenAI generation (app/core.py)
    |       |-- demo scoring OR Jev scoring (app/core.py)
    |       `-- store result in SQLite
    |-- GET /api/runs   -> evaluation history
    `-- GET /api/runs/{id} -> individual stored run

External network services (only when explicitly selected):
    - OpenAI Chat Completions API for generation
    - Jev / TypeSafe API for evaluation
```

**Design choice:** The scoring implementation lives in `app/core.py`; request validation, routes, and SQLite persistence live in `app/main.py`. This is intentionally small and easy to extend. It is **not** currently a React frontend or a microservice architecture.

## Requirements

- Python **3.11 or 3.12** recommended (these versions are configured in CI).
- `pip` and a terminal.
- Internet access to install dependencies, and to use live OpenAI or Jev services.
- Optional: Docker with the Docker Compose plugin.
- Optional: OpenAI API key for generated answers.
- Optional: TypeSafe/Jev API key for live Jev evaluations.

## Quick start

### macOS / Linux

```bash
# Extract the ZIP and enter the repository
cd jev-llm-quality-tester
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
uvicorn app.main:app --reload
```

### Windows PowerShell

```powershell
cd jev-llm-quality-tester
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
uvicorn app.main:app --reload
```

If PowerShell blocks virtual environment activation, use Command Prompt and `.venv\Scripts\activate.bat`, or invoke `.venv\Scripts\python.exe` explicitly.

Open **http://localhost:8000** in a browser. Interactive REST documentation is at **http://localhost:8000/docs**.

No API key is needed to try the **demo** evaluator against an answer you enter yourself. Demo mode is deliberately not a scientific score and must not be used as a model quality ranking.

### Activate live providers

Copy the example configuration:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Fill in the desired credentials in `.env`. **The application does not automatically load `.env`** when you simply run `uvicorn app.main:app --reload`. Start with environment variables loaded, for example on bash:

```bash
set -a
source .env
set +a
uvicorn app.main:app --reload
```

Alternatively, install `python-dotenv` and use `uvicorn app.main:app --reload --env-file .env`. Docker Compose also supports the `.env` file as described below.

**Never commit `.env`, API keys, or real user prompts containing confidential information.**

## Environment variables and keys

| Name | Default / example | Purpose |
| --- | --- | --- |
| `TYPESAFE_API_KEY` | empty | Required for `engine: "jev"` |
| `JEV_MODEL` | `jev-latest` | Model value sent to the TypeSafe endpoint |
| `JEV_API_URL` | `https://api.typesafe.ai/v1/systemone` | Jev endpoint; confirm against current vendor docs |
| `REVIEW_CONFIDENCE` | `0.65` | If minimum dimension confidence is below threshold, mark for review |
| `OPENAI_API_KEY` | empty | Required for `generator: "openai"` |
| `ALLOWED_OPENAI_MODELS` | `gpt-4.1-mini,gpt-4.1` | Comma-delimited generation model allowlist |
| `DATABASE_PATH` | `./evaluations.db` in `.env.example` | SQLite filename; otherwise defaults to project-root `evaluations.db` |

The backend sends external provider credentials in request headers. They are not required by, or entered into, the browser UI. Vendor requests can incur external usage charges. Set provider budgets and review provider data-handling policies before using sensitive prompts.

## How to use the dashboard

1. Start the server, then open `http://localhost:8000`.
2. Enter a question of at least 3 characters.
3. For manual mode, provide an answer. For OpenAI generation, configure the OpenAI key and select an allowlisted model.
4. Add a reference answer when you have a trustworthy target response.
5. Choose `demo` to explore the interface without credentials, or `jev` to send a structured rubric evaluation to the configured Jev endpoint.
6. Submit. Review the returned dimension scores, overall score, status, confidence if available, and explanatory note.
7. Use evaluation history or the `/api/runs` API to inspect earlier results.

Demo results may look arbitrary for paraphrases because the implementation uses word overlap and simple length/punctuation signals. A semantically excellent answer can score poorly, and a wrong answer can score well. This is expected for a wiring demonstration.

## REST API reference

The application automatically exposes a Swagger/OpenAPI interface at `GET /docs` and a machine-readable specification at `GET /openapi.json`.

### `GET /health`

Simple process health indicator.

```bash
curl http://localhost:8000/health
```

Example response: `{"status":"ok"}`. Note that this endpoint does **not** check the external providers or database connectivity.

### `POST /api/evaluate`

Request body:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `question` | string | Yes | 3–10,000 characters |
| `answer` | string or null | When `generator=manual` | Manual answer, up to 20,000 characters |
| `reference` | string or null | No | Reference answer, up to 20,000 characters |
| `engine` | `demo` or `jev` | No | Defaults to `demo` |
| `generator` | `manual` or `openai` | No | Defaults to `manual` |
| `model` | string | No | Defaults to `gpt-4.1-mini`; used with OpenAI generation |

**Manual answer, no key needed:**

```bash
curl -X POST http://localhost:8000/api/evaluate \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "What is the capital of France?",
    "answer": "Paris is the capital of France.",
    "reference": "Paris.",
    "generator": "manual",
    "engine": "demo"
  }'
```

**Generate using OpenAI, then evaluate with Jev** (both API keys required):

```bash
curl -X POST http://localhost:8000/api/evaluate \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "Explain the purpose of an HTTP status code.",
    "reference": "An HTTP status code communicates the outcome of an HTTP request.",
    "generator": "openai",
    "model": "gpt-4.1-mini",
    "engine": "jev"
  }'
```

Response shape (values below are **illustrative**, not a recorded evaluation):

```json
{
  "id": "11111111-2222-4333-8444-555555555555",
  "question": "What is the capital of France?",
  "answer": "Paris is the capital of France.",
  "reference": "Paris.",
  "scores": {
    "accuracy": 100.0,
    "relevance": 80.0,
    "completeness": 80.0,
    "clarity": 80.0,
    "instruction_following": 80.0
  },
  "overall": 86.0,
  "confidence": null,
  "status": "demo_only",
  "engine": "deterministic_demo",
  "note": "Illustrative lexical heuristics only; NOT validated quality, factual accuracy or a Jev result."
}
```

The values in this example demonstrate the **response format only**. Do not interpret them as measured scores for the question.

Validation failures produce HTTP `422`. Missing API keys or network/provider errors are returned as HTTP `503` with a `detail` message. External failures are **not** silently replaced with demo results.

### `GET /api/runs?limit=25`

Returns stored evaluation records in reverse chronological order. `limit` must be between **1 and 100** inclusive.

```bash
curl 'http://localhost:8000/api/runs?limit=10'
```

### `GET /api/runs/{run_id}`

Fetches one stored evaluation by ID. Returns HTTP `404` if the ID does not exist.

```bash
curl http://localhost:8000/api/runs/REPLACE_WITH_EVALUATION_ID
```

**Data persistence:** The database saves prompts, full answers, optional references, score breakdowns, overall score, engine, generation model, confidence, status and notes. Treat stored data as potentially sensitive.

## Scoring system and Jev integration

### Rubric dimensions and weights

| Dimension | Weight | Interpreted as |
| --- | ---: | --- |
| Accuracy | 30% | Agreement with the provided reference, when one exists |
| Relevance | 25% | Responsiveness to the user question |
| Completeness | 20% | Coverage of requested aspects |
| Clarity | 10% | Readability and organisation |
| Instruction following | 15% | Compliance with explicit instructions |

Each Jev dimension is requested on a **0–5** rubric and normalized to **0–100** by multiplying by 20. The code calculates the weighted overall score:

```text
overall = round(
    0.30 * accuracy
  + 0.25 * relevance
  + 0.20 * completeness
  + 0.10 * clarity
  + 0.15 * instruction_following,
  1
)
```

Weights are in `app/core.py` as `WEIGHTS`; editing them changes future scores, not previously stored evaluations. Keep rubric versions alongside results before using this for serious comparative analysis.

### Live Jev request

When `engine=jev`, the backend sends an authenticated `POST` request to the configured `JEV_API_URL` with:

- The configured Jev model name.
- The question, candidate answer and reference (or a message indicating no reference was supplied).
- Five typed `score` questions, each with the same six-level rubric.

The integration expects an `answers` object containing all five dimensions, each with `type: "score"` and a numeric `score` between 0 and 5. Optional per-dimension `confidence` values must fall within 0–1. The code rejects malformed/out-of-range scores and calculates the reported confidence as the **minimum** of the five confidences, but only if all five are present and valid.

> Vendor schemas, model IDs, and endpoint behaviour can change. Confirm the current TypeSafe/Jev API documentation before using live credentials. The unit tests validate the adapter against **mocked** responses, not the live service.

### Review statuses

| Status | Trigger | How to treat it |
| --- | --- | --- |
| `demo_only` | Deterministic demo evaluator | UI demonstration; not a benchmark result |
| `evaluated` | Jev returned complete confidence, met threshold, and a reference was present | Model judgment; still requires independent verification for factual truth |
| `review` | Jev confidence missing/low or reference absent | Flagged for additional review; **not** automatically re-evaluated |

The `REVIEW_CONFIDENCE` setting is a routing threshold for the **status flag only**. This MVP does not yet send cases to a second judge or human reviewer. Evaluator confidence is a reported model signal, **not** a calibrated probability of correctness.

### Improving evaluation validity

For trustworthy benchmarking, add expert-labelled examples, provenance for reference answers, retrieval-backed claim verification, known adversarial tests, and inter-rater agreement measurements. Compare Jev judgments with human reviews, calculate error rates, and freeze rubric and dataset versions. Add holdout datasets to avoid overfitting an evaluation prompt to a public benchmark.

## Run tests and continuous integration

From the project root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests are in `tests/test_core.py` and `tests/test_api.py`, with fixtures in `tests/conftest.py`. They cover scoring logic, input and API behaviour, persistence, and mocked provider interaction. The Jev tests **do not** call the live endpoint and cannot establish real-world judge validity.

GitHub Actions workflow: `.github/workflows/ci.yml`.

- Triggered on pushes and pull requests.
- Runs on Ubuntu with Python **3.11 and 3.12**.
- Installs development requirements and executes `python -m pytest -q`.

**Before publishing:** always rerun tests locally and confirm the Actions tab is green on the remote repository. A green CI run proves the checked behaviours passed, not that external APIs are configured or that reported quality scores are correct.

## Docker and deployment

From the repository root:

```bash
# Optional: create .env and add live service keys
cp .env.example .env

docker compose up --build
```

Open `http://localhost:8000`. The Compose configuration maps port `8000` to the container and uses a named volume (`data`) for SQLite data at `/data/evaluations.db`. `env_file` is optional, so demo mode can start without credentials. Your Docker Compose version must support the `env_file` mapping syntax used in `docker-compose.yml`.

Stop the stack with:

```bash
docker compose down
```

To delete the **stored volume and evaluations**, run `docker compose down -v`. This permanently removes data in that Compose-managed volume; use with caution.

**Deployment warning:** this container is for local demonstration and controlled internal testing. Before exposing it to untrusted traffic, add authentication, authorization, TLS, request throttling, security monitoring, secret management, and explicit data retention/deletion controls.

## Repository structure

```text
jev-llm-quality-tester/
├── .env.example                # Configuration template (no real secrets)
├── .github/workflows/ci.yml   # Automated CI tests
├── .gitignore                  # Files excluded from Git
├── Dockerfile                  # Application container
├── LICENSE                     # MIT license
├── README.md                   # This guide
├── app/
│   ├── __init__.py
│   ├── core.py                  # Demo scoring, Jev adapter, OpenAI generation
│   └── main.py                  # FastAPI, validation, routes, SQLite history
├── docker-compose.yml         # App service and persistent SQLite volume
├── requirements.txt           # Runtime Python dependencies
├── requirements-dev.txt       # Runtime + test dependencies
├── tests/
│   ├── conftest.py             # Shared test fixtures
│   ├── test_api.py             # Endpoint/persistence tests
│   └── test_core.py            # Scoring/provider-adapter tests
└── web/
    └── index.html             # Browser dashboard
```

Generated directories such as `__pycache__/`, `.pytest_cache/`, virtual environments, and local SQLite databases should not be committed. Keep secrets out of Git history.

## Security, privacy, and operational considerations

The initial application has **no authentication**. Anyone who can reach its HTTP endpoints could submit prompts, invoke configured paid APIs, and read stored evaluation history. Therefore, bind it to a trusted environment only until protective controls are implemented.

Before deployment, at minimum:

1. **Authentication and authorization:** require login/API keys; protect history by tenant/user.
2. **Request controls:** add rate limits, concurrency limits, quotas and provider spend ceilings.
3. **Data privacy:** define retention, deletion, encryption, backups, and redaction rules. Do not send private/sensitive prompts to vendors without suitable agreements.
4. **Secrets:** use deployment secret managers; rotate leaked keys; never log tokens.
5. **Network protection:** HTTPS/TLS termination, restrictive CORS and ingress rules.
6. **Availability:** instrument timeouts, retry/backoff policy for transient errors, and service health checks.
7. **Observability:** log correlation IDs, latency, cost, model/rubric versions and failure rates, while minimizing personal data.
8. **Evaluation governance:** treat untrusted prompt/answer/reference text as data; test resistance to prompt injection and evaluation gaming.

Current request field size limits offer basic validation but are not substitutes for these protections.

## Troubleshooting

**The web page does not open.** Confirm Uvicorn is running, you are in the repository root, and port 8000 is available. Try `http://127.0.0.1:8000/health`.

**`ModuleNotFoundError` when starting.** Activate the intended virtual environment and reinstall `requirements-dev.txt`. Run Uvicorn from the project root.

**Jev reports `TYPESAFE_API_KEY not configured`.** Create `.env` and **load it into the process environment** before starting Uvicorn. Simply placing `.env` in the directory is not enough with the default command.

**OpenAI generation reports `OPENAI_API_KEY not configured`.** Configure and load the key, then restart the process.

**The model is not allowed.** Add the desired supported model ID to `ALLOWED_OPENAI_MODELS`, and check that your OpenAI account can use it. The request uses OpenAI Chat Completions, not the Responses API.

**Jev returns HTTP 503.** Check credentials, configured endpoint/model, vendor availability and whether the vendor response still matches the adapter schema. External errors intentionally do not fall back to demo scoring.

**Scores appear incorrect.** Confirm you did not choose `demo`. Lexical demo scoring is illustrative only. Even a live Jev score is a rubric estimate; add trusted references and human validation.

**History is missing after restart.** Check `DATABASE_PATH`. Local Python and Docker Compose use different database locations; Docker stores data in a named volume.

**GitHub Actions fails but local tests pass.** Compare Python versions, dependencies, path assumptions and environment variables. The default automated suite is intended to run without external API secrets.

## Production scalability roadmap

Proposed sequence, **not currently shipped functionality**:

| Phase | Deliverables | Acceptance criteria |
| --- | --- | --- |
| 1. Hardening | Authentication, rate limiting, structured logs, secrets management | No anonymous access to provider calls or history |
| 2. Reliable data | PostgreSQL, migrations, tenant isolation, rubric/dataset versioning | Reproducible, tenant-scoped results under concurrent writes |
| 3. Async evaluation | Redis + worker pool, job IDs, retries, timeouts, idempotency | Large batch jobs survive worker restarts |
| 4. Multi-model adapters | Anthropic, Gemini, configurable OpenAI models | Same dataset evaluated through standard provider interfaces |
| 5. Benchmarking | Dataset uploads, golden answers, side-by-side comparisons, export | Repeatable model-level metrics and test reports |
| 6. Calibration | Human-rated ground truth, claim-level evidence checks, calibration metrics | Documented judge agreement and measured false-positive/negative rates |
| 7. CI quality gates | Baselines, regression thresholds, pull-request reports | Deterministic pass/fail policies with interpretable evidence |
| 8. Operability | Dashboards, spend tracking, autoscaling, incident alerts | Auditable latency, throughput, error and cost targets |

Potential model-comparison metrics: quality by dimension, pass rate on gold sets, latency distributions, cost per answer/evaluation, judge-human agreement, and version-to-version regression. A ranking should not be treated as scientifically meaningful without representative datasets and controls for judge bias.

## Updating and contributing

### Recommended edit workflow

1. Create a new Git branch for changes.
2. Modify one component at a time (`app/core.py` for rubric/scoring, `app/main.py` for API/data, `web/index.html` for UI).
3. Add or update tests to specify expected behaviour.
4. Run `python -m pytest -q` locally.
5. Update this README if any public command, API field, scoring rule or configuration changes.
6. Commit and open a GitHub pull request; ensure CI passes before merging.

### Create a GitHub repository

Install and log in to GitHub CLI (`gh`) if needed, then from the extracted project directory:

```bash
git init
git add .
git commit -m "Initial Jev LLM Quality Tester"
gh repo create jev-llm-quality-tester --public --source=. --push
```

This repository is distributed as a ZIP; **creating the ZIP does not publish anything to GitHub**. Choose `--private` instead of `--public` if you do not intend public distribution. Inspect staged files with `git status` before committing.

### Suggested first contributions

- Add a model/provider registry and support for more generation endpoints.
- Make evaluation rubric and weights configurable with version IDs.
- Add batch evaluation jobs and a dataset import/export format.
- Introduce PostgreSQL migrations, tenant identity and authentication.
- Add formal reliability and validity evaluation based on human-labeled datasets.
- Extend CI with static analysis, security checks and integration test environments.

## License and references

MIT License. See [`LICENSE`](LICENSE).

- TypeSafe/Jev documentation: https://docs.typesafe.ai/
- TypeSafe/Jev guide (secondary reference): https://typesafe-jev.com/en/guides/api/
- FastAPI documentation: https://fastapi.tiangolo.com/
- Pytest documentation: https://docs.pytest.org/

Vendor documentation may change; prefer the vendor's official API specification when verifying live integration requests.
