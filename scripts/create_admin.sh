#!/usr/bin/env bash
set -euo pipefail
STACK_NAME="${1:?Usage: $0 <stack-name> <email> <permanent-password>}"
EMAIL="${2:?Usage: $0 <stack-name> <email> <permanent-password>}"
PASSWORD="${3:?Usage: $0 <stack-name> <email> <permanent-password>}"
USER_POOL_ID="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='AdminUserPoolId'].OutputValue" --output text)"
aws cognito-idp admin-create-user --user-pool-id "$USER_POOL_ID" --username "$EMAIL" --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true --message-action SUPPRESS >/dev/null
aws cognito-idp admin-set-user-password --user-pool-id "$USER_POOL_ID" --username "$EMAIL" --password "$PASSWORD" --permanent
echo "Administrator created: $EMAIL"
