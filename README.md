# Grads Foundry — Orders API (template repo)

This is the repo every student's Loop 1 ticket starts from. It's a real, small
Express API — not a "hello world." Your job on Day 1 is to pick up the ticket
in the tracker, make the change it describes, and get it live.

## What's here

- `server.js` — the app. Two routes: `GET /health`, `GET /orders`.
- `test/` — tests that run in CI before anything gets built or deployed.
- `Dockerfile` — how the app gets packaged.
- `.github/workflows/ci-cd.yml` — the pipeline: test → build & push the image
  to ECR → deploy to AWS Lambda → verify the redeploy is actually healthy
  before the run is allowed to succeed.

## Running it locally

```
npm install
npm test
npm start        # http://localhost:3000/health
```

Or as a container:

```
docker build -t orders-api .
docker run -p 3000:3000 orders-api
```

## How you get "access" to the sandbox

There's no separate signup step. Your first push to `main` (or running the
workflow manually from the Actions tab) *is* the onboarding step — it
triggers the pipeline, which authenticates to AWS via GitHub's OIDC
federation (no AWS keys ever handed to you) and deploys your own
namespaced copy of this app. Same motion a working engineer uses on day one:
push code, watch the pipeline run, get something live.

## Repo secrets/variables this pipeline expects

Set once per repo (or once at the org level once there's more than one):

| Name | Type | What it is |
|---|---|---|
| `AWS_ROLE_ARN` | secret | IAM role the GitHub Actions OIDC token assumes |
| `AWS_REGION` | variable | e.g. `ap-south-1` |
| `ECR_REPOSITORY` | variable | ECR repo name for this app's images |
| `LAMBDA_FUNCTION_NAME` | variable | the Lambda function this pipeline updates |
| `API_BASE_URL` | variable | the live URL the post-deploy smoke test checks |

See `infra/` for the setup that provisions the AWS side of this.
