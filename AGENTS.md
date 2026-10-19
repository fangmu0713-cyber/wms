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

## Current warehouse increments
Migrations 001/002/003/004/005 are published contracts; continue with 006. Outside measurement locks, available=on_hand-reserved-move_reserved-count_reserved; during count_locked measurement, available=0. Same-warehouse IN_TRANSIT is physical custody, not sellable inventory or cross-warehouse transfer. Never cancel dispatched movement directly or bypass active wave tasks. Browser acceptance: `python -m tests.browser_warehouse -v`; preserve historical evidence with `WMS_EVIDENCE_DIR=evidence/stage3/legacy python -m tests.browser_flow -v`.

Count-only credentials may access only their own blind tasks. Never expose baselines/cutoffs/deltas through reads or cached responses. A count approval adds the accepted delta to current stock and releases its hold; it never overwrites a balance with an old count. Recounts compare independent deltas against fresh locked cutoffs. Run `python -m tests.browser_counts -v`; do not downgrade past count-only enforcement.

Cross-warehouse transfers reuse move_reserved before departure, with separate ledger.transfer_transit_delta/transfer_lost_delta. Create/cancel supervisors need both warehouses; dispatch source picker/staff, receive destination receiver/staff; loss close admin with exact remaining and reason. Immutable per-batch events; same transfer/receipt_reference cannot credit twice across actors/keys. Transit custody is attributed once to the source, receipt credits destination only, confirmed loss leaves physical_total. Reconcile needs both ledger sides internally even for one-sided callers. Replay cached transfer responses must recheck current roles/grants. Run `python -m tests.browser_transfers -v`. Local trial is explicit and isolated; never package runtime credentials/DBs.
