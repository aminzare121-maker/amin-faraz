#!/usr/bin/env python3
"""Amin AI: owner's official Sign in with ChatGPT (SIWC) plan-use connector.

For an open-source tool running on the account owner's computer. It uses
the documented OpenAI OAuth + PKCE flow and the PUBLIC Responses API endpoint
with a user-approved ChatGPT plan OAuth token. It NEVER uses Codex, Work,
a paid API key, browser cookies, ChatGPT backend-api, or borrowed credentials.

This cannot resume the original ChatGPT chat or automatically grant its
connected GitHub tools. GitHub tools must be implemented and approved locally.
Requires: pip install 'PyJWT[crypto]>=2.8,<3' 'keyring>=25,<27' 'filelock>=3,<4'.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, urlopen

AUTH = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
JWKS = AUTH + "/.well-known/jwks.json"
AUTH_URL = AUTH + "/api/accounts/authorize"
TOKEN_URL = AUTH + "/api/accounts/oauth/token"
REQUIRED_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
APP_NAME = "Amin AI Support"
MODEL_SLUG = re.compile(r"^[a-zA-Z0-9._:-]{2,100}$")
CLIENT_ID = re.compile(r"^oaiapp_[a-zA-Z0-9_-]{6,180}$")
DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / "AminAI" / "siwc"
SERVICE = "AminAI-SIWC-local-only"
MAX_PROMPT = 3500
MAX_RESULT = 30000


class PlanConnectionUnavailable(RuntimeError):
    pass


def _dependencies():
    try:
        import jwt
        import keyring
        from filelock import FileLock
    except ImportError:
        raise PlanConnectionUnavailable(
            "Install free dependencies: pip install 'PyJWT[crypto]>=2.8,<3' 'keyring>=25,<27' 'filelock>=3,<4'") from None
    backend = keyring.get_keyring()
    if getattr(backend, "priority", 0) <= 0:
        raise PlanConnectionUnavailable("No secure OS credential vault is available; refusing plaintext storage")
    return jwt, keyring, FileLock


def _home(path=DATA_DIR):
    folder = Path(path)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    return folder


def _meta_path(folder):
    return folder / "profile.json"


def _read_meta(folder):
    path = _meta_path(folder)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text("utf8"))
    if not isinstance(data, dict):
        raise PlanConnectionUnavailable("Invalid account metadata")
    return data


def _write_meta(folder, data):
    path = _meta_path(folder)
    tmp = path.with_suffix(".partial")
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n"
    with open(tmp, "w", encoding="utf8") as out:
        os.chmod(tmp, 0o600)
        out.write(payload)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)


def _host_id(folder):
    meta = _read_meta(folder)
    host = meta.get("ext_agent_host_id")
    if host:
        if not isinstance(host, str) or not host.startswith("urn:uuid:"):
            raise PlanConnectionUnavailable("Invalid previously registered host ID")
        return host
    host = "urn:uuid:" + str(uuid.uuid4())
    _write_meta(folder, {**meta, "ext_agent_host_id": host})
    return host


def _vault_id(folder):
    # Different machine/user installations are not allowed to share credentials.
    return _host_id(folder)


def _get_profile(folder, keyring):
    identity = _vault_id(folder)
    stored = keyring.get_password(SERVICE, identity)
    if not stored:
        return None
    profile = json.loads(stored)
    if not isinstance(profile, dict) or not profile.get("client_id"):
        raise PlanConnectionUnavailable("Corrupted protected ChatGPT account connection")
    return profile


def _save_profile(folder, keyring, profile):
    # Persist tokens ONLY in the OS keyring; never in GitHub or local JSON.
    keyring.set_password(SERVICE, _vault_id(folder), json.dumps(profile, ensure_ascii=False))
    metadata = _read_meta(folder)
    metadata.update({k: profile.get(k) for k in (
        "client_id", "subject", "email", "ext_agent_host_id", "scopes")})
    _write_meta(folder, metadata)


def pkce_values():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


def authorization_url(redirect, state, nonce, challenge, host_id, issued_client=None):
    if not redirect.startswith("http://127.0.0.1:") or not redirect.endswith("/auth/callback"):
        raise ValueError("Only a private loopback OAuth callback is permitted")
    if not state or not nonce or not challenge or not host_id.startswith("urn:uuid:"):
        raise ValueError("Missing signed-in host and PKCE transaction state")
    params = {
        "client_id": issued_client or "dynamic_agent_client",
        "response_type": "code",
        "redirect_uri": redirect,
        "scope": SCOPES,
        "resource": RESOURCE,
        "state": state,
        "nonce": nonce,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "ext_agent_host_id": host_id,
    }
    if issued_client:
        if not CLIENT_ID.fullmatch(issued_client):
            raise ValueError("Invalid issued client ID")
    else:
        params["agent_name_hint"] = APP_NAME
    return AUTH_URL + "?" + urlencode(params)


def _json_request(url, token=None, form=None):
    if form is not None:
        body = urlencode(form).encode("utf8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        method = "POST"
    else:
        body = None
        headers = {"Accept": "application/json"}
        method = "GET"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=22) as response:
            if response.status != 200:
                raise PlanConnectionUnavailable("Remote provider did not accept request")
            data = response.read(512_000 + 1)
            if len(data) > 512_000:
                raise PlanConnectionUnavailable("Provider response was too large")
            return json.loads(data)
    except HTTPError as error:
        raise PlanConnectionUnavailable(
            "ChatGPT authorization/provider returned HTTP " + str(error.code)) from None
    except URLError:
        raise PlanConnectionUnavailable("OpenAI authentication server unreachable") from None


def verify_id_token(id_token, client_id, nonce, jwt_module):
    if not CLIENT_ID.fullmatch(client_id):
        raise PlanConnectionUnavailable("Unrecognized issued OAuth client")
    signing = jwt_module.PyJWKClient(JWKS, timeout=10).get_signing_key_from_jwt(id_token)
    identity = jwt_module.decode(
        id_token, signing.key, algorithms=["RS256"],
        issuer=AUTH, audience=client_id,
        options={"require": ["exp", "iat", "sub"]}, leeway=5)
    if not hmac.compare_digest(str(identity.get("nonce", "")), nonce):
        raise PlanConnectionUnavailable("OAuth identity nonce mismatch")
    if not isinstance(identity.get("sub"), str) or not identity["sub"]:
        raise PlanConnectionUnavailable("OAuth account subject missing")
    return identity


def _make_profile(data, client_id, host, identity, previous=None):
    if not isinstance(data, dict) or data.get("token_type", "Bearer").casefold() != "bearer":
        raise PlanConnectionUnavailable("OAuth token exchange did not return a bearer token")
    for name in ("access_token", "refresh_token"):
        if not isinstance(data.get(name), str) or len(data[name]) < 16:
            raise PlanConnectionUnavailable("Missing OAuth access or refresh token")
    granted = set((data.get("scope") or "").split())
    if REQUIRED_SCOPE not in granted or "resource.invoke" not in granted:
        raise PlanConnectionUnavailable(
            "ChatGPT plan sharing not approved; no paid API fallback will be used")
    if previous and (identity["sub"] != previous["subject"]
                     or client_id != previous["client_id"]):
        raise PlanConnectionUnavailable("ChatGPT identity changed; refusing account substitution")
    return {
        "client_id": client_id, "subject": identity["sub"],
        "email": identity.get("email") if identity.get("email_verified") is True else None,
        "scopes": sorted(granted), "ext_agent_host_id": host,
        "id_token": data.get("id_token", ""),
        "access_token": data["access_token"], "refresh_token": data["refresh_token"],
        "expires_at": time.time() + int(data.get("expires_in") or 3600),
        "earliest_refresh_at": data.get("earliest_refresh_at"),
    }


def login(folder=DATA_DIR, browser=True):
    jwt, keyring, FileLock = _dependencies()
    home = _home(folder)
    old = _get_profile(home, keyring)
    meta = _read_meta(home)
    issued = old["client_id"] if old else meta.get("client_id")
    if issued and not CLIENT_ID.fullmatch(issued):
        raise PlanConnectionUnavailable("Saved OAuth client identity invalid")
    nonce, state = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verifier, challenge = pkce_values()
    result = {}
    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path)
            if path.path != "/auth/callback":
                self.send_error(404)
                return
            parsed = parse_qs(path.query, keep_blank_values=True)
            if len(parsed.get("state", [])) != 1 or not hmac.compare_digest(
                    parsed["state"][0], state):
                self.send_error(400, "OAuth state mismatch")
                result["error"] = "state_mismatch"
                return
            if parsed.get("error"):
                result["error"] = "access_denied"
                self.send_response(403)
                self.end_headers()
                return
            if len(parsed.get("code", [])) != 1:
                result["error"] = "missing_code"
                self.send_error(400)
                return
            callback_id = (parsed.get("client_id") or [issued])[0]
            if not callback_id or not CLIENT_ID.fullmatch(callback_id):
                result["error"] = "missing_client_id"
                self.send_error(400)
                return
            if issued and callback_id != issued:
                result["error"] = "account_registration_mismatch"
                self.send_error(400)
                return
            result.update({"code": parsed["code"][0], "client_id": callback_id})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write("ChatGPT sign-in received. You may return to Amin AI.".encode())
        def log_message(self, *_):  # Never log OAuth codes or query parameters
            return

    with HTTPServer(("127.0.0.1", 0), Callback) as server:
        server.timeout = 240
        url = f"http://127.0.0.1:{server.server_port}/auth/callback"
        login_url = authorization_url(url, state, nonce, challenge, _host_id(home), issued)
        print("Opening the official ChatGPT sign-in page; approve sharing if you agree.")
        if not browser or not webbrowser.open(login_url, new=1):
            raise PlanConnectionUnavailable("Unable to open system browser safely")
        server.handle_request()
    if "code" not in result:
        raise PlanConnectionUnavailable("ChatGPT sign-in did not complete: " +
                                        result.get("error", "timeout"))
    callback_id = result["client_id"]
    # Save issued ID so a one-time code failure does not register a fresh client.
    if not issued:
        saved = _read_meta(home)
        saved["client_id"] = callback_id
        _write_meta(home, saved)
    data = _json_request(TOKEN_URL, form={
        "grant_type": "authorization_code", "client_id": callback_id,
        "code": result["code"], "code_verifier": verifier,
        "redirect_uri": url, "resource": RESOURCE,
    })
    identity = verify_id_token(data.get("id_token", ""), callback_id, nonce, jwt)
    profile = _make_profile(data, callback_id, _host_id(home), identity, old)
    with FileLock(str(home / ".oauth.lock"), timeout=30):
        _save_profile(home, keyring, profile)
    return {"connected": True, "sharing": True, "email": profile["email"],
            "client_id": callback_id}


def _refresh_if_needed(folder, keyring, FileLock):
    home = _home(folder)
    with FileLock(str(home / ".oauth.lock"), timeout=30):
        current = _get_profile(home, keyring)
        if not current:
            raise PlanConnectionUnavailable("ChatGPT not connected; run login first")
        if REQUIRED_SCOPE not in current.get("scopes", []):
            raise PlanConnectionUnavailable("ChatGPT plan usage not authorized")
        if current["expires_at"] > time.time() + 120:
            return current
        earliest = current.get("earliest_refresh_at")
        if earliest is not None:
            try:
                min_refresh = float(earliest)
            except (ValueError, TypeError):
                try:
                    min_refresh = datetime.fromisoformat(
                        str(earliest).replace("Z", "+00:00")).timestamp()
                except ValueError:
                    raise PlanConnectionUnavailable("Unknown earliest refresh format")
            if time.time() < min_refresh:
                if current["expires_at"] > time.time() + 5:
                    return current
                raise PlanConnectionUnavailable("Token refresh is not permitted yet")
        data = _json_request(TOKEN_URL, form={
            "grant_type": "refresh_token", "client_id": current["client_id"],
            "refresh_token": current["refresh_token"], "resource": RESOURCE,
        })
        for name in ("access_token", "refresh_token"):
            if not isinstance(data.get(name), str) or len(data[name]) < 16:
                raise PlanConnectionUnavailable("Refresh did not return rotated token")
        if REQUIRED_SCOPE not in set((data.get("scope") or "").split()):
            raise PlanConnectionUnavailable("ChatGPT plan access no longer granted")
        current.update({
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_at": time.time() + int(data.get("expires_in") or 3600),
            "earliest_refresh_at": data.get("earliest_refresh_at"),
            "scopes": sorted(set(data.get("scope", "").split())),
        })
        _save_profile(home, keyring, current)
        return current


def models(folder=DATA_DIR):
    _, keyring, FileLock = _dependencies()
    profile = _refresh_if_needed(folder, keyring, FileLock)
    data = _json_request(RESOURCE + "/models", token=profile["access_token"])
    return [m for m in data.get("models", []) if isinstance(m, dict)
            and m.get("visibility") == "list" and MODEL_SLUG.fullmatch(m.get("slug", ""))]


def parse_sse_events(lines):
    """Process OpenAI SSE frames. Never accept partial output as final inference."""
    answer = []
    completed = False
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode("utf8")
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            event = json.loads(data)
        except (TypeError, ValueError):
            raise PlanConnectionUnavailable("Provider returned malformed event stream")
        kind = event.get("type")
        if kind == "response.output_text.delta":
            delta = event.get("delta")
            if isinstance(delta, str) and sum(len(x) for x in answer) + len(delta) <= MAX_RESULT:
                answer.append(delta)
        if kind in ("response.failed", "response.incomplete", "error"):
            error = event.get("response", {}).get("error") if isinstance(
                event.get("response"), dict) else event.get("error")
            code = error.get("code", kind) if isinstance(error, dict) else kind
            raise PlanConnectionUnavailable("ChatGPT request failed: " + str(code))
        if kind == "response.completed":
            completed = True
    if not completed or not "".join(answer).strip():
        raise PlanConnectionUnavailable("ChatGPT stream incomplete or empty")
    return "".join(answer).strip()


def ask(question: str, folder=DATA_DIR, model=None):
    if not isinstance(question, str) or not question.strip() or len(question) > MAX_PROMPT:
        raise ValueError("Question must be 1-3500 characters")
    _, keyring, FileLock = _dependencies()
    profile = _refresh_if_needed(folder, keyring, FileLock)
    available = models(folder)
    slugs = {m["slug"] for m in available}
    selected = model or os.environ.get("AMIN_SIWC_MODEL", "")
    if not selected:
        selected = next(iter(m["slug"] for m in available), "")
    if selected not in slugs:
        raise PlanConnectionUnavailable("No available ChatGPT plan model for this account")
    payload = {
        "model": selected,
        "input": [{"role": "user", "content": question.strip()}],
        "instructions": ("You are Amin AI, a Persian-language software support assistant. "
                         "Answer clearly and accurately. Do not claim to have executed code, "
                         "tested on real devices, connected to GitHub, or installed software "
                         "without corresponding tool evidence."),
        "store": False, "stream": True,
    }
    req = Request(RESOURCE + "/responses",
                  data=json.dumps(payload, ensure_ascii=False).encode("utf8"),
                  headers={"Authorization": "Bearer " + profile["access_token"],
                           "Content-Type": "application/json",
                           "Accept": "text/event-stream"},
                  method="POST")
    try:
        with urlopen(req, timeout=180) as response:
            if response.status != 200:
                raise PlanConnectionUnavailable("ChatGPT inference HTTP failure")
            text = parse_sse_events(response)
    except HTTPError as error:
        if error.code == 429:
            raise PlanConnectionUnavailable(
                "ChatGPT plan usage limit reached; no paid API fallback") from None
        raise PlanConnectionUnavailable("OpenAI inference returned HTTP " + str(error.code)) from None
    except URLError:
        raise PlanConnectionUnavailable("OpenAI inference connection unavailable") from None
    return {"answer": text, "model": selected, "model_used": True,
            "source": "SIWC ChatGPT plan", "action_performed": False}


def status(folder=DATA_DIR):
    _, keyring, _ = _dependencies()
    home = _home(folder)
    profile = _get_profile(home, keyring)
    if profile is None:
        return {"connected": False, "sharing": False}
    return {"connected": True, "sharing": REQUIRED_SCOPE in profile.get("scopes", []),
            "email": profile.get("email"), "expires_in_seconds": max(
                0, int(profile["expires_at"] - time.time()))}


def logout(folder=DATA_DIR):
    _, keyring, _ = _dependencies()
    home = _home(folder)
    keyring.delete_password(SERVICE, _vault_id(home))
    return {"local_session_removed": True,
            "remote_revocation_confirmed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Official ChatGPT plan usage; no Codex and no paid API key")
    parser.add_argument("command", choices=["login", "status", "models", "ask", "logout"])
    parser.add_argument("--question", default=None)
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "login": result = login()
        elif args.command == "status": result = status()
        elif args.command == "models":
            result = [{"slug": x["slug"], "display_name": x.get("display_name")} for x in models()]
        elif args.command == "ask":
            question = args.question if args.question is not None else sys.stdin.read(MAX_PROMPT+1)
            result = ask(question, model=args.model)
        else: result = logout()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PlanConnectionUnavailable, ValueError) as error:
        print("ChatGPT connection unavailable: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
