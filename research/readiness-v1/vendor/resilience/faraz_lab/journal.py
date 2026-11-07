"""Strict local append-only journal for the offline synthetic resilience lab.

An append returns only after write, flush and os.fsync succeed. The supported
durability assumption is that the OS/device honors that successful file fsync;
no directory-entry, controller-cache or physical power-loss guarantee is made.
Checksums detect accidental corruption, not an authenticated broker or attacker.
No damaged suffix is truncated automatically and no checkpoint is authoritative.
"""
from pathlib import Path
import hashlib
import os

from faraz_core.execution import DemoBinding, TraceEntry, replay
from .codec import CodecError, canonical_bytes, dumps, from_data, parse_json, to_data


FORMAT = "FARAZ_OFFLINE_JOURNAL"
SCHEMA_VERSION = 1
ZERO_HASH = "0" * 64
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
_FRAME_FIELDS = {"format", "version", "sequence", "binding_hash", "previous_hash",
                 "payload", "checksum"}


class JournalError(RuntimeError):
    pass


def _path(value):
    text = os.fspath(value)
    if not isinstance(text, str) or text.startswith(("\\\\", "//")):
        raise JournalError("LOCAL_LAB_PATH_REQUIRED")
    return Path(text).absolute()


def _digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _binding_hash(binding):
    return hashlib.sha256(dumps(binding)).hexdigest()


def _initial_binding(entries):
    if (not entries or type(entries[0]) is not TraceEntry
            or entries[0].operation != "start" or type(entries[0].arguments) is not tuple
            or len(entries[0].arguments) != 1 or type(entries[0].arguments[0]) is not DemoBinding):
        raise JournalError("START_BINDING_REQUIRED")
    binding = entries[0].arguments[0]
    if binding.policy is None:
        raise JournalError("PINNED_POLICY_REQUIRED")
    return binding


def _validate_trace(entries, expected_binding=None):
    binding = _initial_binding(entries)
    if expected_binding is not None and binding != expected_binding:
        raise JournalError("ACCOUNT_POLICY_BINDING_MISMATCH")
    try:
        state = replay(entries)
    except (ValueError, TypeError, ArithmeticError, AttributeError) as error:
        raise JournalError("INVALID_TRANSITION_TRACE") from error
    if (state.binding.account_id != binding.account_id or state.binding.policy != binding.policy
            or state.binding.budget_epoch_id != binding.budget_epoch_id
            or state.binding.epoch_risk_limit != binding.epoch_risk_limit):
        raise JournalError("ACCOUNT_POLICY_BINDING_CHANGED")
    return binding


def _read(path, expected_binding=None):
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise JournalError("JOURNAL_SIZE_EXCEEDED")
        raw = path.read_bytes()
    except OSError as error:
        raise JournalError("JOURNAL_READ_FAILURE") from error
    if not raw or not raw.endswith(b"\n"):
        raise JournalError("EMPTY_OR_INCOMPLETE_JOURNAL")
    entries = []
    previous = ZERO_HASH
    binding_hash = None
    try:
        for number, line in enumerate(raw.splitlines(keepends=True), 1):
            if (not line.endswith(b"\n") or line.endswith(b"\r\n")
                    or len(line) > MAX_RECORD_BYTES):
                raise JournalError("INCOMPLETE_OR_OVERSIZE_RECORD")
            wire = line[:-1]
            frame = parse_json(wire)
            if type(frame) is not dict or set(frame) != _FRAME_FIELDS:
                raise JournalError("UNKNOWN_JOURNAL_FIELDS")
            if frame["format"] != FORMAT or type(frame["version"]) is not int or frame["version"] != SCHEMA_VERSION:
                raise JournalError("UNSUPPORTED_JOURNAL_SCHEMA")
            if type(frame["sequence"]) is not int or frame["sequence"] != number:
                raise JournalError("JOURNAL_SEQUENCE_GAP_OR_FORK")
            if frame["previous_hash"] != previous:
                raise JournalError("JOURNAL_HASH_CHAIN_MISMATCH")
            body = {key: value for key, value in frame.items() if key != "checksum"}
            if frame["checksum"] != _digest(body):
                raise JournalError("JOURNAL_CHECKSUM_MISMATCH")
            if canonical_bytes(frame) != wire:
                raise JournalError("NONCANONICAL_JOURNAL_FRAME")
            entry = from_data(frame["payload"])
            if type(entry) is not TraceEntry:
                raise JournalError("TRACE_ENTRY_REQUIRED")
            entries.append(entry)
            if number == 1:
                binding_hash = _binding_hash(_initial_binding(tuple(entries)))
            if frame["binding_hash"] != binding_hash:
                raise JournalError("ACCOUNT_POLICY_BINDING_MISMATCH")
            previous = frame["checksum"]
        result = tuple(entries)
        _validate_trace(result, expected_binding)
        return result, previous, binding_hash
    except CodecError as error:
        raise JournalError("JOURNAL_CODEC_FAILURE:" + str(error)) from error


def load_entries(path, expected_binding=None):
    """Read-only, strict reconstruction input. A bad byte never frees a reserve."""
    return _read(_path(path), expected_binding)[0]


