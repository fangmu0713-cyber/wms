"""Restore to a NEW isolated path; never overwrite a running database."""
import argparse
import os
import time
from pathlib import Path
from app.db import connect


def restore(source, target):
    started = time.perf_counter()
    if not Path(source).is_file():
        raise ValueError('backup does not exist')
    fd = os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(fd)
    transfer_custody = 'not_applicable'
    with connect(source) as backup, connect(target) as restored:
        backup.backup(restored)
        assert restored.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert restored.execute('PRAGMA foreign_key_check').fetchall()==[]
        counts = {table:restored.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('orders','inventory','ledger','receipts','returns','fees')}
        columns = {r['name'] for r in restored.execute('PRAGMA table_info(inventory)')}
        fields = [name for name in ('on_hand','reserved','picked','move_reserved','count_reserved') if name in columns]
        sums = ','.join(f'SUM({name}_delta) AS {name}' for name in fields)
        conditions = ' OR '.join(f'i.{name}<>COALESCE(l.{name},0)' for name in fields)
        mismatches = restored.execute(f'''SELECT i.id FROM inventory i LEFT JOIN (
            SELECT inventory_id,{sums} FROM ledger GROUP BY inventory_id
            ) l ON l.inventory_id=i.id WHERE {conditions}''').fetchall()
        assert not mismatches, 'ledger balance mismatch'
        if 'count_reserved' in columns:
            mismatches = restored.execute('''SELECT i.id FROM inventory i LEFT JOIN (
                SELECT inventory_id,SUM(hold_qty) q FROM count_lines WHERE active=1 GROUP BY inventory_id
                ) c ON c.inventory_id=i.id WHERE i.count_reserved<>COALESCE(c.q,0)''').fetchall()
            assert not mismatches, 'count hold mismatch'
            invalid = restored.execute('''SELECT a.id FROM count_attempts a LEFT JOIN count_locks c ON c.attempt_id=a.id
                LEFT JOIN count_lines l ON l.id=a.line_id WHERE a.status='ACTIVE' AND
                (c.attempt_id IS NULL OR c.line_id<>a.line_id OR c.session_id<>a.session_id OR c.inventory_id<>l.inventory_id OR l.active<>1)''').fetchall()
            invalid += restored.execute('''SELECT c.attempt_id FROM count_locks c JOIN count_attempts a ON a.id=c.attempt_id
                WHERE a.status<>'ACTIVE' ''').fetchall()
            assert not invalid, 'count measurement lock mismatch'
        tables = {r['name'] for r in restored.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'transfers' in tables:
            from app.transfers import reconcile
            issues = reconcile(restored,[dict(r) for r in restored.execute('SELECT * FROM transfers')])
            assert not issues, 'transfer custody mismatch'
            mismatches = restored.execute("""SELECT i.id FROM inventory i LEFT JOIN (
                SELECT source_inventory_id,SUM(qty) q FROM (
                    SELECT source_inventory_id,qty FROM movements WHERE status IN ('PLANNED','CLAIMED')
                    UNION ALL SELECT source_inventory_id,qty FROM transfers WHERE status='TRANSFER_PLANNED'
                ) GROUP BY source_inventory_id
                ) h ON h.source_inventory_id=i.id WHERE i.move_reserved<>COALESCE(h.q,0)""").fetchall()
            assert not mismatches, 'movement/transfer hold mismatch'
            transfer_custody = 'ok'
    return {'transfer_custody':transfer_custody,'integrity':'ok','foreign_keys':'ok','ledger_balances':'ok','counts':counts,'elapsed_seconds':round(time.perf_counter()-started,4)}

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('backup')
    parser.add_argument('new_database')
    args = parser.parse_args()
    print(restore(args.backup,args.new_database))
