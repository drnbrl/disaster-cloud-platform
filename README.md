# AI-Powered Disaster Cloud Platform

Three-week internship MVP: citizens submit free-text disaster requests; the backend stores them, queues AI analysis, validates structured output, calculates explainable priority scores, shows an admin dashboard/map, and calculates deterministic resource-allocation suggestions.

> Demo and decision-support prototype only. It is not certified for live emergency dispatch, medical triage or autonomous life-critical decisions. Use synthetic data.

## Stack
- React + TypeScript + Vite
- API Gateway + Lambda + SQS + DynamoDB
- Amazon Bedrock (optional at first; mock analyzer is default)
- Cognito administrator authentication
- CloudWatch alarms/logs
- AWS SAM infrastructure as code

## Local-only development
Use this mode when you want the MVP running without an AWS account, AWS credentials, deployment, Bedrock, cloud DynamoDB, cloud SQS, Cognito, API Gateway or any `amazonaws.com` endpoint.

```bash
./scripts/local-up.sh
./scripts/local-seed.sh 15
./scripts/local-test.sh
./scripts/local-down.sh
```

Open `http://localhost:5173`. The local FastAPI backend is `http://localhost:8001` and health is available at `http://localhost:8001/health`.

Create a local administrator before using the admin screens:

```bash
./scripts/create-local-admin.sh \
  admin@example.com \
  "Strong-Local-Password-123!" \
  "Admin Name"
```

See [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) for the local architecture, endpoints, administrator management, reset command and limitations. This local path uses DynamoDB Local with persistent Docker storage, mock AI analysis and local-only JWT authentication; the AWS production architecture below remains unchanged.

## macOS prerequisites
Docker Desktop is already installed; start it before `sam local`.

```bash
brew update
brew install git node python@3.12 awscli aws-sam-cli jq

git --version
node --version
python3.12 --version
aws --version
sam --version
docker --version
```

Use your company authentication method. Prefer IAM Identity Center when supplied:
```bash
aws configure sso
aws sts get-caller-identity
```
Never commit AWS keys.

## Install and test
```bash
cd ai-disaster-cloud-platform
make install
make test
```

## Deploy backend
```bash
cd backend
sam validate
sam build --use-container
sam deploy --guided
```
Suggested first deployment:
```text
Stack Name: disaster-platform-dev
StageName: dev
AllowedOrigin: http://localhost:5173
UseMockAi: true
BedrockModelId: leave empty
```

Export outputs for the frontend:
```bash
cd ..
./scripts/export_stack_env.sh disaster-platform-dev
```

Create an admin user:
```bash
./scripts/create_admin.sh disaster-platform-dev your-email@example.com 'Strong-Demo-Password-123!'
```

Run frontend:
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173`.

## Seed synthetic requests
```bash
python3.12 scripts/seed_requests.py \
  --api-url "$(grep VITE_API_URL frontend/.env.local | cut -d= -f2)" \
  --count 15
```

## Optional coordinate backfill
Existing DynamoDB requests with an address but no coordinates are not automatically reprocessed. After deploying the geocoding-enabled analyzer, review a dry run first:
```bash
REQUESTS_TABLE_NAME=your-requests-table backend/.venv/bin/python scripts/backfill_missing_coordinates.py --region your-region --dry-run
```
Remove `--dry-run` only when the counts look correct. The script updates only location-related attributes and skips records with any existing valid coordinate.

## Enable Bedrock
Confirm the approved model/inference profile is available in your selected AWS Region and supports Converse. Then:
```bash
cd backend
sam deploy --parameter-overrides \
  StageName=dev \
  AllowedOrigin=http://localhost:5173 \
  UseMockAi=false \
  BedrockModelId='YOUR_APPROVED_MODEL_OR_INFERENCE_PROFILE_ID'
```
The model extracts facts. `shared/priority.py` calculates priority. `shared/allocation.py` calculates quantities.

## Frontend hosting
Connect the GitHub repository to AWS Amplify Hosting, set app root to `frontend`, add variables from `frontend/.env.local`, build with `npm install && npm run build`, and publish `dist`. Redeploy the API with `AllowedOrigin` equal to the Amplify URL.

## Useful commands
```bash
sam logs --stack-name disaster-platform-dev --name AnalyzeRequestFunction --tail
aws cloudformation describe-stacks --stack-name disaster-platform-dev --query 'Stacks[0].Outputs'
```

## Production backlog
A real deployment needs WAF/bot protection, fine-grained roles, formal threat modeling, audit trails, reconciliation jobs, multi-Region recovery, load/chaos tests, accessibility/KVKK reviews, expert-reviewed triage rules and integrations with authorized emergency organizations.
