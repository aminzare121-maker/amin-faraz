"""Integration checks for actual concurrent full-duplex WebSocket messaging.

This is loopback integration, not a phone, public TLS, or a live coding agent.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from amin_support import SupportEngine
from live_bridge import LiveGateway, run_server


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        folder = Path(self.tmp.name)
        config = folder / "config.json"
        config.write_text(json.dumps({"projects": [
            {"id": "alpha", "name": "alpha", "source_prefixes": [], "public_paths": []},
            {"id": "beta", "name": "beta", "source_prefixes": [], "public_paths": []}
        ]}), encoding="utf8")
        self.engine = SupportEngine(config, folder / "support.sqlite3")
        self.alpha = self.engine.access.issue("alpha", allow_ticket=True)
        self.other = self.engine.access.issue("alpha", allow_ticket=True)
        self.beta = self.engine.access.issue("beta", allow_ticket=True)
        self.gateway = LiveGateway(self.engine)
        self.server = await serve(self.gateway.handler, "127.0.0.1", 0)
        self.url = "ws://127.0.0.1:" + str(self.server.sockets[0].getsockname()[1])

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def login(self, token):
        ws = await connect(self.url, open_timeout=3)
        await ws.send(json.dumps({"type": "auth", "token": token}))
        ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
        return ws, ready

    async def test_auth_and_cross_project(self):
        ws, response = await self.login(self.alpha["token"])
        self.assertEqual(response["type"], "ready")
        self.assertEqual(response["project"], "alpha")
        self.assertFalse(response["personal_chatgpt_connected"])
        await ws.send(json.dumps({"type": "ask", "id": "no", "project": "beta",
                                  "message": "private"}))
        result = json.loads(await asyncio.wait_for(ws.recv(), 3))
        self.assertEqual(result["type"], "error")
        self.assertIn("denied", result["message"])
        await ws.close()
        denied = await connect(self.url)
        await denied.send(json.dumps({"type": "auth", "token": "wrong"}))
        with self.assertRaises(ConnectionClosed):
            await denied.recv()
        await denied.close()

    async def test_duplex_ask_two_requests_processed_concurrently(self):
        def answer(project, question, role, external):
            time.sleep(0.20 if question == "slow" else 0.02)
            return {"answer": question, "sources": [], "model_used": False,
                    "needs_human": False}
        self.engine.answer = answer
        ws, _ = await self.login(self.alpha["token"])
        await ws.send(json.dumps({"type": "ask", "id": "slow1",
                                  "project": "alpha", "message": "slow"}))
        await ws.send(json.dumps({"type": "ask", "id": "fast2",
                                  "project": "alpha", "message": "fast"}))
        messages = [json.loads(await asyncio.wait_for(ws.recv(), 4)) for _ in range(4)]
        answered = [row for row in messages if row["type"] == "answer"]
        self.assertEqual([row["id"] for row in answered], ["fast2", "slow1"])
        self.assertTrue(all(row["action_performed"] is False for row in answered))
        await ws.close()

    async def test_work_never_claims_execution_when_not_configured(self):
        ws, _ = await self.login(self.alpha["token"])
        await ws.send(json.dumps({"type": "work", "id": "w1", "project": "alpha",
                                  "message": "Build an app", "consent": True}))
        a = json.loads(await asyncio.wait_for(ws.recv(), 3))
        b = json.loads(await asyncio.wait_for(ws.recv(), 3))
        self.assertEqual(a["status"], "queued")
        self.assertEqual(b["status"], "needs_setup")
        job_id = a["id_of_job"]
        self.assertFalse(b["action_performed"])
        await ws.send(json.dumps({"type": "resume", "id": "resume1",
                                  "project": "alpha", "job_id": job_id}))
        own = json.loads(await asyncio.wait_for(ws.recv(), 3))
        self.assertEqual(own["status"], "needs_setup")
        await ws.close()
        foreign, _ = await self.login(self.other["token"])
        await foreign.send(json.dumps({"type": "resume", "id": "other",
                                       "project": "alpha", "job_id": job_id}))
        denied = json.loads(await asyncio.wait_for(foreign.recv(), 3))
        self.assertEqual(denied["type"], "error")
        await foreign.close()

    async def test_work_requires_consent_and_permission(self):
        ws, _ = await self.login(self.alpha["token"])
        await ws.send(json.dumps({"type": "work", "id": "c1", "project": "alpha",
                                  "message": "Do something", "consent": False}))
        denied = json.loads(await asyncio.wait_for(ws.recv(), 3))
        self.assertEqual(denied["type"], "error")
        await ws.close()
        read_only = self.engine.access.issue("alpha", allow_ticket=False)
        ws, _ = await self.login(read_only["token"])
        await ws.send(json.dumps({"type": "work", "id": "c2", "project": "alpha",
                                  "message": "Do something", "consent": True}))
        denied = json.loads(await asyncio.wait_for(ws.recv(), 3))
        self.assertIn("permission", denied["message"].lower())
        await ws.close()

    async def test_event_dispatch_and_live_return_without_execution_claim(self):
        class FakePrivateGitHub:
            def __init__(self, repo, token):
                self.repo = repo
            def submit(self, project, question, device, target, operation):
                assert target in {"none", "android", "windows", "web", "github"}
                assert operation in {"answer", "build", "repair", "analyze", "release"}
                return {"issue_number": 9, "request_id": "f"*32}
            def status(self, issue, req_id):
                return {"status": "answered", "answer": "Documented guidance",
                        "needs_human": True, "action_performed": False}
        self.gateway.repo = "owner/private"
        self.gateway.github_token = "fake-server-side-only"
        self.gateway.owner_token_id = self.alpha["token_id"]
        self.gateway.poll_seconds = 2
        with patch("live_bridge.GitHubPrivateBridge", FakePrivateGitHub):
            ws, _ = await self.login(self.alpha["token"])
            await ws.send(json.dumps({"type": "work", "id": "x1", "project": "alpha",
                                      "message": "Create app", "consent": True}))
            rows = [json.loads(await asyncio.wait_for(ws.recv(), 5)) for _ in range(3)]
            self.assertEqual([r["status"] for r in rows],
                             ["queued", "github_dispatched", "needs_action"])
            self.assertFalse(rows[-1]["action_performed"])
            self.assertTrue(rows[-1]["needs_human"])
            await ws.close()

    async def test_remote_socket_refuses_plaintext(self):
        with self.assertRaisesRegex(ValueError, "TLS"):
            await run_server(self.engine, "0.0.0.0", 0)


if __name__ == "__main__":
    unittest.main()
