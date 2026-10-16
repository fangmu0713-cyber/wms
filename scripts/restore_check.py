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
    with connect(source) as backup, connect(target) as restored:
        backup.backup(restored)
        assert restored.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert restored.execute('PRAGMA foreign_key_check').fetchall()==[]
        counts = {table:restored.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('orders','inventory','ledger','receipts','returns','fees')}
        mismatches = restored.execute('''SELECT i.id FROM inventory i LEFT JOIN (
            SELECT inventory_id,SUM(on_hand_delta) h,SUM(reserved_delta) r,SUM(picked_delta) p FROM ledger GROUP BY inventory_id
            ) l ON l.inventory_id=i.id WHERE i.on_hand<>COALESCE(l.h,0) OR i.reserved<>COALESCE(l.r,0) OR i.picked<>COALESCE(l.p,0)''').fetchall()
        assert not mismatches, 'ledger balance mismatch'
    return {'integrity':'ok','foreign_keys':'ok','ledger_balances':'ok','counts':counts,'elapsed_seconds':round(time.perf_counter()-started,4)}

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('backup')
    parser.add_argument('new_database')
    args = parser.parse_args()
    print(restore(args.backup,args.new_database))
