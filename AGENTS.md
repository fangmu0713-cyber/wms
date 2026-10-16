# Development rules
Read docs/PROJECT_STATUS.md, TASK_BOARD.md, HANDOFF.md, DECISIONS.md and CONTRACT.md before changes. Follow docs/Codex_Overseas_WMS_Master_Task.md and user instructions. Never report ERP authorization or deployment without evidence.

## Ownership and migrations
Coordinator owns app core and sequential numbered SQL migrations; subtask agents must not edit migrations. UI owns app/static; verification owns tests; integration owns app/integrations.py and ERP/reference docs. Coordinate interface changes first.

## Commands
Python 3.12. Install: `python -m pip install -r requirements.txt`.
Migrate: `python -m app.cli migrate`. Initialize admin: `python -m app.cli bootstrap --tenant NAME --name NAME` (token writes only protected file).
Run: `uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log`.
Tests: `python -m unittest discover -s tests -v`. Browser instructions in tests and docs/OPERATIONS.md.

## Invariants and safety
Do not edit stock directly. Each write uses BEGIN IMMEDIATE transaction, idempotency record, audit and stock ledger as applicable. Never decrement stock for reserve/pick/pack; ship once. Scope every query by tenant and owner/warehouse access. No unauthenticated seed data, no default passwords, no business localStorage. Never log/store raw tokens except protected credential export, no secrets in screenshots. Use test-only temp databases. Do not touch VPS, SSH or running external services. Keep unresolved scope explicit in status/handoff.
