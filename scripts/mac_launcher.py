"""Mac double-click launcher. Bootstrap uses only Python's standard library."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import socket
import sqlite3
import subprocess
import sys
from threading import Thread
import time
import venv

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = {'admin':'管理员', 'source_picker':'源仓拣货/发出员',
            'destination_receiver':'目标仓收货员', 'counter_a':'初盘员 A', 'counter_b':'复盘员 B'}


def default_directory():
    return Path.home()/'Library'/'Application Support'/'AtlasWMS'/'Trial-0.5'


def require_mac():
    if sys.platform != 'darwin':
        raise ValueError('此双击入口仅用于 macOS；其他系统请使用 scripts.local_trial。')
    if sys.version_info[:2] != (3,12):
        raise ValueError('请先安装 Python 3.12，再打开启动文件。')
    version = platform.mac_ver()[0]
    if not version or int(version.split('.')[0]) < 11:
        raise ValueError('此试用包要求 macOS 11 或更新版本。')


@contextmanager
def exclusive(path, message):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd = os.open(path,os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(message) from None
        yield
    finally:
        os.close(fd)


def runtime_ready(python, root=ROOT):
    if not python.is_file():
        return False
    check = """import sys,json,platform
from importlib.metadata import version
import fastapi,uvicorn,pydantic_core
print(json.dumps({'versions':{name:version(name) for name in sys.argv[1:]},'python':list(sys.version_info[:2]),'machine':platform.machine()}))"""
    expected = dict(line.split('==',1) for line in (root/'requirements.lock').read_text().splitlines() if line and not line.startswith('#'))
    result = subprocess.run([str(python),'-c',check,*expected],capture_output=True,text=True)
    if result.returncode:
        return False
    try:
        actual = json.loads(result.stdout)
        return actual['versions']==expected and actual['python']==[3,12] and actual['machine']==platform.machine()
    except (ValueError,KeyError):
        return False


def ensure_runtime(root=ROOT):
    python = root/'.venv'/'bin'/'python'
    if runtime_ready(python,root):
        return python
    architecture = platform.machine()
    if architecture not in ('arm64','x86_64'):
        raise ValueError('未识别的 Python 架构，请安装官方 Python 3.12 universal2 版本。')
    wheels = root/'mac-wheels'/architecture
    if not wheels.is_dir() or not list(wheels.glob('*.whl')):
        raise ValueError('离线依赖缺失。请完整解压 Mac 试用包，不要只复制 .command 文件。')
    with exclusive(root/'.mac-install.lock','另一个窗口正在准备运行环境，请等待该窗口完成。'):
        if runtime_ready(python,root):
            return python
        if (root/'.venv').is_symlink():
            raise ValueError('.venv 不能是符号链接。请在新的完整解压目录启动。')
        if not python.is_file():
            print('首次准备本机运行环境，请稍候……',flush=True)
            venv.EnvBuilder(with_pip=True).create(root/'.venv')
        print('安装包内离线依赖，不修改系统 Python……',flush=True)
        result = subprocess.run([str(python),'-m','pip','--isolated','install','--no-index','--only-binary=:all:',
            '--find-links',str(wheels),'-r',str(root/'requirements.lock')])
        if result.returncode or not runtime_ready(python,root):
            raise ValueError('运行环境准备失败，请保留错误信息，并确认安装的是 Python 3.12。')
    return python


def copy_credential(directory, account='admin'):
    """Selected credential goes only to pbcopy's stdin, never argv or stdout."""
    directory = Path(directory)
    credential_file, database = directory/'accounts.token', directory/'trial.sqlite3'
    if credential_file.is_symlink() or database.is_symlink() or not credential_file.is_file() or not database.is_file():
        raise ValueError('尚无完整试用数据，请先双击“启动仓储.command”。')
    data = json.loads(credential_file.read_text())
    if data.get('format') != 'wms-isolated-local-trial-v1' or account not in ACCOUNTS:
        raise ValueError('无法识别试用账号文件。')
    selected = data['accounts'][account]
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as db:
        row = db.execute('SELECT expires_at FROM users WHERE id=? AND tenant_id=? AND token_hash=? AND active=1',
            (selected['user_id'],data['tenant_id'],hashlib.sha256(selected['token'].encode()).hexdigest())).fetchone()
    if not row or (row[0] and datetime.fromisoformat(row[0])<=datetime.now(timezone.utc)):
        raise ValueError('此账号已过期或撤销，请联系管理员；不会自动重发或重置库存。')
    result = subprocess.run(['/usr/bin/pbcopy'],input=selected['token'].encode(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if result.returncode:
        raise ValueError('未能复制凭证，请在本机 accounts.token 文件中手动复制对应账号的 token 值。')
    print(f'已复制{ACCOUNTS[account]}登录凭证。请在页面令牌框按 Command+V 粘贴，再点“连接工作空间”。',flush=True)


def listener(preferred=8000):
    for port in range(preferred,preferred+11):
        sock = socket.socket()
        try:
            sock.bind(('127.0.0.1',port))
            return sock
        except OSError:
            sock.close()
    raise ValueError('本地 8000–8010 端口均被占用；请停止其他试用窗口后重试。')


def open_when_ready(server, url, directory):
    deadline = time.monotonic()+20
    while not server.started and not server.should_exit and time.monotonic()<deadline:
        time.sleep(0.1)
    if not server.started:
        print('页面未能自动打开，请检查当前终端中的启动错误。',flush=True)
        return
    try:
        copy_credential(directory)
    except (ValueError,OSError,KeyError,sqlite3.Error):
        print('未能自动复制登录凭证。请双击“复制登录凭证.command”，或在本机账号文件中复制。',flush=True)
    subprocess.run(['/usr/bin/open',url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def serve(directory, desktop=True):
    from scripts.local_trial import prepare
    from app.main import create_app
    import uvicorn
    database, credentials = prepare(directory)
    sock = listener()
    url = f'http://127.0.0.1:{sock.getsockname()[1]}'
    print(f'本地试用页面：{url}\n数据保存在：{database}\n账号文件：{credentials}',flush=True)
    print('请保留此终端窗口；按 Control+C 停止服务，试用数据会保留。仅用示例数据。',flush=True)
    server = uvicorn.Server(uvicorn.Config(create_app(database),log_level='warning',access_log=False))
    if desktop:
        Thread(target=open_when_ready,args=(server,url,Path(directory)),daemon=True).start()
    try:
        server.run(sockets=[sock])
    except KeyboardInterrupt:
        print("\n本地试用已停止，数据已保留。",flush=True)
    finally:
        sock.close()


def launch(directory, root=ROOT):
    directory = Path(directory).absolute()
    lock = directory.with_name(directory.name+'.launch.lock')
    with exclusive(lock,'试用已在另一个终端启动（或正在准备）。请使用原窗口，不必重复启动。'):
        python = ensure_runtime(root)
        child = subprocess.Popen([str(python),'-m','scripts.mac_launcher','serve','--data-directory',str(directory)],cwd=root)
        try:
            return child.wait()
        except KeyboardInterrupt:
            if child.poll() is None:
                child.send_signal(signal.SIGINT)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    child.wait(timeout=5)
            return 0


def main():
    parser = argparse.ArgumentParser(description='Atlas WMS Mac 本地试用')
    parser.add_argument('action',choices=['start','copy','serve'])
    parser.add_argument('--data-directory',type=Path,default=default_directory())
    parser.add_argument('--account',choices=list(ACCOUNTS))
    args = parser.parse_args()
    status = 0
    try:
        require_mac()
        if args.action=='serve':
            serve(args.data_directory)
            return
        if args.action=='start':
            status = launch(args.data_directory)
        else:
            account = args.account
            if account is None:
                names = list(ACCOUNTS)
                for index,name in enumerate(names,1):
                    print(f'{index}. {ACCOUNTS[name]}')
                selection = input('输入账号序号（默认 1 管理员）：').strip() or '1'
                if selection not in {str(i) for i in range(1,len(names)+1)}:
                    raise ValueError('账号序号无效，请重新打开复制凭证入口。')
                account = names[int(selection)-1]
            copy_credential(args.data_directory,account)
    except KeyboardInterrupt:
        print('\n已停止本地试用。')
    except (ValueError,OSError,KeyError,sqlite3.Error,subprocess.SubprocessError):
        # Never stringify token-bearing input, JSON or child arguments.
        # ValueError messages here are controlled; JSONDecodeError must be generic.
        error = sys.exc_info()[1]
        message = str(error) if type(error) is ValueError else '请检查完整解压目录、Python 3.12 和试用账号文件；原数据没有自动重置。'
        print(f'启动/复制未完成：{message}',file=sys.stderr)
        status = 1
    if args.action!='serve' and sys.stdin.isatty():
        try:
            input('按回车关闭此窗口……')
        except (EOFError,KeyboardInterrupt):
            pass
    raise SystemExit(status)


if __name__=='__main__':
    main()
