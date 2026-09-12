# Grads Foundry — Orders Service (template repo)

This is the app every student's tickets land against. It's a real, small,
**already-running** web app — Python (FastAPI) API + a static frontend,
backed by Postgres — not a from-scratch build. Sprint 1's ticket is to add
a real feature to it; Sprint 2's is to fix a bug in what you just shipped.

## What's here

- `main.py` — the API. `GET /api/health`, `GET /api/orders`, `GET /api/orders/{id}`.
- `frontend/index.html` — a bare page that calls the API and lists orders.
- `tests/` — run against a real Postgres in CI, not mocked.
- `Dockerfile` — packages the app as a normal, long-lived HTTP service.
- `.github/workflows/ci-cd.yml` — every push to `main` builds, tests
  against a real database, and deploys straight to your **dev** environment.
- `.github/workflows/promote-to-prod.yml` — fires when a PR into the
  protected `prod` branch is merged, and ships the *exact* image already
  verified in dev to **prod**. That merge approval is your change ticket.

## Sprint 1 ticket (once the sandbox exists)

Add order attachments: a way to upload a receipt/invoice file for an order
and get it back later.

- `POST /api/orders/{id}/attachments` — upload a file, store it in S3.
- `GET /api/orders/{id}/attachments` — return a presigned download URL.
- Add the upload button and a download link to `frontend/index.html`
  (there's a placeholder "Attachment" column already there).

This is real API design, not filled-in boilerplate: think about the request
shape, what status codes make sense, and what happens if someone re-uploads.

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
docker build -t orders-api .
docker run -p 8080:8080 -e DATABASE_URL=... orders-api
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
