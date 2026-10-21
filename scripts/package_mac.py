"""Build a source-based Mac trial ZIP with both CPython 3.12 wheel sets."""
import argparse
from email.parser import Parser
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(wheels, output):
    expected = dict(line.split('==',1) for line in (ROOT/'requirements.lock').read_text().splitlines() if line and not line.startswith('#'))
    normalize = lambda name:name.lower().replace('_','-')
    expected = {normalize(k):v for k,v in expected.items()}
    manifest = {'python':'CPython 3.12','macos':'11+','architectures':{},'mac_hardware_executed':False}
    wheel_files = []
    for architecture in ('arm64','x86_64'):
        packages, records = {}, []
        for wheel in sorted((Path(wheels)/architecture).glob('*.whl')):
            with zipfile.ZipFile(wheel) as archive:
                assert archive.testzip() is None
                meta = next(name for name in archive.namelist() if name.endswith('.dist-info/METADATA'))
                data = Parser().parsestr(archive.read(meta).decode())
                packages[normalize(data['Name'])] = data['Version']
                tag_file = next(name for name in archive.namelist() if name.endswith('.dist-info/WHEEL'))
                tags = archive.read(tag_file).decode()
                if normalize(data['Name'])=='pydantic-core':
                    assert 'cp312-cp312-macosx_' in tags and architecture in tags
            records.append({'file':wheel.name,'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest()})
            wheel_files.append((wheel,'mac-wheels/'+architecture+'/'+wheel.name))
        if packages != expected:
            raise ValueError(f'Incomplete or mismatched offline wheels for {architecture}')
        manifest['architectures'][architecture] = records
    files = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name in filter(None,files):
            if name.startswith(('var/','.venv/','.git/')) or name.endswith(('.token','.sqlite3','.sqlite3-wal','.sqlite3-shm')):
                raise ValueError('Runtime secrets or databases must not be packaged')
            archive.write(ROOT/name,'仓储Mac试用/'+name)
        for path,name in wheel_files:
            archive.write(path,'仓储Mac试用/'+name)
        archive.writestr('仓储Mac试用/mac-wheels/manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        archive.write(ROOT/'docs/MAC_TRIAL.md','仓储Mac试用/Mac先读我.txt')
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for name in ('启动仓储.command','复制登录凭证.command'):
            info = archive.getinfo('仓储Mac试用/'+name)
            assert (info.external_attr>>16)&0o111
    return {'file':str(output),'bytes':Path(output).stat().st_size,'sha256':hashlib.sha256(Path(output).read_bytes()).hexdigest(),
            'architectures':['arm64','x86_64'],'wheels':len(wheel_files),'crc':'ok','command_executable_bits':'preserved','mac_hardware_executed':False}


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wheels',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.wheels,args.output),ensure_ascii=False,indent=2))
