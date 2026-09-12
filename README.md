# Grads Foundry — Payments Service (template repo)

This is the app every student's tickets land against. It's a real, small,
**already-running** payments API — Python (FastAPI) backed by Postgres, with
a static frontend — not a from-scratch build. Sprint 1's ticket is to add a
real feature to it; Sprint 2's is to fix a bug in what you just shipped.

Read `main.py` before doing anything else. `POST /api/payments` is the
reference pattern for the rest of this system — study how it handles two
things every real payments API has to get right:

1. **Idempotency.** Every request carries an `Idempotency-Key` header. Retry
   the same request with the same key (e.g. because your first attempt
   timed out) and you get back the *original* result — the money moves
   once, not twice.
2. **Safe concurrent balance updates.** Both accounts involved get
   row-locked, always in the same order, before either balance changes —
   otherwise two transfers between the same two accounts running at the
   same time can corrupt both balances, or deadlock each other.

Both are proven by tests, not just claimed — see `tests/test_api.py`.

## What's here

- `main.py` — the API: `GET /api/health`, `GET /api/accounts/{id}`, `POST /api/payments`, `GET /api/payments/{id}`.
- `frontend/index.html` — a bare page listing account balances.
- `tests/` — run against a real Postgres in CI, not mocked.
- `Dockerfile` — packages the app as a normal, long-lived HTTP service.
- `.github/workflows/ci-cd.yml` — every push to `main` builds, tests
  against a real database, and deploys straight to your **dev** environment.
- `.github/workflows/promote-to-prod.yml` — fires when a PR into the
  protected `prod` branch is merged, and ships the *exact* image already
  verified in dev to **prod**. That merge approval is your change ticket.

## Sprint 1 ticket (once the sandbox exists)

Add payment disputes: a way to flag a completed payment as disputed and
attach evidence.

- `POST /api/payments/{id}/disputes` — open a dispute, with an uploaded
  file (receipt/screenshot) stored in S3.
- `GET /api/payments/{id}/disputes` — return the dispute's status and a
  presigned download URL for the evidence.

Think about real edge cases before you code: can a payment be disputed
twice? What happens if the payment doesn't exist, or isn't `completed` yet?
Does re-uploading replace the evidence or reject the request? This is real
API design, not filled-in boilerplate.

## Running it locally

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/                      # works without a database at all
DATABASE_URL=postgresql://... uvicorn main:app --reload   # with one
```

Or with a real local Postgres via Docker:

```
docker run -d --rm --name gf-pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=gradsfoundry -p 5432:5432 postgres:16-alpine
DATABASE_URL=postgresql://postgres:test@localhost:5432/gradsfoundry uvicorn main:app --reload
```

Or as a container:

```
docker build -t payments-api .
docker run -p 8080:8080 -e DATABASE_URL=... payments-api
```

Try the idempotency guarantee yourself:

```
curl -X POST localhost:8080/api/payments -H "Idempotency-Key: test-1" \
  -H "Content-Type: application/json" \
  -d '{"from_account_id":1,"to_account_id":2,"amount_cents":500}'
# run the exact same command again -- same payment comes back, balance doesn't move twice
```

## How you get "access" to the sandbox

There's no separate signup step. Your first push to `main` *is* the
onboarding step — it builds, tests against a real database, and deploys to
your own `dev` environment. To go live: open a PR from `main` into `prod`
and request review — once it's approved and merged, `prod` updates
automatically to that exact tested build.

## Repo secrets/variables this pipeline expects

Per-student identity aside, most of this is org-level and set once:

| Name | Type | Scope | What it is |
|---|---|---|---|
| `AWS_ROLE_ARN` | secret | per-repo | This student's scoped deploy role (both dev and prod) |
| `AWS_REGION` | variable | org-level | e.g. `ap-south-1` |
| `ECS_CLUSTER` | variable | org-level | The shared cluster name |
| `COHORT_TAG` | variable | org-level | e.g. `pilot-2026-10` — cost tracking only |
| `DEV_BASE_URL` / `PROD_BASE_URL` | variable | per-repo | This student's CloudFront URL for each environment, used only by the post-deploy smoke test |
