"""Local operations. Credentials are written to a new mode-0600 file, never stdout."""
import argparse
import os
import json
from pathlib import Path
from .db import default_path, migrate, connect
from .auth import provision, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default=default_path())
    commands = parser.add_subparsers(dest='command',required=True)
    commands.add_parser('migrate')
    bootstrap = commands.add_parser('bootstrap')
    bootstrap.add_argument('--tenant',required=True)
    bootstrap.add_argument('--name',required=True)
    bootstrap.add_argument('--output',default='var/admin.token')
    user = commands.add_parser('user')
    user.add_argument('--tenant-id',required=True)
    user.add_argument('--name',required=True)
    user.add_argument('--role',choices=['admin','staff','owner','owner_readonly','receiver','picker','packer','finance'],required=True)
    user.add_argument('--owner-id')
    user.add_argument('--count-only',action='store_true',help='Blind-count-only picker credential; no inventory/business reads')
    user.add_argument('--warehouse-id',action='append',default=[])
    user.add_argument('--output',required=True)
    revoke = commands.add_parser('revoke')
    revoke.add_argument('--user-id',required=True)
    backup = commands.add_parser('backup')
    backup.add_argument('--output',required=True)
    args = parser.parse_args()
    if args.command=='migrate':
        migrate(args.db)
        print('Migrations applied.')
    elif args.command in ('bootstrap','user'):
        output = Path(args.output)
        output.parent.mkdir(parents=True,exist_ok=True)
        # Reserve credential file before creating any user, preventing silent overwrite.
        fd = os.open(output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        try:
            result = provision(args.db,args.tenant if args.command=='bootstrap' else '',args.name,
                **({} if args.command=='bootstrap' else {'tenant_id':args.tenant_id,'role':args.role,'owner_id':args.owner_id,'warehouse_ids':args.warehouse_id,'count_only':args.count_only}))
            with os.fdopen(fd,'w') as stream:
                fd = None
                json.dump(result,stream)
            print(f'Credentials saved to protected file {output}; valid 30 days. Do not commit or share.')
        except BaseException:
            if fd is not None:
                os.close(fd)
            output.unlink(missing_ok=True)
            raise
    elif args.command=='revoke':
        with connect(args.db) as db:
            count = db.execute('UPDATE users SET active=0 WHERE id=?',(args.user_id,)).rowcount
        print(f'Revoked users: {count}')
    elif args.command=='backup':
        output = Path(args.output)
        fd = os.open(output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        os.close(fd)
        with connect(args.db) as source, connect(str(output)) as target:
            source.backup(target)
            assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        print('Consistent backup created; integrity_check=ok.')

if __name__=='__main__':
    main()
