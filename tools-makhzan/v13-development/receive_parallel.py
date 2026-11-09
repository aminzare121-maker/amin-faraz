"""Bounded parallel MP4 receiver for the pinned V13 preparation engine."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import re
import sys
import urllib.request


def receive(url, output, engine, serial):
    engine._allowed_https(url)
    opener = urllib.request.build_opener(engine.SourceRedirectSafe)

    def request(start, end, tag=None):
        headers = {"User-Agent": "Mozilla/5.0", "Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"}
        if tag is not None:
            headers["If-Match"] = tag
        return opener.open(urllib.request.Request(url, headers=headers), timeout=60)

    with request(0, 63) as response:
        tag = response.headers.get("ETag", "")
        span = re.fullmatch(r"bytes 0-63/(\d+)", response.headers.get("Content-Range", ""))
        supported = response.status == 206 and span and re.fullmatch(r'"[^"]+"', tag)
        if supported and b"ftyp" not in response.read(64)[:24]:
            raise ValueError("Source probe is not an MP4")
    if not supported:
        return serial(url, output)
    size = int(span.group(1))
    if not 1024 <= size <= engine.MAX_BYTES:
        raise ValueError("Invalid source size")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    block_size = 8 * 1024 * 1024
    # Independent handles permit disjoint writes on Linux and Windows.
    def copy_range(start):
        end = min(start + block_size, size) - 1
        with request(start, end, tag) as response, output.open("r+b") as dest:
            if (response.status != 206 or response.headers.get("ETag") != tag or
                    response.headers.get("Content-Range") != f"bytes {start}-{end}/{size}"):
                raise ValueError("Source version or byte range changed")
            dest.seek(start)
            remaining = end - start + 1
            while remaining:
                data = response.read(min(1 << 20, remaining))
                if not data:
                    raise ValueError("Truncated source range")
                dest.write(data)
                remaining -= len(data)
            if response.read(1):
                raise ValueError("Oversized source range")
    with output.open("xb") as dest:
        dest.truncate(size)
    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(copy_range, range(0, size, block_size)))
        with output.open("rb") as source:
            if b"ftyp" not in source.read(24):
                raise ValueError("Reassembled source is not MP4")
            source.seek(0)
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        return size, digest
    except BaseException:
        output.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    # Adapter lives only in this isolated process, never in the queue worker.
    sys.path.insert(0, os.path.abspath(sys.argv.pop(1)))
    import video001_v13_remote_prep as engine
    serial = engine.download_once
    engine.download_once = lambda url, output: receive(url, output, engine, serial)
    engine.main()
