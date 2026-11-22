#!/usr/bin/env bash
# Package a real OFFLINE Persian ASR and neural TTS into the Android APK.
# Build MUST fail if any required model is absent. No paid API or Codex.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ASSETS="$ROOT/app/src/main/assets/offline_voice"
LIBS="$ROOT/app/libs"
CACHE="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/amin-fa-voice-assets"
mkdir -p "$CACHE" "$ASSETS/tts" "$LIBS"
AAR="$LIBS/sherpa-onnx.aar"
TTS_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-fa_IR-gyro-medium.tar.bz2"
ESPEAK_URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/espeak-ng-data.tar.bz2"
VOSK_URL="https://alphacephei.com/vosk/models/vosk-model-small-fa-0.42.zip"
AAR_URL="https://huggingface.co/csukuangfj/sherpa-onnx-libs/resolve/main/android/aar/sherpa-onnx-1.10.41.aar"
get_file() {
  local url="$1" out="$2"
  if [ ! -s "$out" ]; then
    curl --fail --location --retry 3 --connect-timeout 25 --max-time 480 "$url" -o "$out.tmp"
    mv "$out.tmp" "$out"
  fi
}
get_file "$AAR_URL" "$AAR"
get_file "$TTS_URL" "$CACHE/persian-gyro.tar.bz2"
get_file "$ESPEAK_URL" "$CACHE/espeak-ng-data.tar.bz2"
get_file "$VOSK_URL" "$CACHE/vosk-small-fa.zip"
python3 - "$CACHE" "$ASSETS" "$AAR" <<'PY'
import io, sys, tarfile, zipfile, shutil
from pathlib import Path
cache, assets, aar = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
tts = assets / 'tts'
tts.mkdir(exist_ok=True, parents=True)

def members_from_tar(p):
    with tarfile.open(p,'r:bz2') as archive:
        for item in archive:
            if not item.isfile():
                continue
            # Do not extract paths blindly from the Internet.
            name = Path(item.name).name
            if name in ('fa_IR-gyro-medium.onnx','tokens.txt'):
                data = archive.extractfile(item).read()
                yield name,data
def unpack_model():
    found = {}
    for name,data in members_from_tar(cache / 'persian-gyro.tar.bz2'):
        found[name] = data
    if set(found) != {'fa_IR-gyro-medium.onnx','tokens.txt'}:
        raise RuntimeError('Persian neural TTS model or tokens missing')
    if len(found['fa_IR-gyro-medium.onnx']) < 10_000_000:
        raise RuntimeError('Persian ONNX model truncated')
    (tts/'model_fa.onnx').write_bytes(found['fa_IR-gyro-medium.onnx'])
    (tts/'tokens_fa.txt').write_bytes(found['tokens.txt'])
unpack_model()
with tarfile.open(cache/'espeak-ng-data.tar.bz2','r:bz2') as tar:
    copied = 0
    for item in tar:
        if not item.isfile():
            continue
        segments = Path(item.name).parts
        if 'espeak-ng-data' not in segments:
            continue
        n = segments.index('espeak-ng-data')
        rest = segments[n+1:]
        if not rest or any(p in ('..','.') for p in rest):
            continue
        path = tts/'espeak-ng-data'/Path(*rest)
        if not path.resolve().is_relative_to((tts/'espeak-ng-data').resolve()):
            raise RuntimeError('Unsafe espeak data archive')
        path.parent.mkdir(parents=True,exist_ok=True)
        with tar.extractfile(item) as source, path.open('wb') as dest:
            shutil.copyfileobj(source,dest)
        copied+=1
    if copied < 10:
        raise RuntimeError('eSpeak phonemizer archive incomplete')
with zipfile.ZipFile(cache/'vosk-small-fa.zip') as z:
    copied = 0
    for item in z.infolist():
        if item.is_dir(): continue
        parts = Path(item.filename).parts
        if not parts or parts[0] != 'vosk-model-small-fa-0.42': continue
        rest = parts[1:]
        if not rest or any(p in ('..','.') for p in rest): continue
        relative = Path(*rest)
        path = assets/'model-fa'/relative
        if not path.resolve().is_relative_to((assets/'model-fa').resolve()):
            raise RuntimeError('Unsafe Vosk model archive')
        path.parent.mkdir(parents=True,exist_ok=True)
        with z.open(item) as source,path.open('wb') as dest:
            shutil.copyfileobj(source,dest)
        copied+=1
    if copied < 10 or not (assets/'model-fa/am/final.mdl').is_file():
        raise RuntimeError('Persian offline recognition model incomplete')
with zipfile.ZipFile(aar) as z:
    if not any(n.endswith('libonnxruntime.so') or n.endswith('libsherpa-onnx-jni.so') for n in z.namelist()):
        raise RuntimeError('Sherpa native Android runtime not found in AAR')
print('Offline Persian voice assets verified; TTS, phonemizer and speech-recognition are packaged')
PY
