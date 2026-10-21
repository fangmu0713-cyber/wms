"""Launcher logic on Linux; desktop APIs are explicit stubs, not Mac acceptance."""
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.db import connect
from scripts.local_trial import prepare
from scripts import mac_launcher as mac


class MacLauncherTests(unittest.TestCase):
    def test_persistent_mac_data_directory_separate_from_extracted_source(self):
        with patch.object(Path,'home',return_value=Path('/Users/Example User')):
            self.assertEqual(mac.default_directory(),Path('/Users/Example User/Library/Application Support/AtlasWMS/Trial-0.5'))
        self.assertNotIn('var',mac.default_directory().parts)

    def test_selected_token_only_to_clipboard_stdin_never_printed_or_in_argv(self):
        with TemporaryDirectory(prefix='mac trial spaces ') as root:
            directory = Path(root)/'示例 数据'
            _,credentials = prepare(directory)
            accounts = json.loads(credentials.read_text())['accounts']
            output = io.StringIO()
            with contextlib.redirect_stdout(output),patch.object(mac.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
                mac.copy_credential(directory,'destination_receiver')
            args,kwargs = run.call_args
            self.assertEqual(args[0],['/usr/bin/pbcopy'])
            self.assertEqual(kwargs['input'],accounts['destination_receiver']['token'].encode())
            for account in accounts.values():
                self.assertNotIn(account['token'],output.getvalue())
                self.assertNotIn(account['token'],str(args))
            self.assertIn('目标仓收货员',output.getvalue())

    def test_clipboard_rejects_missing_wrong_format_and_symlink_without_seeding(self):
        with TemporaryDirectory() as root:
            directory = Path(root)/'trial'
            with patch.object(mac.subprocess,'run') as run:
                with self.assertRaises(ValueError):
                    mac.copy_credential(directory)
                self.assertFalse(directory.exists())
                database,credentials = prepare(directory)
                data = credentials.read_text()
                credentials.unlink()
                hidden = Path(root)/'secrets.token'
                hidden.write_text(data)
                credentials.symlink_to(hidden)
                with self.assertRaises(ValueError):
                    mac.copy_credential(directory)
                run.assert_not_called()

    def test_clipboard_rejects_revoked_expired_or_mismatched_tokens(self):
        with TemporaryDirectory() as root:
            directory = Path(root)/'trial'
            database,credentials = prepare(directory)
            accounts = json.loads(credentials.read_text())['accounts']
            with patch.object(mac.subprocess,'run') as run:
                with connect(database) as db:
                    db.execute('UPDATE users SET active=0 WHERE id=?',(accounts['counter_a']['user_id'],))
                    db.execute("UPDATE users SET expires_at='2020-01-01T00:00:00+00:00' WHERE id=?",(accounts['counter_b']['user_id'],))
                    db.execute("UPDATE users SET token_hash='wrong' WHERE id=?",(accounts['source_picker']['user_id'],))
                for account in ('counter_a','counter_b','source_picker'):
                    with self.assertRaises(ValueError):
                        mac.copy_credential(directory,account)
                run.assert_not_called()

    def test_held_instance_lock_blocks_second_launch_and_releases_normally(self):
        with TemporaryDirectory() as root:
            lock = Path(root)/'App Support'/'Trial.launch.lock'
            with mac.exclusive(lock,'busy'):
                code = 'from scripts.mac_launcher import exclusive; import sys\ntry:\n with exclusive(sys.argv[1],"busy"): pass\nexcept ValueError:\n raise SystemExit(42)'
                result = subprocess.run([sys.executable,'-c',code,str(lock)],capture_output=True)
                self.assertEqual(result.returncode,42,result.stderr)
                self.assertEqual(lock.stat().st_mode&0o777,0o600)
            with mac.exclusive(lock,'busy'):
                pass

    def test_existing_foreign_service_is_not_reused_when_default_port_busy(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1',0))
            port = occupied.getsockname()[1]
            if port>65524:
                self.skipTest('ephemeral port too near range limit')
            reserved = mac.listener(port)
            try:
                self.assertNotEqual(reserved.getsockname()[1],port)
                self.assertEqual(reserved.getsockname()[0],'127.0.0.1')
            finally:
                reserved.close()

    def test_runtime_uses_pinned_metadata_and_import_check(self):
        self.assertTrue(mac.runtime_ready(Path(sys.executable)))
        with TemporaryDirectory() as root:
            root = Path(root)
            (root/'requirements.lock').write_text('fastapi==0.0.0\n')
            self.assertFalse(mac.runtime_ready(Path(sys.executable),root))
            self.assertFalse(mac.runtime_ready(root/'missing',root))

    def test_non_mac_and_old_mac_stopped_before_setup(self):
        with patch.object(mac.sys,'platform','linux'):
            with self.assertRaisesRegex(ValueError,'仅用于 macOS'):
                mac.require_mac()
        with patch.object(mac.sys,'platform','darwin'),patch.object(mac.platform,'mac_ver',return_value=('10.15.7',(),'')):
            with self.assertRaisesRegex(ValueError,'macOS 11'):
                mac.require_mac()

    def test_missing_offline_wheels_does_not_create_or_replace_runtime(self):
        with TemporaryDirectory() as root:
            root = Path(root)
            with self.assertRaisesRegex(ValueError,'离线依赖缺失'):
                mac.ensure_runtime(root)
            self.assertFalse((root/'.venv').exists())

    def test_command_entrypoints_keep_executable_bits_and_valid_bash_syntax(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('启动仓储.command','复制登录凭证.command','scripts/mac_launcher.sh'):
            path = root/name
            self.assertTrue(os.access(path,os.X_OK))
            self.assertEqual(subprocess.run(['bash','-n',str(path)],capture_output=True).returncode,0)
