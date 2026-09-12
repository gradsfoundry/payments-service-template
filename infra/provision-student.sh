#!/usr/bin/env bash
# Run ONCE per student, after their repo exists (created from the template)
# and before they're told to push. Batchable: loop this over a CSV of repo
# names. Not tested against a real account yet -- read before running.
# See infra/DESIGN.md for the identity model this implements.
#
# Usage: GITHUB_ORG=gradsfoundry COHORT_TAG=pilot-2026-xx ./provision-student.sh <repo-name>
# e.g.:  ./provision-student.sh aishwarya-orders-api

set -euo pipefail

REPO_NAME="${1:?Usage: provision-student.sh <repo-name>}"
: "${GITHUB_ORG:?Set GITHUB_ORG=gradsfoundry}"
: "${COHORT_TAG:?Set COHORT_TAG=pilot-2026-xx}"

ROLE_NAME="gradsfoundry-${REPO_NAME}-deploy"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
OIDC_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"

echo "Provisioning AWS identity for ${GITHUB_ORG}/${REPO_NAME} ..."

cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "${OIDC_ARN}" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike": { "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/${REPO_NAME}:*" }
    }
  }]
}
EOF

# Scoped so this student's role can only touch resources whose name is
# derived from their own repo name -- not anyone else's.
cat > /tmp/permissions-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:CreateRepository",
        "ecr:DescribeRepositories",
        "ecr:BatchCheckLayerAvailability",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "arn:aws:ecr:*:${ACCOUNT_ID}:repository/gradsfoundry/${REPO_NAME}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:GetFunction",
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:CreateFunctionUrlConfig",
        "lambda:GetFunctionUrlConfig",
        "lambda:AddPermission"
      ],
      "Resource": "arn:aws:lambda:*:${ACCOUNT_ID}:function:gradsfoundry-${REPO_NAME}"
    },
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::${ACCOUNT_ID}:role/gradsfoundry-lambda-execution"
    }
  ]
}
EOF

aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document file:///tmp/trust-policy.json \
  --tags Key=gradsfoundry:cohort,Value="$COHORT_TAG" \
  || echo "(role may already exist -- check before re-running for this student)"

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name gradsfoundry-deploy-permissions \
  --policy-document file:///tmp/permissions-policy.json

ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text)
echo "Role created: $ROLE_ARN"

if command -v gh >/dev/null 2>&1; then
  echo "Setting AWS_ROLE_ARN secret on ${GITHUB_ORG}/${REPO_NAME} via gh..."
  gh secret set AWS_ROLE_ARN --repo "${GITHUB_ORG}/${REPO_NAME}" --body "$ROLE_ARN"
  echo "Done -- ${REPO_NAME} can now push and deploy."
else
  echo ">>> gh CLI not found. Set this manually as the repo secret AWS_ROLE_ARN:"
  echo "$ROLE_ARN"
fi
