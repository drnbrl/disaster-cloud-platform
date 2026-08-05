# Codex repository instructions

## Mission
Build a safe internship MVP for disaster-assistance request intake and decision support. Never describe it as a certified emergency dispatch or medical-triage system.

## Architecture invariants
1. Store public requests before AI processing.
2. Keep AI processing asynchronous through Amazon SQS.
3. AI extracts structured facts; deterministic Python calculates priority.
4. Deterministic Python calculates allocation quantities; AI may only explain them.
5. Never log raw citizen messages or future contact details.
6. Keep SQS processing idempotent and return partial batch failures.
7. Keep deployed administrator routes protected by Cognito.
8. Validate every AI result with Pydantic.
9. Use synthetic test data only.
10. Do not add Kubernetes, another database, or an agent framework without a requirement.

## Verification commands
```bash
cd backend && source .venv/bin/activate && pytest
cd backend && sam validate
cd frontend && npm run build
```

## Conventions
- Python 3.12, type hints, UTC ISO-8601 timestamps.
- React + TypeScript; avoid `any`.
- Keep secrets, account IDs and credentials out of Git.
- Update tests and docs for behavior changes.
