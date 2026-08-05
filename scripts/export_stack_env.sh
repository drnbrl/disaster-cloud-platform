#!/usr/bin/env bash
set -euo pipefail
STACK_NAME="${1:-disaster-platform-dev}"
value() {
  aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
REGION="$(aws configure get region || true)"
if [[ -z "$REGION" ]]; then
  REGION="$(aws ec2 describe-availability-zones --query 'AvailabilityZones[0].RegionName' --output text)"
fi
cat > frontend/.env.local <<ENV
VITE_API_URL=$(value ApiUrl)
VITE_AWS_REGION=$REGION
VITE_COGNITO_USER_POOL_ID=$(value AdminUserPoolId)
VITE_COGNITO_USER_POOL_CLIENT_ID=$(value AdminUserPoolClientId)
ENV
echo "Wrote frontend/.env.local"
