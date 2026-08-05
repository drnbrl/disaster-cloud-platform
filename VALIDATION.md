# Validation status

Validated in the generation environment:

- `python3 -m compileall backend/src backend/tests scripts`: passed
- `PYTHONPATH=src pytest -q`: **8 tests passed**
- `backend/template.yaml`: parsed successfully as YAML with 15 resources
- No AWS credentials, account IDs, passwords or model IDs are included

Not fully executable in the generation environment:

- `npm install` could not complete because package-registry access timed out. Run `cd frontend && npm install && npm run build` on macOS.
- AWS SAM CLI was not installed in the generation environment. Run `cd backend && sam validate && sam build --use-container` on macOS.
- No deployment was attempted because AWS credentials, Region and approved Bedrock model access are user/company-specific.

The default backend parameter is `UseMockAi=true`, allowing the deployed pipeline to work before Bedrock access is configured.
