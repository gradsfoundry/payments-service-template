#!/usr/bin/env bash
# One-time setup, run ONCE against the AWS account before any student is
# provisioned. Not idempotent-tested against a real account yet -- read it
# before running it, and run each section once. See infra/DESIGN.md.
#
# Requires: AWS CLI configured with an admin IAM user (not root), and
# GITHUB_ORG set to your GitHub org name.

set -euo pipefail

: "${GITHUB_ORG:?Set GITHUB_ORG=gradsfoundry (or whatever the org is named)}"
: "${COHORT_TAG:?Set COHORT_TAG=pilot-2026-xx, used for cost tracking}"
AWS_REGION="${AWS_REGION:-ap-south-1}"

echo "== 1. GitHub OIDC identity provider =="
# One provider for the whole account -- every student role and the
# teardown role trust this same provider, just with different repo
# conditions on their individual trust policies.
OIDC_ARN=$(aws iam list-open-id-connect-providers \
  --query "OpenIDConnectProviderList[?contains(Arn, 'token.actions.githubusercontent.com')].Arn" \
  --output text)

if [ -z "$OIDC_ARN" ]; then
  OIDC_ARN=$(aws iam create-open-id-connect-provider \
    --url "https://token.actions.githubusercontent.com" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" \
    --query OpenIDConnectProviderArn --output text)
  echo "Created OIDC provider: $OIDC_ARN"
else
  echo "OIDC provider already exists: $OIDC_ARN"
fi

echo "== 2. Shared Lambda execution role (every student function uses this) =="
# This is NOT a per-student identity -- it's what Lambda itself assumes
# at runtime to write its own logs. Safe to share: it can't do anything
# except write CloudWatch logs for whatever function invokes it.
cat > /tmp/lambda-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "lambda.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name gradsfoundry-lambda-execution \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
  --tags Key=gradsfoundry:cohort,Value="$COHORT_TAG" \
  || echo "(role may already exist -- check before re-running)"

aws iam attach-role-policy \
  --role-name gradsfoundry-lambda-execution \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

LAMBDA_EXEC_ROLE_ARN=$(aws iam get-role --role-name gradsfoundry-lambda-execution --query Role.Arn --output text)
echo "Lambda execution role: $LAMBDA_EXEC_ROLE_ARN"
echo ">>> Set this as the GitHub ORG-level variable LAMBDA_EXECUTION_ROLE_ARN"

echo "== 3. Teardown role (used only by the ops/teardown workflow) =="
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
cat > /tmp/teardown-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "$OIDC_ARN" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike": { "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/ops:*" }
    }
  }]
}
EOF

cat > /tmp/teardown-permissions-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["lambda:DeleteFunction", "lambda:DeleteFunctionUrlConfig", "lambda:GetFunction"],
      "Resource": "arn:aws:lambda:*:*:function:gradsfoundry-*"
    },
    {
      "Effect": "Allow",
      "Action": ["ecr:DeleteRepository", "ecr:DescribeRepositories"],
      "Resource": "arn:aws:ecr:*:*:repository/gradsfoundry/*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:DeleteLogGroup"],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/gradsfoundry-*"
    }
  ]
}
EOF

aws iam create-role \
  --role-name gradsfoundry-teardown \
  --assume-role-policy-document file:///tmp/teardown-trust-policy.json \
  --tags Key=gradsfoundry:cohort,Value="$COHORT_TAG" \
  || echo "(role may already exist -- check before re-running)"

aws iam put-role-policy \
  --role-name gradsfoundry-teardown \
  --policy-name gradsfoundry-teardown-permissions \
  --policy-document file:///tmp/teardown-permissions-policy.json

TEARDOWN_ROLE_ARN=$(aws iam get-role --role-name gradsfoundry-teardown --query Role.Arn --output text)
echo "Teardown role: $TEARDOWN_ROLE_ARN"
echo ">>> Set this as the secret AWS_TEARDOWN_ROLE_ARN in the ops repo (${GITHUB_ORG}/ops)"

echo "== 4. Budget, filtered by the cost-allocation tag =="
echo "NOTE: activate 'gradsfoundry:cohort' as a user-defined cost allocation"
echo "tag in Billing > Cost allocation tags first -- can take up to 24h to"
echo "start showing cost data. Do this well before a cohort starts."
cat > /tmp/budget.json <<EOF
{
  "BudgetName": "gradsfoundry-${COHORT_TAG}",
  "BudgetLimit": { "Amount": "${BUDGET_LIMIT_USD:-100}", "Unit": "USD" },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST",
  "CostFilters": { "TagKeyValue": ["user:gradsfoundry:cohort\$${COHORT_TAG}"] }
}
EOF
cat > /tmp/budget-notification.json <<'EOF'
[{
  "Notification": {
    "NotificationType": "ACTUAL",
    "ComparisonOperator": "GREATER_THAN",
    "Threshold": 80,
    "ThresholdType": "PERCENTAGE"
  },
  "Subscribers": [{ "SubscriptionType": "EMAIL", "Address": "REPLACE_WITH_YOUR_EMAIL" }]
}]
EOF
echo "Edit /tmp/budget-notification.json with your real email, then run:"
echo "  aws budgets create-budget --account-id $ACCOUNT_ID --budget file:///tmp/budget.json --notifications-with-subscribers file:///tmp/budget-notification.json"
echo "(left as a manual last step -- didn't want to silently create a budget notifying an email nobody checks)"

echo
echo "Done. Next: run infra/provision-student.sh once per student."
