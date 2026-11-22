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
from urllib.parse import urlsplit

from amin_support import DEFAULT_CONFIG, DEFAULT_DB, SupportEngine
from direct_github_relay import GitHubPrivateBridge
from chatgpt_work_event import prepare_work_event
from chatgpt_plan_direct import ask as chatgpt_plan_ask, PlanConnectionUnavailable
from chatgpt_git_agent import run_agent as run_chatgpt_git_agent
from github_agent_tools import AgentToolError
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
ALLOWED_TARGETS = {"android", "windows", "web", "github", "none"}
ALLOWED_OPERATIONS = {"answer", "build", "repair", "analyze", "release"}


def trusted_browser_origins(local_host: bool, configured=""):
    """Deny arbitrary browser origins; Android/Windows native clients send no Origin.

    Public browser deployments must opt in the exact HTTPS site hosting the UI.
    Origins cannot contain credentials, paths, query strings or wildcards.
    """
    allowed = [None]
    if local_host:
        allowed.extend(["http://127.0.0.1:8765", "http://localhost:8765"])
    for item in configured.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        if len(candidate) > 260 or "*" in candidate or "\\" in candidate:
            raise ValueError("Invalid WebSocket origin allowlist entry")
        parsed = urlsplit(candidate)
        host = parsed.hostname
        if (not host or parsed.username or parsed.password or parsed.path
                or parsed.query or parsed.fragment or parsed.port == 0
                or (parsed.scheme != "https"
                    and not (local_host and parsed.scheme == "http"
                             and host in {"127.0.0.1", "localhost", "::1"}))):
            raise ValueError("Only explicit HTTPS browser origins or local loopback are permitted")
        if parsed.port is not None and parsed.port > 65535:
            raise ValueError("Invalid WebSocket origin port")
        if candidate not in allowed:
            allowed.append(candidate)
    return allowed


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
                request_key TEXT NOT NULL DEFAULT '',
                chatgpt_work_event INTEGER NOT NULL DEFAULT 0,
                github_write_authorized INTEGER NOT NULL DEFAULT 0,
                github_public_authorized INTEGER NOT NULL DEFAULT 0,
                agent_result_json TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                target_environment TEXT NOT NULL DEFAULT 'none',
                requested_operation TEXT NOT NULL DEFAULT 'answer',
                repo TEXT NOT NULL DEFAULT '',
                issue_number INTEGER NOT NULL DEFAULT 0,
                request_id TEXT NOT NULL DEFAULT '',
                answer TEXT NOT NULL DEFAULT '',
                needs_human INTEGER NOT NULL DEFAULT 1,
                action_performed INTEGER NOT NULL DEFAULT 0,
                artifact_json TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            cols = {r[1] for r in db.execute("PRAGMA table_info(amin_live_work)")}
            if "target_environment" not in cols:
                db.execute("ALTER TABLE amin_live_work ADD COLUMN target_environment TEXT NOT NULL DEFAULT 'none'")
            if "requested_operation" not in cols:
                db.execute("ALTER TABLE amin_live_work ADD COLUMN requested_operation TEXT NOT NULL DEFAULT 'answer'")
            if "artifact_json" not in cols:
                db.execute("ALTER TABLE amin_live_work ADD COLUMN artifact_json TEXT NOT NULL DEFAULT ''")
            if "request_key" not in cols:
                db.execute("ALTER TABLE amin_live_work ADD COLUMN request_key TEXT NOT NULL DEFAULT ''")
            if "chatgpt_work_event" not in cols:
                db.execute("ALTER TABLE amin_live_work ADD COLUMN chatgpt_work_event INTEGER NOT NULL DEFAULT 0")
            if "github_write_authorized" not in cols:
                db.execute("ALTER TABLE amin_live_work ADD COLUMN github_write_authorized INTEGER NOT NULL DEFAULT 0")
            if "github_public_authorized" not in cols:
                db.execute("ALTER TABLE amin_live_work ADD COLUMN github_public_authorized INTEGER NOT NULL DEFAULT 0")
            if "agent_result_json" not in cols:
                db.execute("ALTER TABLE amin_live_work ADD COLUMN agent_result_json TEXT NOT NULL DEFAULT ''")
            db.execute("CREATE INDEX IF NOT EXISTS amin_live_owner ON amin_live_work(token_id,project_id)")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS amin_live_idempotent "
                       "ON amin_live_work(token_id,project_id,request_key) WHERE request_key != ''")

    def connect(self):
        return sqlite3.connect(str(self.db_path), timeout=20)

    def new(self, project, token_id, question, target_environment="none", requested_operation="answer"):
        if target_environment not in ALLOWED_TARGETS or requested_operation not in ALLOWED_OPERATIONS:
            raise ValueError("Unknown environment or operation")
        ident = uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO amin_live_work(id,project_id,token_id,question,status,target_environment,requested_operation)"
                       " VALUES(?,?,?,?,?,?,?)", (ident, project, token_id, question, "queued",
                                                target_environment, requested_operation))
        return ident

    def new_once(self, project, token_id, question, target_environment="none",
                 requested_operation="answer", request_key="", chatgpt_work_event=False,
                 github_write_authorized=False, github_public_authorized=False):
        """Atomically accept a client request at most once per token and project.

        A fresh key makes a fresh job. Replaying the SAME key returns its previous
        durable id and never submits another Issue/PR. Legacy clients without a
        key keep the previous behavior for backward compatibility.
        """
        if not request_key:
            return self.new(project, token_id, question, target_environment,
                            requested_operation), True
        if not isinstance(request_key, str) or not JOB_ID.fullmatch(request_key):
            raise ValueError("Invalid idempotency key")
        if target_environment not in ALLOWED_TARGETS or requested_operation not in ALLOWED_OPERATIONS:
            raise ValueError("Unknown environment or operation")
        ident = uuid4().hex
        with self.connect() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO amin_live_work"
                "(id,project_id,token_id,question,status,target_environment,"
                "requested_operation,request_key,chatgpt_work_event,github_write_authorized,"
                "github_public_authorized) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (ident, project, token_id, question, "queued", target_environment,
                 requested_operation, request_key, int(chatgpt_work_event),
                 int(github_write_authorized), int(github_public_authorized)))
            actual = db.execute(
                "SELECT id,question,target_environment,requested_operation,chatgpt_work_event,"
                "github_write_authorized,github_public_authorized "
                "FROM amin_live_work WHERE project_id=? AND token_id=? AND request_key=?",
                (project, token_id, request_key)).fetchone()
        if not actual:
            raise RuntimeError("Durable idempotency record unavailable")
        # Reusing a key with a DIFFERENT request is an error, not a silent reroute.
        if actual[1:] != (question, target_environment,
                             requested_operation, int(chatgpt_work_event),
                             int(github_write_authorized), int(github_public_authorized)):
            raise ValueError("Request key belongs to a different work request")
        return actual[0], cursor.rowcount == 1

    def read(self, ident, project, token_id):
        if not isinstance(ident, str) or not JOB_ID.fullmatch(ident):
            return None
        with self.connect() as db:
            row = db.execute(
                "SELECT status,repo,issue_number,request_id,answer,needs_human,"
                "action_performed,target_environment,requested_operation,artifact_json,agent_result_json "
                "FROM amin_live_work "
                "WHERE id=? AND project_id=? AND token_id=?",
                (ident, project, token_id)).fetchone()
        if not row:
            return None
        return dict(zip(("status", "repo", "issue_number", "request_id",
                         "answer", "needs_human", "action_performed",
                         "target_environment", "requested_operation", "artifact_json",
                         "agent_result_json"), row), id=ident,
                    project=project)

    def change(self, ident, status, **fields):
        keys = {"repo", "issue_number", "request_id", "answer", "needs_human",
                "action_performed", "artifact_json", "agent_result_json"}
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
        # A server-wide private GitHub token is OWNER-ONLY. Customers must
        # connect their own private repository from their own device.
        self.owner_token_id = os.environ.get("AMIN_LIVE_OWNER_TOKEN_ID", "")
        # Explicit opt-in only. This is personal plan usage for the OWNER,
        # not a shared unlimited AI subscription for all customers.
        self.use_chatgpt_plan = os.environ.get("AMIN_SIWC_ENABLE") == "1"
        self.use_github_agent = os.environ.get("AMIN_SIWC_AGENT_ENABLE") == "1"
        self.agent_token = os.environ.get("AMIN_AGENT_GITHUB_TOKEN", "")
        try:
            mapping = json.loads(os.environ.get("AMIN_AGENT_PROJECT_REPOS_JSON", "{}"))
        except (ValueError, TypeError):
            raise ValueError("Invalid authorized project-repository mapping") from None
        if not isinstance(mapping, dict):
            raise ValueError("Authorized project repository mapping must be an object")
        self.agent_project_repos = mapping
        self.agent_public_optin = os.environ.get("AMIN_AGENT_ALLOW_PUBLIC") == "1"
        self.poll_seconds = max(2, int(poll_seconds))
        self.limits = SlidingLimits()
        self.sem = asyncio.Semaphore(8)
        self.detached_work = set()

    async def send(self, socket, kind, message_id, **fields):
        try:
            await socket.send(json.dumps({"type": kind, "id": message_id, **fields},
                                         ensure_ascii=False, separators=(",", ":")))
        except ConnectionClosed:
            # A disconnected client must not cancel server-side approved work.
            pass

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
                        personal_chatgpt_connected=False,
                        chatgpt_plan_mode=("siwc_user_authorized"
                             if self.use_chatgpt_plan
                             and self.owner_token_id == access["token_id"]
                             else "disabled"),
                        live_tools="owner_hosted")
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
                route = "chat" if action == "ask" else "ticket"
                if (command.get("project") != access["project_id"] or
                        not self.limits.allow(access["token_id"], route, 30 if action == "ask" else 8)):
                    await self.send(socket, "error", ident, message="Project denied or rate limit exceeded")
                    continue
                if len(outstanding) >= 8 or len(self.detached_work) >= 32 or ident in active_ids:
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
                    if action == "work" and not isinstance(command.get("chatgpt_work_event", False), bool):
                        await self.send(socket, "error", ident, message="Invalid Work event permission")
                        continue
                    if action == "work" and (
                        not isinstance(command.get("authorize_github_write", False), bool) or
                        not isinstance(command.get("authorize_public_repo", False), bool)):
                        await self.send(socket, "error", ident,
                                        message="Invalid GitHub execution permission")
                        continue
                    if (action == "work" and (command.get("authorize_github_write", False)
                         or command.get("authorize_public_repo", False))
                         and not command.get("request_key")):
                        await self.send(socket, "error", ident,
                                        message="GitHub execution requires a unique request key")
                        continue
                    if (action == "work" and command.get("chatgpt_work_event") is True
                            and not command.get("request_key")):
                        await self.send(socket, "error", ident,
                                        message="ChatGPT Work event requires a 128-bit request key")
                        continue
                    if action == "work" and ("request_key" in command and
                            (not isinstance(command["request_key"], str) or
                             not JOB_ID.fullmatch(command["request_key"]))):
                        await self.send(socket, "error", ident, message="Invalid work idempotency key")
                        continue
                    if action == "work" and (
                        command.get("target_environment", "none") not in ALLOWED_TARGETS or
                        command.get("requested_operation", "answer") not in ALLOWED_OPERATIONS):
                        await self.send(socket, "error", ident, message="Unknown target or operation")
                        continue
                active_ids.add(ident)
                task = asyncio.create_task(
                    self.perform(socket, access, command),
                    name="amin-live-" + ident)
                if action == "work":
                    # Persist approved work even if the phone loses connectivity.
                    self.detached_work.add(task)
                    task.add_done_callback(self.detached_work.discard)
                else:
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
                units = await asyncio.to_thread(
                    self.engine.quotas.reserve, access["token_id"], "chat")
                if units == "exhausted":
                    await self.send(socket, "error", ident, message="Chat quota exhausted")
                    return
                await self.send(socket, "accepted", ident, mode="answer", status="working")
                if self.use_chatgpt_plan:
                    if not self.owner_token_id or access["token_id"] != self.owner_token_id:
                        await self.send(socket, "error", ident,
                                        message="ChatGPT plan is owner-only; user must authorize own plan")
                        return
                    try:
                        async with self.sem:
                            result = await asyncio.to_thread(chatgpt_plan_ask, command["message"])
                    except PlanConnectionUnavailable as error:
                        await self.send(socket, "error", ident,
                                        message="ChatGPT sign-in/plan usage unavailable; no paid fallback",
                                        chatgpt_connected=False)
                        return
                    await self.send(socket, "answer", ident, status="answered",
                                    answer=result["answer"], sources=[],
                                    model_used=True, provider="ChatGPT plan OAuth",
                                    model=result["model"], needs_human=False,
                                    action_performed=False)
                else:
                    async with self.sem:
                        result = await asyncio.to_thread(
                            self.engine.answer, project, command["message"], "customer", False)
                    await self.send(socket, "answer", ident, status="answered",
                                    answer=result["answer"], sources=result["sources"],
                                    model_used=result["model_used"],
                                    needs_human=result["needs_human"], action_performed=False)
            elif action == "work":
                await self.run_work(socket, access, command)
            else:
                job = await asyncio.to_thread(
                    self.jobs.read, command.get("job_id"), project, access["token_id"])
                if job is None:
                    await self.send(socket, "error", ident, message="Job not found")
                    return
                payload = {key: value for key, value in job.items()
                           if key not in {"id", "artifact_json", "agent_result_json"}}
                if job.get("artifact_json"):
                    payload["artifact"] = json.loads(job["artifact_json"])
                if job.get("agent_result_json"):
                    payload["agent_result"] = json.loads(job["agent_result_json"])
                await self.send(socket, "work_state", ident,
                                id_of_job=job["id"], **payload)
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
        units = await asyncio.to_thread(
            self.engine.quotas.reserve, access["token_id"], "ticket")
        if units == "exhausted":
            await self.send(socket, "error", ident, message="Work quota exhausted")
            return
        target = command.get("target_environment", "none")
        operation = command.get("requested_operation", "answer")
        job_id, created = await asyncio.to_thread(
            self.jobs.new_once, project, access["token_id"], command["message"].strip(),
            target, operation, command.get("request_key", ""),
            command.get("chatgpt_work_event", False),
            command.get("authorize_github_write", False),
            command.get("authorize_public_repo", False))
        if not created:
            if units not in {"unmetered", "exhausted"}:
                await asyncio.to_thread(
                    self.engine.quotas.refund, access["token_id"], "ticket", units)
            prior = await asyncio.to_thread(
                self.jobs.read, job_id, project, access["token_id"])
            await self.send(socket, "work_state", ident, id_of_job=job_id,
                            status=prior["status"], duplicate_suppressed=True,
                            action_performed=False, chatgpt_invoked=False)
            if prior["status"] == "github_dispatched":
                await self.watch(socket, ident, prior)
            return
        await self.send(socket, "work_state", ident, id_of_job=job_id,
                        status="queued", action_performed=False)
        if self.use_github_agent:
            await self.run_agent_work(socket, access, command, job_id, units)
            return
        if (not self.repo or not self.github_token
                or not self.owner_token_id
                or access["token_id"] != self.owner_token_id):
            if units not in {"unmetered", "exhausted"}:
                await asyncio.to_thread(self.engine.quotas.refund, access["token_id"], "ticket", units)
            await asyncio.to_thread(self.jobs.change, job_id, "needs_setup")
            await self.send(socket, "work_state", ident, id_of_job=job_id,
                            status="needs_setup",
                            message="Only owner-scoped bridge may use configured GitHub token. "
                                    "Customers use their own private GitHub connection.",
                            action_performed=False, chatgpt_invoked=False)
            return
        async with self.sem:
            try:
                # Only the configured *verified private* repository is used.
                bridge = GitHubPrivateBridge(self.repo, self.github_token)
                result = await asyncio.to_thread(
                    bridge.submit, project, command["message"], "live_gateway",
                    target, operation)
            except (ValueError, RuntimeError):
                if units not in {"unmetered", "exhausted"}:
                    await asyncio.to_thread(self.engine.quotas.refund, access["token_id"], "ticket", units)
                await asyncio.to_thread(self.jobs.change, job_id, "dispatch_failed")
                await self.send(socket, "work_state", ident, id_of_job=job_id,
                                status="dispatch_failed", action_performed=False)
                return
        await asyncio.to_thread(self.jobs.change, job_id, "github_dispatched",
                                repo=self.repo, issue_number=result["issue_number"],
                                request_id=result["request_id"])
        await self.send(socket, "work_state", ident, id_of_job=job_id,
                        status="github_dispatched", issue_number=result["issue_number"],
                        target_environment=target, requested_operation=operation,
                        chatgpt_invoked=False, action_performed=False)
        if command.get("chatgpt_work_event") is True:
            # One user-confirmed work request -> private Issue -> private PR event.
            # DOES NOT prove an eligible ChatGPT Work task is installed/running.
            try:
                work_event = await asyncio.to_thread(
                    prepare_work_event, bridge, result["issue_number"], result["request_id"])
                await self.send(socket, "progress", ident,
                                status="chatgpt_work_event_created",
                                pull_request_number=work_event["pull_request_number"],
                                chatgpt_invoked=False,
                                chatgpt_task_configured=False,
                                message="Private PR event emitted; ChatGPT Work connection remains unverified")
            except (ValueError, RuntimeError, KeyError):
                # Do not lose the private Issue or mistakenly claim model execution.
                await self.send(socket, "progress", ident,
                                status="chatgpt_work_event_failed",
                                chatgpt_invoked=False,
                                message="Private Issue saved, but Work PR event could not be created")
        job = await asyncio.to_thread(self.jobs.read, job_id, project, access["token_id"])
        await self.watch(socket, ident, job)

    async def run_agent_work(self, socket, access, command, job_id, units):
        """Run the user-authorized SIWC agent; never fall back to paid API/Work."""
        ident = command["id"]
        project = access["project_id"]
        repo = self.agent_project_repos.get(project)
        if (not self.use_chatgpt_plan or
                not self.owner_token_id or access["token_id"] != self.owner_token_id or
                not isinstance(repo, str) or not repo or not self.agent_token):
            await asyncio.to_thread(self.jobs.change, job_id, "agent_needs_setup")
            if units not in {"unmetered", "exhausted"}:
                await asyncio.to_thread(
                    self.engine.quotas.refund, access["token_id"], "ticket", units)
            await self.send(socket, "work_state", ident, id_of_job=job_id,
                            status="agent_needs_setup", chatgpt_invoked=False,
                            action_performed=False,
                            message="Owner ChatGPT plan login and a scoped project GitHub repo are required")
            return
        if command.get("chatgpt_work_event"):
            await asyncio.to_thread(self.jobs.change, job_id, "agent_conflicting_modes")
            await self.send(socket, "work_state", ident, id_of_job=job_id,
                            status="agent_conflicting_modes", action_performed=False,
                            message="Direct ChatGPT agent cannot also route to ChatGPT Work")
            return
        writable = command.get("authorize_github_write") is True
        public = command.get("authorize_public_repo") is True and self.agent_public_optin
        await asyncio.to_thread(self.jobs.change, job_id, "chatgpt_running", repo=repo)
        await self.send(socket, "work_state", ident, id_of_job=job_id,
                        status="chatgpt_running", repo=repo, action_performed=False,
                        chatgpt_invoked=False)
        try:
            async with self.sem:
                result = await asyncio.to_thread(
                    run_chatgpt_git_agent, command["message"], repo, self.agent_token,
                    job_id, allow_write=writable, allow_public=public)
        except PlanConnectionUnavailable:
            status = "chatgpt_login_or_quota_blocked"
        except (AgentToolError, RuntimeError, ValueError):
            status = "agent_execution_failed"
        else:
            # Only an observed GitHub commit counts as a source change.
            status = result["status"]
            safe_result = {key: value for key, value in result.items()
                           if key not in {"token", "access_token"}}
            await asyncio.to_thread(self.jobs.change, job_id, status,
                                    answer=result.get("answer", ""),
                                    action_performed=int(result.get("action_performed", False)),
                                    needs_human=int(not (
                                        status == "draft_pr_created" and result.get("tests_passed"))),
                                    agent_result_json=json.dumps(safe_result, ensure_ascii=False))
            await self.send(socket, "work_state", ident,
                            id_of_job=job_id, status=status, agent_result=safe_result,
                            action_performed=result.get("action_performed", False),
                            chatgpt_invoked=result.get("model_used", False))
            return
        await asyncio.to_thread(self.jobs.change, job_id, status)
        await self.send(socket, "work_state", ident,
                        id_of_job=job_id, status=status, action_performed=False,
                        chatgpt_invoked=False)

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
            artifact = result.get("artifact")
            if artifact and artifact.get("environment") != job.get("target_environment"):
                artifact = None
            # A GitHub comment is a report, NOT independently verified execution.
            state = ("deliverable_ready" if artifact else
                     "execution_reported_unverified" if action_performed else
                     "needs_action" if needs_human else "answered_no_execution")
            await asyncio.to_thread(self.jobs.change, job["id"], state,
                                    answer=result["answer"],
                                    needs_human=int(needs_human),
                                    action_performed=0,
                                    artifact_json=json.dumps(artifact) if artifact else "")
            outgoing = {"id_of_job": job["id"], "status": state,
                        "answer": result["answer"], "needs_human": needs_human,
                        "action_performed": False}
            if artifact:
                outgoing["artifact"] = artifact
            await self.send(socket, "work_state", ident, **outgoing)
            return
        await self.send(socket, "progress", ident, status="still_pending",
                        message="Work remains in GitHub; resume later with job id")


