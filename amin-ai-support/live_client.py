#!/usr/bin/env python3
"""Interactive Windows terminal client for Amin's full-duplex WebSocket service.

One WebSocket can receive status / answers while the operator continues typing
new questions and work requests. No API key is sent in the URL.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit
from windows_delivery import deliver, validate_release

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

TOKEN = re.compile(r"amin_[A-Za-z0-9_-]{40,60}\Z")
PROJECT = re.compile(r"[a-z][a-z0-9_-]{1,60}\Z")
JOB = re.compile(r"[a-f0-9]{32}\Z")


def safe_url(raw: str) -> str:
    p = urlsplit(raw)
    loopback = p.hostname in {"localhost", "127.0.0.1", "::1"}
    if (p.scheme != "wss" and not (p.scheme == "ws" and loopback)) or not p.hostname:
        raise ValueError("Remote WebSocket requires WSS; WS is loopback-only")
    if p.username or p.password or p.path not in {"", "/"} or p.query or p.fragment:
        raise ValueError("No URL path, query, password or fragment allowed")
    return raw


async def run(url, token):
    if not TOKEN.fullmatch(token):
        raise ValueError("Program-scoped client token required")
    async with connect(safe_url(url), max_size=16000, open_timeout=12) as ws:
        await ws.send(json.dumps({"type": "auth", "token": token}))
        ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=12))
        if ready.get("type") != "ready":
            raise RuntimeError("Live handshake failed")
        project = ready["project"]
        print("Connected to scoped live project:", project, flush=True)
        print("Commands: ask <text>, work windows build <text>, resume <job-id>, deliver, quit", flush=True)
        ident = 0
        most_recent_artifact = None

        async def read_updates():
            nonlocal most_recent_artifact
            async for text in ws:
                message = json.loads(text)
                kind = message.get("type")
                if kind == "answer":
                    print("\n[ANSWER] " + message.get("answer", ""), flush=True)
                elif kind == "work_state":
                    print("\n[WORK] status=" + str(message.get("status"))
                          + " job_id=" + str(message.get("id_of_job", ""))
                          + " action_performed=" + str(message.get("action_performed", False)),
                          flush=True)
                    if message.get("answer"):
                        print("[WORK ANSWER] " + message["answer"], flush=True)
                    artifact = message.get("artifact")
                    if isinstance(artifact, dict) and artifact.get("environment") == "windows":
                        try:
                            validate_release(artifact["url"], artifact["sha256"])
                            most_recent_artifact = artifact
                            print("[DELIVERY READY] Verified metadata; type 'deliver' to download"
                                  " after explicit permission. No automatic execution.", flush=True)
                        except (ValueError, KeyError, TypeError):
                            print("[DELIVERY REJECTED] Unsafe artifact metadata", flush=True)
                elif kind in {"progress", "error"}:
                    print("\n[" + kind.upper() + "] " + str(message.get("message", "")),
                          flush=True)
                elif kind == "accepted":
                    print("\n[ACCEPTED] " + message.get("id", ""), flush=True)

        reader = asyncio.create_task(read_updates())
        try:
            while not reader.done():
                line = (await asyncio.to_thread(input, "\nAmin live> ")).strip()
                if line in {"quit", "exit", "0"}:
                    break
                kind, _, data = line.partition(" ")
                if kind == "deliver":
                    if not most_recent_artifact:
                        print("No validated Windows release was returned.")
                        continue
                    permission = (await asyncio.to_thread(input,
                          "Download verified release to Downloads/Amin AI? (yes/no): ")).strip().lower()
                    if permission != "yes":
                        continue
                    try:
                        destination = Path.home() / "Downloads" / "Amin AI"
                        result = await asyncio.to_thread(
                            deliver, most_recent_artifact["url"],
                            most_recent_artifact["sha256"], destination)
                        print("[DELIVERED] " + json.dumps(result, ensure_ascii=False))
                    except (ValueError, OSError, RuntimeError) as problem:
                        print("[DELIVERY FAILED] " + str(problem))
                    continue
                if kind not in {"ask", "work", "resume"} or not data.strip():
                    print("Use: ask <text> | work windows build <text> | resume <jobid> | deliver | quit")
                    continue
                if kind == "work":
                    target, sep, remainder = data.partition(" ")
                    operation, sep2, requested = remainder.partition(" ")
                    if target not in {"android", "windows", "web", "github", "none"} or (
                       operation not in {"answer", "build", "repair", "analyze", "release"}) or not requested:
                        print("Use: work <android|windows|web|github|none> "
                              "<build|repair|analyze|release|answer> <request text>")
                        continue
                    confirm = (await asyncio.to_thread(input,
                              "Send request to private GitHub for stated environment? (yes/no): ")).strip().lower()
                    if confirm != "yes":
                        continue
                    ask_chatgpt = False  # Direct SIWC model mode does not need Work.
                    permit_write = (await asyncio.to_thread(input,
                        "Allow ChatGPT to commit to isolated branch and create DRAFT PR? (yes/no): "
                        )).strip().lower() == "yes"
                    permit_public = False
                    if permit_write:
                        permit_public = (await asyncio.to_thread(input,
                            "If configured repo is PUBLIC, also allow public code changes? (yes/no): "
                            )).strip().lower() == "yes"
                if kind == "resume" and not JOB.fullmatch(data.strip()):
                    print("Invalid job id")
                    continue
                ident += 1
                message = {"type": kind, "id": "pc" + str(ident), "project": project}
                if kind == "resume":
                    message["job_id"] = data.strip()
                else:
                    message["message"] = data.strip()
                if kind == "work":
                    message["message"] = requested
                    message["target_environment"] = target
                    message["requested_operation"] = operation
                    message["request_key"] = secrets.token_hex(16)
                    message["consent"] = True
                    message["chatgpt_work_event"] = ask_chatgpt
                    message["authorize_github_write"] = permit_write
                    message["authorize_public_repo"] = permit_public
                await ws.send(json.dumps(message, ensure_ascii=False))
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Amin full-duplex Windows client")
    parser.add_argument("--url", default="ws://127.0.0.1:8766")
    args = parser.parse_args(argv)
    token = os.environ.get("AMIN_SUPPORT_CLIENT_TOKEN", "")
    asyncio.run(run(args.url, token))


if __name__ == "__main__":
    main()
