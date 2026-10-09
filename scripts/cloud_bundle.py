"""Create a source-only private-hosting bundle from an explicit allowlist."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path('/source')
TARGET=Path('/bundle')


def main():
    if TARGET.exists():
        raise RuntimeError('existing bundle preserved; choose a new empty directory')
    selected=[]
    for prefix in ('services/common/dorilab','packages/contracts','apps/web','fixtures/demo','migrations'):
        selected.extend(p for p in (ROOT/prefix).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    selected.extend(ROOT/p for p in ('services/cloud/Dockerfile','services/cloud/requirements.lock',
                                    'services/cloud/render.yaml','mockup/DoriLab_SE_Workbench.html',
                                    'mockup/DoriLab_Final_Goal_KASA_ECSS_NASA.md','.dockerignore'))
    manifest=[]
    for source in sorted(selected):
        if source.is_symlink(): raise RuntimeError('source symlink refused')
        relative=source.relative_to(ROOT)
        data=source.read_bytes()
        if b'PRIVATE KEY-----' in data:
            raise RuntimeError('private key found; source bundle refused')
        destination=TARGET/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,destination)
        manifest.append(dict(path=str(relative),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    (TARGET/'render.yaml').write_bytes((ROOT/'services/cloud/render.yaml').read_bytes())
    (TARGET/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('SOURCE_BUNDLE_READY: '+str(len(manifest))+' source files; no secrets, user uploads, or backups')


if __name__=='__main__': main()