async def run_server(engine, host, port, cert=None, key=None, repo="", github_token="", allowed_origins=""):
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
    browser_origins = trusted_browser_origins(local, allowed_origins)
    gateway = LiveGateway(engine, repo, github_token)
    async with serve(gateway.handler, host, port, ssl=context, origins=browser_origins,
                     max_size=16000, ping_interval=20, ping_timeout=20, max_queue=16) as server:
        await server.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Amin full duplex WebSocket gateway")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--tls-cert", type=Path)
    parser.add_argument("--tls-key", type=Path)
    parser.add_argument("--allowed-origin", action="append", default=[],
                        help="Exact trusted HTTPS web UI origin; repeat for each public site")
    args = parser.parse_args(argv)
    engine = SupportEngine(args.config, args.db)
    if engine.access.active_count() == 0:
        parser.error("Issue a project-scoped token before starting the live gateway")
    repo = os.environ.get("AMIN_LIVE_GITHUB_REPO", "")
    secret = os.environ.get("AMIN_LIVE_GITHUB_TOKEN", "")
    origins = ",".join(args.allowed_origin) or os.environ.get("AMIN_LIVE_ALLOWED_ORIGINS", "")
    asyncio.run(run_server(engine, args.host, args.port, args.tls_cert, args.tls_key,
                           repo, secret, origins))


if __name__ == "__main__":
    main()
