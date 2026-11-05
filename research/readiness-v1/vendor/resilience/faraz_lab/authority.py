"""Synthetic two-device authority lab, with one mandatory local order gateway.

This models enforcement by that gateway, NOT fencing an actual terminal/broker.
Actors receive logical tokens and cannot obtain a broker through this API. All
time/health inputs are supplied synthetic observations, not authentication or a
real network monitor. Control and order journals are not an atomic transaction.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from threading import RLock

from faraz_core.execution import BrokerEvent, MockBroker, intent_from_authorization, replay
from .codec import canonical_bytes, dumps, parse_json
from .durable import DurableExecutor
from .journal import _WriterLock, load_entries


COMPONENTS = ("phone", "laptop", "engine", "server", "broker", "journal",
              "authority", "path_A", "path_B")
HEALTH_STATES = ("HEALTHY", "STALE", "UNREACHABLE", "FAILED")
CONTROL_VERSION = 1
_ZERO = "0" * 64


class AuthorityError(RuntimeError):
    def __init__(self, reason, mode="UNKNOWN"):
        self.reason, self.mode = reason, mode
        super().__init__("NO_NEW_ORDER:" + mode + ":" + reason)


@dataclass(frozen=True)
class AuthorityToken:
    owner: str
    epoch: int
    expires_ms: int


def _natural(value):
    if type(value) is not int or value < 0:
        raise AuthorityError("NONNEGATIVE_INJECTED_TIME_REQUIRED")
    return value


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise AuthorityError("UNKNOWN_CONTROL_FIELDS")


def _hash(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def canonical_control_path(executor):
    """Exactly one control namespace for a resolved durable order journal."""
    return Path(str(executor.journal.path.resolve()) + ".authority")


def _unresolved(state):
    for item in state.intents:
        if item.close_uncertain or item.ledger.reserved_risk > 0 or item.ledger.unknown_risk > 0:
            return True
        if item.ledger.open_risk > 0 and (not item.position_evidence_complete or len(item.position_ids) != 1):
            return True
    return False


class AuthorityGateway:
    """One serializing gate and shared durable order idempotency for all actors."""

    @classmethod
    def create(cls, control_path, executor, broker, *, topology="independent",
               unattended_allowed=False, fencing_supported=True, max_health_age_ms=1000,
               fault_hook=None):
        gate = cls.__new__(cls)
        gate._initialize(control_path, executor, broker, fault_hook)
        config = {"binding_hash": hashlib.sha256(dumps(executor.journal.entries[0].arguments[0])).hexdigest(),
                  "order_path_hash": hashlib.sha256(os.path.normcase(str(gate._order_path)).encode()).hexdigest(),
                  "topology": topology, "unattended_allowed": unattended_allowed,
                  "fencing_supported": fencing_supported, "max_health_age_ms": max_health_age_ms}
        try:
            gate._os_lock = _WriterLock(gate.path)
            if gate.path.exists() or gate._anchor_path.exists():
                raise AuthorityError("EXISTING_AUTHORITY_REQUIRES_OPEN_NO_EPOCH_RESET")
            if len(executor.journal.entries) != 1:
                raise AuthorityError("FRESH_ORDER_JOURNAL_REQUIRED_FOR_FIRST_AUTHORITY")
            # Commit an initialization fence in the existing order journal
            # before creating sidecars. Even loss of both sidecars cannot make
            # this a fresh order journal through the public create API again.
            executor.transition("recover")
            gate._write_anchor()
            gate._file = open(gate.path, "xb", buffering=0)
            gate._append({"op": "init", **config})
            return gate
        except BaseException:
            gate.close()
            raise

    @classmethod
    def open(cls, control_path, executor, broker, *, now_ms, fault_hook=None):
        gate = cls.__new__(cls)
        gate._initialize(control_path, executor, broker, fault_hook)
        try:
            gate._os_lock = _WriterLock(gate.path)
            gate._events, gate._state, gate._last_hash = gate._read()
            gate._file = open(gate.path, "ab", buffering=0)
            gate._append({"op": "restart", "now_ms": now_ms, **gate._proof()})
            return gate
        except BaseException:
            gate.close()
            raise

    def _initialize(self, path, executor, broker, fault_hook):
        if type(executor) is not DurableExecutor or type(broker) is not MockBroker:
            raise AuthorityError("EXACT_DURABLE_EXECUTOR_AND_MOCK_REQUIRED")
        path = os.fspath(path)
        if not isinstance(path, str) or path.startswith(("\\\\", "//")):
            raise AuthorityError("LOCAL_CONTROL_PATH_REQUIRED")
        requested = Path(path).resolve()
        canonical = canonical_control_path(executor)
        if os.path.normcase(str(requested)) != os.path.normcase(str(canonical)):
            raise AuthorityError("CANONICAL_CONTROL_PATH_REQUIRED")
        self.path = canonical
        self._order_path = executor.journal.path.resolve()
        self._anchor_path = Path(str(canonical) + ".anchor")
        self._executor, self._broker = executor, broker
        self._mutex = RLock()
        self._file = self._os_lock = None
        self._events, self._state, self._last_hash = (), None, _ZERO
        self.fault_hook = fault_hook
        self.poisoned = self.closed = False

    @property
    def state(self):
        return self._executor.state

    @property
    def actual_mock_attempts(self):
        return len(self._broker.attempted)

    @property
    def control_trace(self):
        # Returned evidence cannot mutate the live control state.
        return tuple(parse_json(canonical_bytes(item)) for item in self._events)

    def _proof(self):
        self._verify_order_prefix()
        entries = self._executor.journal.entries
        return {"order_sequence": len(entries), "order_hash": hashlib.sha256(dumps(entries)).hexdigest()}

    def _verify_order_prefix(self):
        # A cached, previously valid executor is not fresh proof that shared
        # storage is still available and agrees with that state.
        try:
            observed = load_entries(self._executor.journal.path)
        except Exception as error:
            self.poisoned = True
            raise AuthorityError("LIVE_ORDER_JOURNAL_UNAVAILABLE_OR_CORRUPT") from error
        if observed != self._executor.journal.entries:
            self.poisoned = True
            raise AuthorityError("LIVE_ORDER_PREFIX_DIVERGED")

    def _proof_state(self, event):
        size = event["order_sequence"]
        if type(size) is not int or not 1 <= size <= len(self._executor.journal.entries):
            raise AuthorityError("ORDER_PREFIX_PROOF_MISSING")
        prefix = self._executor.journal.entries[:size]
        if hashlib.sha256(dumps(prefix)).hexdigest() != event["order_hash"]:
            raise AuthorityError("ORDER_PREFIX_PROOF_CONFLICT")
        return replay(prefix)

    def _healthy(self, state, component, now):
        value = state["health"][component]
        return (value["status"] == "HEALTHY" and
                0 <= now - value["observed_ms"] <= state["config"]["max_health_age_ms"])

    def _path_reasons(self, state, now, owner, actor=None):
        config = state["config"]
        required = ["engine", "broker", "journal", "authority"]
        required.append("server" if config["topology"] == "independent" else "laptop")
        if owner in ("A", "B"):
            required.append("path_" + owner)
        reasons = ["PATH_UNPROVEN:" + key for key in required if not self._healthy(state, key, now)]
        if actor in ("phone", "laptop"):
            if not self._healthy(state, actor, now):
                reasons.append("ACTOR_UNREACHABLE:" + actor)
        elif actor == "engine":
            if not config["unattended_allowed"]:
                reasons.append("UNATTENDED_NOT_AUTHORIZED")
        elif actor is not None:
            reasons.append("UNKNOWN_ACTOR")
        if (actor is None and not config["unattended_allowed"]
                and not any(self._healthy(state, key, now) for key in ("phone", "laptop"))):
            reasons.append("NO_AUTHORIZED_CONTROL_PATH")
        return reasons

    def _time(self, state, now):
        _natural(now)
        if now < state["last_now"]:
            raise AuthorityError("CLOCK_REGRESSION")

    def _check_token(self, state, token, now):
        self._time(state, now)
        if (type(token) is not AuthorityToken or type(token.epoch) is not int
                or type(token.expires_ms) is not int or token.owner not in ("A", "B")
                or token.epoch != state["epoch"]
                or token.owner != state["owner"] or token.expires_ms != state["expires_ms"]):
            raise AuthorityError("STALE_OR_CONFLICTING_AUTHORITY_EPOCH")
        if now >= token.expires_ms:
            raise AuthorityError("LEASE_EXPIRED", "DEGRADED")

    def _reduce(self, previous, event):
        op = event.get("op") if type(event) is dict else None
        if previous is None:
            _keys(event, ("op", "binding_hash", "order_path_hash", "topology", "unattended_allowed",
                          "fencing_supported", "max_health_age_ms"))
            if op != "init" or event["topology"] not in ("independent", "laptop"):
                raise AuthorityError("INVALID_AUTHORITY_CONFIGURATION")
            if (type(event["unattended_allowed"]) is not bool or type(event["fencing_supported"]) is not bool
                    or type(event["max_health_age_ms"]) is not int or event["max_health_age_ms"] <= 0):
                raise AuthorityError("INVALID_AUTHORITY_CONFIGURATION")
            expected_binding = hashlib.sha256(dumps(self._executor.journal.entries[0].arguments[0])).hexdigest()
            expected_path = hashlib.sha256(os.path.normcase(str(self._order_path)).encode()).hexdigest()
            if event["binding_hash"] != expected_binding or event["order_path_hash"] != expected_path:
                raise AuthorityError("CONTROL_ORDER_JOURNAL_BINDING_CONFLICT")
            return {"config": {key: value for key, value in event.items() if key != "op"},
                    "epoch": 0, "owner": None, "expires_ms": 0, "last_now": 0,
                    "health": {key: {"status": "UNREACHABLE", "observed_ms": 0, "observer": "initial"}
                               for key in COMPONENTS}}
        state = {**previous, "health": {key: dict(value) for key, value in previous["health"].items()}}
        if op == "clock":
            _keys(event, ("op", "now_ms"))
            self._time(state, event["now_ms"])
        elif op == "health":
            _keys(event, ("op", "component", "status", "observed_ms", "observer", "now_ms"))
            self._time(state, event["now_ms"])
            if (event["component"] not in COMPONENTS or event["status"] not in HEALTH_STATES
                    or type(event["observer"]) is not str or not event["observer"]):
                raise AuthorityError("INVALID_HEALTH_OBSERVATION")
            observed = _natural(event["observed_ms"])
            if observed > event["now_ms"] or observed < state["health"][event["component"]]["observed_ms"]:
                raise AuthorityError("FUTURE_OR_REGRESSING_HEALTH_OBSERVATION")
            state["health"][event["component"]] = {key: event[key] for key in ("status", "observed_ms", "observer")}
        elif op in ("elect", "renew"):
            _keys(event, ("op", "actor", "owner", "epoch", "expires_ms", "lease_ms", "now_ms",
                          "fence_previous", "order_sequence", "order_hash"))
            self._time(state, event["now_ms"])
            if (event["actor"] not in ("phone", "laptop") or event["owner"] not in ("A", "B")
                    or type(event["fence_previous"]) is not bool or type(event["lease_ms"]) is not int
                    or type(event["epoch"]) is not int or type(event["expires_ms"]) is not int
                    or event["lease_ms"] <= 0 or event["expires_ms"] != event["now_ms"] + event["lease_ms"]):
                raise AuthorityError("INVALID_ELECTION_OR_LEASE")
            reasons = self._path_reasons(state, event["now_ms"], event["owner"], event["actor"])
            if reasons:
                raise AuthorityError(reasons[0], "DEGRADED")
            proof = self._proof_state(event)
            if op == "elect":
                if not state["config"]["fencing_supported"]:
                    raise AuthorityError("EFFECTIVE_FENCING_UNAVAILABLE")
                if state["epoch"] and not event["fence_previous"]:
                    raise AuthorityError("PREVIOUS_AUTHORITY_NOT_FENCED")
                if type(event["epoch"]) is not int or event["epoch"] != state["epoch"] + 1:
                    raise AuthorityError("NONMONOTONIC_AUTHORITY_EPOCH")
                if _unresolved(proof):
                    raise AuthorityError("RECONCILIATION_REQUIRED_BEFORE_HANDOFF")
                state.update(owner=event["owner"], epoch=event["epoch"])
            else:
                self._check_token(state, AuthorityToken(event["owner"], event["epoch"], state["expires_ms"]),
                                  event["now_ms"])
                if event["expires_ms"] <= state["expires_ms"]:
                    raise AuthorityError("LEASE_NOT_EXTENDED")
            state["expires_ms"] = event["expires_ms"]
        elif op == "admit":
            _keys(event, ("op", "actor", "owner", "epoch", "expires_ms", "intent_id", "now_ms",
                          "order_sequence", "order_hash"))
            self._check_token(state, AuthorityToken(event["owner"], event["epoch"], event["expires_ms"]),
                              event["now_ms"])
            reasons = self._path_reasons(state, event["now_ms"], state["owner"], event["actor"])
            if reasons or not state["config"]["fencing_supported"]:
                raise AuthorityError(reasons[0] if reasons else "EFFECTIVE_FENCING_UNAVAILABLE", "DEGRADED")
            if type(event["intent_id"]) is not str or not event["intent_id"]:
                raise AuthorityError("INTENT_ID_REQUIRED")
            if _unresolved(self._proof_state(event)):
                raise AuthorityError("RECONCILIATION_REQUIRED_BEFORE_ENTRY")
        elif op in ("order_event", "restart"):
            required = ("op", "now_ms", "order_sequence", "order_hash")
            _keys(event, required + (("event_id",) if op == "order_event" else ()))
            self._time(state, event["now_ms"])
            proof = self._proof_state(event)
            if op == "restart":
                state.update(owner=None, expires_ms=0)
                state["health"] = {key: {**value, "status": "STALE"} for key, value in state["health"].items()}
            elif (not proof.trace or proof.trace[-1].operation != "apply_event"
                  or proof.trace[-1].arguments[0].event_id != event["event_id"]):
                raise AuthorityError("ORDER_EVENT_PROOF_CONFLICT")
        else:
            raise AuthorityError("UNKNOWN_CONTROL_OPERATION")
        state["last_now"] = event["now_ms"]
        return state

    def _anchor_body(self):
        return {"format": "FARAZ_AUTHORITY_ANCHOR", "version": CONTROL_VERSION,
                "binding_hash": hashlib.sha256(dumps(self._executor.journal.entries[0].arguments[0])).hexdigest(),
                "order_path_hash": hashlib.sha256(os.path.normcase(str(self._order_path)).encode()).hexdigest(),
                "control_path_hash": hashlib.sha256(os.path.normcase(str(self.path)).encode()).hexdigest()}

    def _write_anchor(self):
        body = self._anchor_body()
        wire = canonical_bytes(dict(body, checksum=_hash(body))) + b"\n"
        self._cut("before_anchor_write")
        with open(self._anchor_path, "xb", buffering=0) as stream:
            if stream.write(wire) != len(wire):
                raise AuthorityError("SHORT_AUTHORITY_ANCHOR_WRITE")
            stream.flush()
            self._cut("before_anchor_fsync")
            os.fsync(stream.fileno())
            self._cut("after_anchor_fsync")

    def _validate_anchor(self):
        try:
            raw = self._anchor_path.read_bytes()
            if not raw.endswith(b"\n") or len(raw) > 4096:
                raise AuthorityError("AUTHORITY_ANCHOR_MISSING_OR_INVALID")
            frame = parse_json(raw[:-1])
            expected = self._anchor_body()
            if (frame != dict(expected, checksum=_hash(expected))
                    or canonical_bytes(frame) + b"\n" != raw):
                raise AuthorityError("AUTHORITY_ANCHOR_MISSING_OR_INVALID")
        except AuthorityError:
            raise
        except Exception as error:
            raise AuthorityError("AUTHORITY_ANCHOR_MISSING_OR_INVALID") from error

    def _read(self):
        try:
            self._verify_order_prefix()
            self._validate_anchor()
            raw = self.path.read_bytes()
            if not raw or not raw.endswith(b"\n") or len(raw) > 32 * 1024 * 1024:
                raise AuthorityError("INCOMPLETE_OR_OVERSIZE_CONTROL_JOURNAL")
            events, state, previous = [], None, _ZERO
            for number, line in enumerate(raw.splitlines(keepends=True), 1):
                if len(line) > 2 * 1024 * 1024 or line.endswith(b"\r\n"):
                    raise AuthorityError("INVALID_CONTROL_RECORD")
                frame = parse_json(line[:-1])
                _keys(frame, ("format", "version", "sequence", "previous_hash", "event", "checksum"))
                if (frame["format"] != "FARAZ_AUTHORITY_CONTROL" or type(frame["version"]) is not int
                        or frame["version"] != CONTROL_VERSION):
                    raise AuthorityError("UNKNOWN_CONTROL_SCHEMA")
                if type(frame["sequence"]) is not int or frame["sequence"] != number:
                    raise AuthorityError("CONTROL_SEQUENCE_GAP_OR_FORK")
                body = {key: value for key, value in frame.items() if key != "checksum"}
                if (frame["previous_hash"] != previous or frame["checksum"] != _hash(body)
                        or canonical_bytes(frame) != line[:-1]):
                    raise AuthorityError("CONTROL_INTEGRITY_FAILURE")
                state = self._reduce(state, frame["event"])
                events.append(frame["event"])
                previous = frame["checksum"]
            return tuple(events), state, previous
        except AuthorityError:
            raise
        except Exception as error:
            raise AuthorityError("CONTROL_REPLAY_FAILURE") from error

    def _append(self, event):
        candidate = self._reduce(self._state, event)
        try:
            self._validate_anchor()
            if self._events:
                events, unused_state, previous = self._read()
                if events != self._events or previous != self._last_hash:
                    raise AuthorityError("CONTROL_PREFIX_DIVERGED")
            body = {"format": "FARAZ_AUTHORITY_CONTROL", "version": CONTROL_VERSION,
                    "sequence": len(self._events) + 1, "previous_hash": self._last_hash, "event": event}
            checksum = _hash(body)
            wire = canonical_bytes(dict(body, checksum=checksum)) + b"\n"
            self._cut("before_control_write")
            if self._file.write(wire) != len(wire):
                raise AuthorityError("SHORT_CONTROL_WRITE")
            self._cut("after_control_write")
            self._file.flush()
            self._cut("before_control_fsync")
            os.fsync(self._file.fileno())
            self._cut("after_control_fsync")
            self._events += (parse_json(canonical_bytes(event)),)
            self._state, self._last_hash = candidate, checksum
        except BaseException as error:
            self.poisoned = True
            if not isinstance(error, Exception):
                raise
            if isinstance(error, AuthorityError):
                raise
            raise AuthorityError("CONTROL_COMMIT_UNKNOWN") from error

    def _cut(self, label):
        if self.fault_hook is not None:
            self.fault_hook(label, self)

    def _ready(self):
        if (self.closed or self.poisoned or self._executor.closed or self._executor.poisoned
                or self._executor.journal.closed or self._executor.journal.poisoned):
            raise AuthorityError("JOURNAL_OR_AUTHORITY_RECOVERY_REQUIRED")
        self._verify_order_prefix()

    def _advance_clock(self, now_ms):
        # Even rejected calls and status observations must not let a later
        # supplied timestamp resurrect an already observed expired lease.
        # The explicit event keeps replay pure and the high-water durable.
        self._time(self._state, now_ms)
        if now_ms > self._state["last_now"]:
            self._append({"op": "clock", "now_ms": now_ms})

    def observe(self, component, status, observed_ms, now_ms, observer="lab"):
        with self._mutex:
            self._ready()
            self._advance_clock(now_ms)
            self._append({"op": "health", "component": component, "status": status,
                          "observed_ms": observed_ms, "now_ms": now_ms, "observer": observer})

    def elect(self, actor, candidate, now_ms, lease_ms, fence_previous=False):
        with self._mutex:
            self._ready()
            _natural(now_ms)
            _natural(lease_ms)
            self._advance_clock(now_ms)
            event = {"op": "elect", "actor": actor, "owner": candidate,
                     "epoch": self._state["epoch"] + 1, "expires_ms": now_ms + lease_ms,
                     "lease_ms": lease_ms, "now_ms": now_ms, "fence_previous": fence_previous, **self._proof()}
            self._append(event)
            return AuthorityToken(candidate, self._state["epoch"], self._state["expires_ms"])

    def renew(self, actor, token, now_ms, lease_ms):
        with self._mutex:
            self._ready()
            _natural(now_ms)
            _natural(lease_ms)
            self._advance_clock(now_ms)
            self._check_token(self._state, token, now_ms)
            self._append({"op": "renew", "actor": actor, "owner": token.owner, "epoch": token.epoch,
                          "expires_ms": now_ms + lease_ms, "lease_ms": lease_ms,
                          "now_ms": now_ms, "fence_previous": False, **self._proof()})
            return AuthorityToken(token.owner, token.epoch, self._state["expires_ms"])

    def submit(self, actor, token, authorization, now_ms):
        with self._mutex:
            self._ready()
            self._advance_clock(now_ms)
            self._check_token(self._state, token, now_ms)
            reasons = self._path_reasons(self._state, now_ms, token.owner, actor)
            if reasons:
                raise AuthorityError(reasons[0], "DEGRADED")
            intent = intent_from_authorization(authorization, self.state.binding.policy)
            for existing in self.state.intents:
                if existing.intent.client_intent_id == intent.client_intent_id:
                    if existing.intent != intent:
                        raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
                    if existing.reservation_made:
                        return {"status": "IDEMPOTENT_EXISTING", "intent_id": intent.client_intent_id,
                                "mock_attempts": self.actual_mock_attempts}
            self._append({"op": "admit", "actor": actor, "owner": token.owner, "epoch": token.epoch,
                          "expires_ms": token.expires_ms, "intent_id": intent.client_intent_id,
                          "now_ms": now_ms, **self._proof()})
            try:
                self._executor.transition("propose", intent)
                self._executor.transition("approve", intent.client_intent_id, intent.requested_risk)
                limit = self.state.budget.risk_limit
                self._executor.transition("reserve", intent.client_intent_id, limit, limit)
                # Still under the serial gate; the original exact MockBroker is
                # called only by DurableExecutor after its durable attempt marker.
                self._executor.send(self._broker, intent.client_intent_id, authorization, now_ms)
            except BaseException:
                self.poisoned = True
                if not self._executor.poisoned and not self._executor.journal.poisoned:
                    try:
                        self._executor.transition("recover")
                    except Exception:
                        pass
                raise
            return {"status": "SYNTHETIC_SENT", "intent_id": intent.client_intent_id,
                    "mock_attempts": self.actual_mock_attempts}

    def record_event(self, event, now_ms):
        """Synthetic evidence ingestion can reconcile even without an active writer."""
        with self._mutex:
            self._ready()
            self._advance_clock(now_ms)
            if type(event) is not BrokerEvent:
                raise AuthorityError("SYNTHETIC_EVENT_REQUIRED")
            previous = self.state
            try:
                self._executor.transition("apply_event", event)
                if self.state is not previous:
                    self._append({"op": "order_event", "event_id": event.event_id,
                                  "now_ms": now_ms, **self._proof()})
            except BaseException:
                self.poisoned = True
                raise
            return self.state

    def view(self, now_ms):
        with self._mutex:
            _natural(now_ms)
            reasons = []
            mode = "DEGRADED"
            if not self.closed and not self.poisoned:
                try:
                    self._verify_order_prefix()
                    self._advance_clock(now_ms)
                    events, unused_state, previous = self._read()
                    if events != self._events or previous != self._last_hash:
                        raise AuthorityError("CONTROL_PREFIX_DIVERGED")
                except AuthorityError as error:
                    reasons.append(error.reason)
                    if error.reason != "CLOCK_REGRESSION":
                        self.poisoned = True
            if (self.closed or self.poisoned or self._executor.closed or self._executor.poisoned
                    or self._executor.journal.closed or self._executor.journal.poisoned):
                reasons.append("JOURNAL_OR_AUTHORITY_RECOVERY_REQUIRED")
                mode = "UNKNOWN"
            try:
                self._time(self._state, now_ms)
            except AuthorityError as error:
                reasons.append(error.reason)
                mode = "UNKNOWN"
            reasons += self._path_reasons(self._state, now_ms, self._state["owner"])
            if self._state["owner"] is None:
                reasons.append("NO_ACTIVE_AUTHORITY")
            elif now_ms >= self._state["expires_ms"]:
                reasons.append("LEASE_EXPIRED")
            if not self._state["config"]["fencing_supported"]:
                reasons.append("EFFECTIVE_FENCING_UNAVAILABLE")
            if _unresolved(self.state):
                reasons.append("RECONCILIATION_REQUIRED")
                mode = "UNKNOWN"
            healthy = not reasons
            result = {"mode": "READY_SYNTHETIC" if healthy else mode,
                    "NO_NEW_ORDER": not healthy, "reasons": reasons,
                    "epoch": self._state["epoch"], "owner": self._state["owner"],
                    "expires_ms": self._state["expires_ms"],
                    "health": {key: {**value, "fresh_healthy": self._healthy(self._state, key, now_ms)}
                               for key, value in self._state["health"].items()},
                    "mock_attempts": self.actual_mock_attempts,
                    "readiness_scope": "SYNTHETIC_INFRASTRUCTURE_GATE_ONLY",
                    "evidence_source": "OFFLINE_SYNTHETIC",
                    "broker_fencing_confirmed": False}
            phone = result["health"]["phone"]["fresh_healthy"]
            laptop = result["health"]["laptop"]["fresh_healthy"]
            if phone and laptop:
                devices_fa = "دسترسی گوشی و لپ‌تاپ در این مدل تأیید شده است."
            elif phone:
                devices_fa = "اتصال لپ‌تاپ تأیید نشده؛ دسترسی گوشی در این مدل برقرار است."
            elif laptop:
                devices_fa = "اتصال گوشی تأیید نشده؛ دسترسی لپ‌تاپ در این مدل برقرار است."
            else:
                devices_fa = "اتصال گوشی و لپ‌تاپ تأیید نشده است."
            if healthy:
                execution_fa = "مسیر اجرایی مصنوعی موتور تا بروکر mock و journal با اختیار یکتا تأیید شده است."
            elif self._state["config"]["topology"] == "laptop" and not laptop:
                execution_fa = "موتور روی لپ‌تاپ فرض شده و مسیر اجرای آن تأیید نیست؛ اتصال گوشی جای موتور را نمی‌گیرد."
            elif "RECONCILIATION_REQUIRED" in reasons:
                execution_fa = "نتیجه سفارش یا تعهدات نامعلوم است؛ انتقال کنترل و ورود تازه تا تطبیق معتبر متوقف‌اند."
            elif "EFFECTIVE_FENCING_UNAVAILABLE" in reasons:
                execution_fa = "منع نویسنده قبلی قابل اثبات نیست؛ انتقال اختیار انجام نمی‌شود."
            elif self._state["owner"] is None:
                execution_fa = "اختیار فعال تأیید نشده؛ انتقال کنترل موفق اعلام نمی‌شود."
            elif mode == "UNKNOWN":
                execution_fa = "وضعیت اجرای مصنوعی نامعلوم است؛ انتقال کنترل موفق اعلام نمی‌شود."
            else:
                execution_fa = "مسیر اجرایی مصنوعی کاهش قابلیت دارد و تأیید کامل نیست."
            action_fa = ("ورود سفارش تازه ممنوع است (NO_NEW_ORDER)." if not healthy else
                         "گیت زیرساخت مصنوعی آماده است؛ تصمیم معامله همچنان به کنترل ریسک نیاز دارد.")
            result["display_fa"] = {"devices": devices_fa, "execution": execution_fa,
                                    "action": action_fa,
                                    "scope": "آزمایشگاه آفلاین؛ این پیام تأیید اتصال واقعی موتور یا بروکر نیست."}
            result["message_fa"] = " ".join(result["display_fa"].values())
            return result

    def close(self):
        with self._mutex:
            if self.closed:
                return
            self.closed = True
            try:
                if self._file is not None:
                    self._file.close()
                    self._file = None
            finally:
                if self._os_lock is not None:
                    self._os_lock.close()
                    self._os_lock = None

    def __enter__(self):
        self._ready()
        return self

    def __exit__(self, *_):
        self.close()