class _WriterLock:
    """OS-scoped local writer lock; file presence itself is never a lease."""

    def __init__(self, path):
        self.file = None
        try:
            self.file = open(str(path) + ".lock", "a+b", buffering=0)
            if self.file.seek(0, os.SEEK_END) == 0:
                self.file.write(b"\0")
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            elif os.name == "posix":
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                raise JournalError("UNSUPPORTED_LOCAL_LOCK_PLATFORM")
        except (OSError, JournalError) as error:
            if self.file is not None:
                self.file.close()
            self.file = None
            if isinstance(error, JournalError):
                raise
            raise JournalError("LOCAL_WRITER_LOCK_UNAVAILABLE") from error

    def close(self):
        if self.file is None:
            return
        try:
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        finally:
            self.file.close()
            self.file = None


class Journal:
    """One local writer. Open/create never overwrite, repair or trim a journal."""

    @classmethod
    def create(cls, path, binding, fault_hook=None):
        if type(binding) is not DemoBinding or binding.policy is None:
            raise JournalError("PINNED_DEMO_BINDING_REQUIRED")
        instance = cls.__new__(cls)
        instance._initialize(path, fault_hook)
        try:
            instance._lock = _WriterLock(instance.path)
            instance._file = open(instance.path, "xb", buffering=0)
            instance._binding = binding
            instance._binding_hash = _binding_hash(binding)
            instance.append(TraceEntry("start", (binding,)))
            return instance
        except BaseException as error:
            instance.close()
            if not isinstance(error, Exception):
                raise
            if isinstance(error, JournalError):
                raise
            raise JournalError("JOURNAL_CREATE_FAILURE") from error

    @classmethod
    def open(cls, path, binding=None, fault_hook=None):
        instance = cls.__new__(cls)
        instance._initialize(path, fault_hook)
        try:
            instance._lock = _WriterLock(instance.path)
            entries, previous, binding_hash = _read(instance.path, binding)
            instance._entries = entries
            instance._last_hash = previous
            instance._binding = _initial_binding(entries)
            instance._binding_hash = binding_hash
            instance._file = open(instance.path, "ab", buffering=0)
            return instance
        except BaseException as error:
            instance.close()
            if not isinstance(error, Exception):
                raise
            if isinstance(error, JournalError):
                raise
            raise JournalError("JOURNAL_OPEN_FAILURE") from error

    def _initialize(self, path, fault_hook):
        self.path = _path(path)
        self._file = None
        self._lock = None
        self._entries = ()
        self._last_hash = ZERO_HASH
        self._binding = None
        self._binding_hash = None
        self.fault_hook = fault_hook
        self.poisoned = False
        self.closed = False

    @property
    def entries(self):
        return self._entries

    def _hook(self, label):
        if self.fault_hook is not None:
            self.fault_hook(label, self)

    def _write(self, data):
        return self._file.write(data)

    def _flush(self):
        self._file.flush()

    def _fsync(self):
        os.fsync(self._file.fileno())

    def append(self, entry):
        if self.closed or self.poisoned:
            raise JournalError("JOURNAL_WRITER_CLOSED_OR_POISONED")
        try:
            if type(entry) is not TraceEntry:
                raise JournalError("TRACE_ENTRY_REQUIRED")
            if self._entries:
                observed, previous, unused_binding_hash = _read(self.path, self._binding)
                if observed != self._entries or previous != self._last_hash:
                    raise JournalError("JOURNAL_DIVERGED_FROM_WRITER")
            candidate = self._entries + (entry,)
            _validate_trace(candidate, self._binding)
            body = {"format": FORMAT, "version": SCHEMA_VERSION,
                    "sequence": len(candidate), "binding_hash": self._binding_hash,
                    "previous_hash": self._last_hash, "payload": to_data(entry)}
            checksum = _digest(body)
            data = canonical_bytes(dict(body, checksum=checksum)) + b"\n"
            if len(data) > MAX_RECORD_BYTES or self._file.tell() + len(data) > MAX_FILE_BYTES:
                raise JournalError("JOURNAL_SIZE_EXCEEDED")
            self._hook("before_write")
            if self._write(data) != len(data):
                raise JournalError("SHORT_JOURNAL_WRITE")
            self._hook("after_write")
            self._hook("before_flush")
            self._flush()
            self._hook("after_flush")
            self._hook("before_fsync")
            self._fsync()
            self._hook("after_fsync")
            # Visibility changes only after the whole append protocol returns.
            self._entries = candidate
            self._last_hash = checksum
        except BaseException as error:
            self.poisoned = True
            if not isinstance(error, Exception):
                raise
            if isinstance(error, JournalError):
                raise
            raise JournalError("JOURNAL_APPEND_AMBIGUOUS:" + str(error)) from error

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self._file is not None:
                self._file.close()
                self._file = None
        finally:
            if self._lock is not None:
                self._lock.close()
                self._lock = None

    def __enter__(self):
        if self.closed:
            raise JournalError("JOURNAL_WRITER_CLOSED_OR_POISONED")
        return self

    def __exit__(self, unused_type, unused_value, unused_traceback):
        self.close()
