# Grads Foundry — Orders API (template repo)

This is the repo every student's Loop 1 ticket starts from. It's a real, small
Express API — not a "hello world." Your job on Day 1 is to pick up the ticket
in the tracker, make the change it describes, and get it live.

## What's here

- `server.js` — the app. Two routes: `GET /health`, `GET /orders`.
- `test/` — tests that run in CI before anything gets built or deployed.
- `Dockerfile` — how the app gets packaged (includes the AWS Lambda Web
  Adapter, so it runs on Lambda without being rewritten as a Lambda handler).
- `.github/workflows/ci-cd.yml` — the pipeline: test → build & push the image
  to ECR → deploy to AWS Lambda → verify the redeploy is actually healthy
  before the run is allowed to succeed. Creates your ECR repo and Lambda
  function for you on the very first run — see `infra/DESIGN.md`.

## Running it locally

```
npm install
npm test
npm start        # http://localhost:3000/health
```

Or as a container:

```
docker build -t orders-api .
docker run -p 3000:8080 orders-api   # container listens on 8080 (Lambda Web Adapter default)
```

## How you get "access" to the sandbox

There's no separate signup step. Your first push to `main` (or running the
workflow manually from the Actions tab) *is* the onboarding step — it
triggers the pipeline, which authenticates to AWS via GitHub's OIDC
federation (no AWS keys ever handed to you) and deploys your own
namespaced copy of this app. Same motion a working engineer uses on day one:
push code, watch the pipeline run, get something live.

## Repo secrets/variables this pipeline expects

The ECR repo and Lambda function names are derived automatically from this
repo's own name — nothing to set for those. What's left:

| Name | Type | Scope | What it is |
|---|---|---|---|
| `AWS_ROLE_ARN` | secret | per-repo | This student's scoped deploy role — set by `infra/provision-student.sh`, not by hand |
| `AWS_REGION` | variable | org-level | e.g. `ap-south-1` |
| `LAMBDA_EXECUTION_ROLE_ARN` | variable | org-level | The shared role Lambda itself runs as — set once by `infra/bootstrap-org.sh` |
| `COHORT_TAG` | variable | org-level | e.g. `pilot-2026-10` — used for cost tracking, not identity |

See `infra/DESIGN.md` for the full picture of what gets created in AWS and why.
