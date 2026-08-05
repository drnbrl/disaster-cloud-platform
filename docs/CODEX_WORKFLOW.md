# Codex workflow

Install Codex CLI on macOS:
```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
cd ai-disaster-cloud-platform
codex
```

Recommended first prompt:
```text
Read README.md and AGENTS.md. Review the repository without changing files.
Then install dependencies, run backend tests, run sam validate and build the
frontend. Fix only reproducible errors. Preserve SQS, deterministic priority,
deterministic allocation, Cognito authorization and raw-message privacy.
```

Feature prompt example:
```text
Add an administrator request-detail page. Reuse existing API types, do not
expose personal data, add loading and error states, and run npm run build.
```

Security-review prompt:
```text
Review Cognito, CORS, IAM scope, DynamoDB access, SQS retries, raw-message
logging, prompt injection and denial-of-wallet risks. Apply low-risk fixes and
add regression tests.
```
