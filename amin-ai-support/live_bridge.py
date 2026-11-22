#!/usr/bin/env python3
"""Optional live, full-duplex, per-client WebSocket gateway for Amin Support.

No schedule. A running, reachable gateway is mandatory; GitHub isn't a socket
transport, and this service cannot wake a private ChatGPT web conversation.

Messages are framed JSON, authenticated with an existing program-scoped token
AFTER the TLS WebSocket handshake (never in an URL or GitHub log).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sqlite3
import ssl
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from amin_support import DEFAULT_CONFIG, DEFAULT_DB, SupportEngine
from direct_github_relay import GitHubPrivateBridge
from request_limits import SlidingLimits

try:
    from websockets.asyncio.server import serve
    from websockets.exceptions import ConnectionClosed
except ImportError:
    serve = None
    class ConnectionClosed(Exception):
        pass

MSG_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
JOB_ID = re.compile(r"^[a-f0-9]{32}$")
LIVE_PROTOCOL = "amin.live.v1"


class LiveJobs:
    """Durable per-token work status; never accessible to another token."""
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS amin_live_work (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                token_id TEXT NOT NULL,
                question TEXT NOT NULL,
                status TEXT NOT NULL,
                repo TEXT NOT NULL DEFAULT '',
                issue_number INTEGER NOT NULL DEFAULT 0,
                request_id TEXT NOT NULL DEFAULT '',
                answer TEXT NOT NULL DEFAULT '',
                needs_human INTEGER NOT NULL DEFAULT 1,
                action_performed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS amin_live_owner ON amin_live_work(token_id,project_id)")

    def connect(self):
        return sqlite3.connect(str(self.db_path), timeout=20)

    def new(self, project, token_id, question):
        ident = uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO amin_live_work(id,project_id,token_id,question,status)"
                       " VALUES(?,?,?,?,?)", (ident, project, token_id, question, "queued"))
        return ident

    def read(self, ident, project, token_id):
        if not isinstance(ident, str) or not JOB_ID.fullmatch(ident):
            return None
        with self.connect() as db:
            row = db.execute(
                "SELECT status,repo,issue_number,request_id,answer,needs_human,"
                "action_performed FROM amin_live_work WHERE id=? AND project_id=? AND token_id=?",
                (ident, project, token_id)).fetchone()
        if not row:
            return None
        return dict(zip(("status", "repo", "issue_number", "request_id",
                         "answer", "needs_human", "action_performed"), row), id=ident,
                    project=project)

    def change(self, ident, status, **fields):
        keys = {"repo", "issue_number", "request_id", "answer", "needs_human", "action_performed"}
        if any(k not in keys for k in fields):
            raise ValueError("Unsafe state field")
        fields = {"status": status, **fields}
        sql = ", ".join(k + "=?" for k in fields)
        with self.connect() as db:
            db.execute(f"UPDATE amin_live_work SET {sql}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (*fields.values(), ident))


class LiveGateway:
    def __init__(self, engine, repo="", github_token="", poll_seconds=5):
        self.engine = engine
        self.jobs = LiveJobs(engine.knowledge.db_path)
        self.repo = repo
        self.github_token = github_token
        self.poll_seconds = max(2, int(poll_seconds))
        self.limits = SlidingLimits()
        self.sem = asyncio.Semaphore(8)

    async def send(self, socket, kind, message_id, **fields):
        await socket.send(json.dumps({"type": kind, "id": message_id, **fields},
                                     ensure_ascii=False, separators=(",", ":")))

    async def auth(self, socket):
        try:
            first = await asyncio.wait_for(socket.recv(), timeout=10)
            message = json.loads(first)
        except (asyncio.TimeoutError, ValueError, TypeError):
            await socket.close(code=1008, reason="Authentication required")
            return None
        if not isinstance(message, dict) or message.get("type") != "auth":
            await socket.close(code=1008, reason="Authentication required")
            return None
        access = self.engine.access.verify(message.get("token"))
        if not access or access["project_id"] not in self.engine.projects:
            await socket.close(code=1008, reason="Invalid credential")
            return None
        await self.send(socket, "ready", "auth", protocol=LIVE_PROTOCOL,
                        project=access["project_id"], duplex=True,
                        personal_chatgpt_connected=False, live_tools="owner_hosted")
        return access

    async def handler(self, socket):
        access = await self.auth(socket)
        if access is None:
            return
        outstanding = set()
        active_ids = set()
        try:
            async for frame in socket:
                if not isinstance(frame, str) or len(frame) > 16000:
                    await self.send(socket, "error", "", message="Invalid frame")
                    continue
                try:
                    command = json.loads(frame)
                except (ValueError, TypeError):
                    await self.send(socket, "error", "", message="Invalid JSON")
                    continue
                if not isinstance(command, dict):
                    await self.send(socket, "error", "", message="Invalid command")
                    continue
                ident = command.get("id", "")
                action = command.get("type")
                if not isinstance(ident, str) or not MSG_ID.fullmatch(ident):
                    await self.send(socket, "error", "", message="Request id must be 1-64 safe characters")
                    continue
                if action == "ping":
                    await self.send(socket, "pong", ident)
                    continue
                if action not in {"ask", "work", "resume"}:
                    await self.send(socket, "error", ident, message="Unsupported operation")
                    continue
                if (command.get("project") != access["project_id"] or
                        not self.limits.allow(access["token_id"], action, 30 if action == "ask" else 8)):
                    await self.send(socket, "error", ident, message="Project denied or rate limit exceeded")
                    continue
                if len(outstanding) >= 8 or ident in active_ids:
                    await self.send(socket, "error", ident, message="Busy or duplicate id")
                    continue
                if action == "work" and not access["allow_ticket"]:
                    await self.send(socket, "error", ident, message="Work permission required")
                    continue
                if action in {"ask", "work"}:
                    message = command.get("message")
                    if not isinstance(message, str) or not message.strip() or len(message) > 2500:
                        await self.send(socket, "error", ident, message="Question must be 1-2500 characters")
                        continue
                    if action == "work" and command.get("consent") is not True:
                        await self.send(socket, "error", ident, message="Explicit work consent required")
                        continue
                active_ids.add(ident)
                task = asyncio.create_task(
                    self.perform(socket, access, command),
                    name="amin-live-" + ident)
                outstanding.add(task)
                task.add_done_callback(outstanding.discard)
                task.add_done_callback(lambda _task, msg_id=ident: active_ids.discard(msg_id))
        except ConnectionClosed:
            pass
        finally:
            for task in outstanding:
                task.cancel()
            if outstanding:
                await asyncio.gather(*outstanding, return_exceptions=True)

    async def perform(self, socket, access, command):
        ident = command["id"]
        action = command["type"]
        project = access["project_id"]
        try:
            if action == "ask":
                await self.send(socket, "accepted", ident, mode="answer", status="working")
                async with self.sem:
                    result = await asyncio.to_thread(
                        self.engine.answer, project, command["message"], "customer", False)
                await self.send(socket, "answer", ident, status="answered", answer=result["answer"],
                                sources=result["sources"], model_used=result["model_used"],
                                needs_human=result["needs_human"], action_performed=False)
            elif action == "work":
                await self.run_work(socket, access, command)
            else:
                job = await asyncio.to_thread(
                    self.jobs.read, command.get("job_id"), project, access["token_id"])
                if job is None:
                    await self.send(socket, "error", ident, message="Job not found")
                    return
                await self.send(socket, "work_state", ident, **job)
                if job["status"] == "github_dispatched":
                    await self.watch(socket, ident, job)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # Exception class only: never leak credentials or private questions.
            with suppress(ConnectionClosed):
                await self.send(socket, "error", ident, message="Operation failed: " + type(error).__name__)

    async def run_work(self, socket, access, command):
        ident = command["id"]
        project = access["project_id"]
        job_id = await asyncio.to_thread(
            self.jobs.new, project, access["token_id"], command["message"].strip())
        await self.send(socket, "work_state", ident, id_of_job=job_id,
                        status="queued", action_performed=False)
        if not self.repo or not self.github_token:
            await asyncio.to_thread(self.jobs.change, job_id, "needs_setup")
            await self.send(socket, "work_state", ident, id_of_job=job_id,
                            status="needs_setup", message="Private GitHub worker not configured",
                            action_performed=False, chatgpt_invoked=False)
            return
        async with self.sem:
            try:
                # Only the configured *verified private* repository is used.
                bridge = GitHubPrivateBridge(self.repo, self.github_token)
                result = await asyncio.to_thread(bridge.submit, project, command["message"])
            except (ValueError, RuntimeError):
                await asyncio.to_thread(self.jobs.change, job_id, "dispatch_failed")
                await self.send(socket, "work_state", ident, id_of_job=job_id,
                                status="dispatch_failed", action_performed=False)
                return
        await asyncio.to_thread(self.jobs.change, job_id, "github_dispatched",
                                repo=self.repo, issue_number=result["issue_number"],
                                request_id=result["request_id"])
        await self.send(socket, "work_state", ident, id_of_job=job_id,
                        status="github_dispatched", issue_number=result["issue_number"],
                        chatgpt_invoked=False, action_performed=False)
        job = await asyncio.to_thread(self.jobs.read, job_id, project, access["token_id"])
        await self.watch(socket, ident, job)

    async def watch(self, socket, ident, job):
        issue = int(job["issue_number"])
        request_id = job["request_id"]
        if not issue or not request_id or job["repo"] != self.repo:
            return
        bridge = GitHubPrivateBridge(self.repo, self.github_token)
        # No schedule. Watch concurrently while the client connection is alive.
        # Reconnect with 'resume' for long operations. GitHub may be unavailable.
        for count in range(240):
            await asyncio.sleep(self.poll_seconds)
            try:
                result = await asyncio.to_thread(bridge.status, issue, request_id)
            except (ValueError, RuntimeError):
                if count in (0, 5, 20):
                    await self.send(socket, "progress", ident, status="github_wait",
                                    message="GitHub temporarily unavailable")
                continue
            if result["status"] != "answered":
                continue
            needs_human = bool(result.get("needs_human", True))
            action_performed = bool(result.get("action_performed", False))
            state = ("needs_action" if needs_human else
                     "executed" if action_performed else "answered_no_execution")
            await asyncio.to_thread(self.jobs.change, job["id"], state,
                                    answer=result["answer"],
                                    needs_human=int(needs_human),
                                    action_performed=int(action_performed))
            await self.send(socket, "work_state", ident, id_of_job=job["id"],
                            status=state, answer=result["answer"],
                            needs_human=needs_human, action_performed=action_performed)
            return
        await self.send(socket, "progress", ident, status="still_pending",
                        message="Work remains in GitHub; resume later with job id")


async def run_server(engine, host, port, cert=None, key=None, repo="", github_token=""):
    if serve is None:
        raise RuntimeError("Install the open-source 'websockets' package for live transport")
    if bool(cert) != bool(key):
        raise ValueError("Both TLS certificate and private key are required")
    local = host in {"127.0.0.1", "localhost", "::1"}
    if not local and not cert:
        raise ValueError("Remote WebSocket connections require TLS (wss)")
    context = None
    if cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(cert), str(key))
    gateway = LiveGateway(engine, repo, github_token)
    async with serve(gateway.handler, host, port, ssl=context, max_size=16000,
                     ping_interval=20, ping_timeout=20, max_queue=16) as server:
        await server.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Amin full duplex WebSocket gateway")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--tls-cert", type=Path)
    parser.add_argument("--tls-key", type=Path)
    args = parser.parse_args(argv)
    engine = SupportEngine(args.config, args.db)
    if engine.access.active_count() == 0:
        parser.error("Issue a project-scoped token before starting the live gateway")
    repo = os.environ.get("AMIN_LIVE_GITHUB_REPO", "")
    secret = os.environ.get("AMIN_LIVE_GITHUB_TOKEN", "")
    asyncio.run(run_server(engine, args.host, args.port, args.tls_cert, args.tls_key,
                           repo, secret))


if __name__ == "__main__":
    main()
