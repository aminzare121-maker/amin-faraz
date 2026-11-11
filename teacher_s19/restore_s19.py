"""Restore unmodified teacher core from exact historic git commit, overlay only S19 corrections."""
import argparse,subprocess,hashlib,json,shutil,sys
from pathlib import Path
COMMIT='b48fb06f8b2b0d134292025f5b27fc670ad2a293'
PREFIX='research/artin-independent-engine/'
ROOT=Path(__file__).resolve().parent

def run(origin=None):
    target=ROOT/'teacher_core_s19'
    base=ROOT/'core'
    if target.exists() or base.exists():
        raise SystemExit('REFUSE_OVERWRITE_EXISTING_TEACHER_CORE')
    manifest=json.loads((ROOT/'LEGACY_SHA_MANIFEST.json').read_text(encoding='utf8'))
    assert manifest['source_commit']==COMMIT
    corefiles=sorted(manifest['files_sha256'])
    for directory in (base,target):directory.mkdir()
    for name in corefiles:
        if Path(name).is_absolute() or '..' in Path(name).parts or name.startswith('.') or '\\' in name:
            raise SystemExit('UNSAFE_MANIFEST_PATH')
        if origin:
            data=(Path(origin)/name).read_bytes()
        else:
            p=subprocess.run(['git','show',f'{COMMIT}:{PREFIX}{name}'],capture_output=True,check=True)
            data=p.stdout
        if hashlib.sha256(data).hexdigest()!=manifest['files_sha256'][name]:
            raise SystemExit('PINNED_SOURCE_SHA_MISMATCH:'+name)
        (base/name).parent.mkdir(parents=True,exist_ok=True)
        (target/name).parent.mkdir(parents=True,exist_ok=True)
        (base/name).write_bytes(data)
        (target/name).write_bytes(data)
    shutil.copy2(ROOT/'LEGACY_SHA_MANIFEST.json',base/'LEGACY_SHA_MANIFEST.json')
    shutil.copy2(ROOT/'LEGACY_SHA_MANIFEST.json',target/'LEGACY_SHA_MANIFEST.json')
    changed={'entry_engine.py','raw_pipeline.py','examples.py'}
    correction=json.loads((ROOT/'TEACHER_CORE_S19_PATCH_MANIFEST.json').read_text(encoding='utf8'))
    assert set(correction['changed_files'])==changed
    for name in changed|{'test_s19_teacher_correction.py','test_raw_pipeline.py'}:
        data=(ROOT/name).read_bytes()
        assert hashlib.sha256(data).hexdigest()==correction['sha256'][name]
        (target/name).write_bytes(data)
    shutil.copy2(ROOT/'TEACHER_CORE_S19_PATCH_MANIFEST.json',target/'TEACHER_CORE_S19_PATCH_MANIFEST.json')
    # Complete source is compared to correction's provenance digest; no silent drift.
    for name,expect in correction['sha256'].items():
        assert hashlib.sha256((target/name).read_bytes()).hexdigest()==expect, name
    print('S19_ENGINE_RESTORED_FROM_IMMUTABLE_TEACHER_CORE',len(corefiles))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--local-pinned-dir');a=p.parse_args()
    run(a.local_pinned_dir)