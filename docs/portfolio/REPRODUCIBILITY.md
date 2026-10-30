# CreatorOS — Reproduce the Evidence

The headline suite is **142 tests**. Always report collection separately from
execution, and publish the actual result rather than editing a result to match
the headline. Historical subset reports keep their original counts.

## Local application setup

Prerequisites: Python 3.11+ (collection checked with 3.12), Node/Expo tooling,
MongoDB, and access to the Emergent integration dependency. Start from a clean
checkout. Use a disposable database, not a production database.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Configure MongoDB and the LLM key privately in `backend/.env`. Start MongoDB
using your local installation, then run from `backend/`:

```bash
uvicorn server:app --host 0.0.0.0 --port 8001
```

In another terminal, from `frontend/`:

```bash
npm install
npx expo start --web
```

The backend URL must be reachable from the device/browser running the frontend.
The examples use port 8001 to match the integration tests; the README's plain
`uvicorn` command otherwise defaults to a different port. CORS must include the
frontend origin. Google sign-in also depends on the existing external auth
integration; a clean self-hosted setup is not fully verified by these commands.

Real `.env` files remain ignored. Configure secrets through the deployment
platform; do not commit keys. `DEMO_MODE=false` is the safe default. Enable demo
checkout only in an isolated local demo environment. Provider API code being
present does not mean its credentials or live checkout have been validated.

## Checks without a live backend

```bash
python scripts/check_portfolio.py
```

This checks the curated evidence links, configuration examples and Python
syntax. It does not execute application behaviour or validate web demo links.

To collect functional tests, install the collection-only requirements and set
local placeholder connection values; collection does not execute fixtures:

```bash
python -m pip install -r backend/requirements-collection.txt
cd backend
export MONGO_URL=mongodb://127.0.0.1:27017
export DB_NAME=creatoros_collection_only
export EXPO_PUBLIC_BACKEND_URL=http://127.0.0.1:8001
python -m pytest tests --collect-only -q
```

The CI workflow runs this collection check and uploads its output. A passing
collection check means tests are discoverable/importable, not that they passed.

## Functional/integration execution

The test suite includes live HTTP calls, MongoDB fixture writes, LLM calls,
Razorpay test-mode calls, and environment-specific service restarts. It is not
a hermetic, zero-cost unit suite. Some security tests refer to `/app/backend`
and `supervisorctl`; inspect those assumptions before running elsewhere.

Use an isolated deployment with matching MongoDB/DB_NAME, port 8001, appropriate
test-mode provider credentials and an LLM key. Never point tests at customer
data. Then, from `backend/` in the configured environment:

```bash
python -m pytest tests/ -v --junitxml=../test_reports/pytest/current.xml
```

Record commit, environment, UTC timestamp, dependency versions, collected
count, pass/fail/skip totals and limitations. Do not upload unredacted test
output containing session tokens, user details or provider payloads.

## Semantic AI evaluations (manual, may incur cost)

`backend/pytest.ini` recognises both `test_*.py` and `eval_*.py`; default
`testpaths = tests` keeps the semantic suite opt-in. Install full application
dependencies and configure an isolated running backend and database first.

```bash
cd backend
python -m pytest evals/ --collect-only -q
python -m pytest evals/ -v -s --junitxml=../test_reports/pytest/evals-current.xml
```

These commands write fixtures and make real LLM calls when executed. The
pytest dotenv setup supplies backend/frontend values; an exported environment
variable takes precedence. No paid evaluations run automatically in CI.

For each repeated run, use the [run template](evidence/RUN_TEMPLATE.md). Preserve
redacted input portfolios, complete outputs, rubric scores and failure reasons.
Use distinct run IDs, record model identifiers/settings, include failures and
skips, and review a sample manually. Do not claim the historical six-run results
were reproduced until the new run artifacts exist.

## Verification record

See [this revision's verification](evidence/verification.md). Clean installation,
full integration execution, live demo availability and paid eval results are
separate checks; none should be inferred from static validation or collection.
