"""Explicit opt-in model download for a Windows offline use of Artin V3.

It does not install anything automatically. The user must invoke --download-asr.
Network access and substantial storage are required during this setup ONLY.
"""
import argparse
from pathlib import Path

WHISPER_MODEL_NAMES={'tiny','base','small','medium','large-v3'}


def download_asr(size,target):
    if size not in WHISPER_MODEL_NAMES:
        raise ValueError('Unsupported preset; use one of '+', '.join(sorted(WHISPER_MODEL_NAMES)))
    try:
        from faster_whisper.utils import download_model
    except ImportError as e:
        raise RuntimeError('Install faster-whisper before downloading ASR model') from e
    target=Path(target).expanduser().resolve()
    target.mkdir(parents=True,exist_ok=True)
    print('User-authorized download:',size,'target:',target)
    location=download_model(size,output_dir=str(target),local_files_only=False)
    if not (target/'model.bin').is_file() or not (target/'config.json').is_file():
        raise RuntimeError('Download finished but required model.bin/config.json missing')
    print('LOCAL ASR MODEL READY AT:',location)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--download-asr',choices=sorted(WHISPER_MODEL_NAMES),required=True)
    p.add_argument('--target',type=Path,required=True)
    a=p.parse_args()
    download_asr(a.download_asr,a.target)

if __name__=='__main__':main()
