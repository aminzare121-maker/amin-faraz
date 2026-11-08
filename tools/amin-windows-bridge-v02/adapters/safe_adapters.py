"""Offline contracts only. No SDK import, attachment, process control or trading."""
import json
import math
import os
from pathlib import Path

SYMBOL = 'XAUUSD.st'
APIS = frozenset({'account_info', 'symbol_info', 'copy_rates_from_pos'})


class PolicyError(Exception):
    pass


AUDIT_CODES = frozenset({'API_DENIED', 'ACCOUNT_GUARD', 'SYMBOL_GUARD', 'MARKET_READ',
                         'AUTH_REQUIRED', 'SDK_ERROR'})


class JsonlAuditSink:
    """Host-approved local destination only. No request chooses this path.

    Single-process contract; host must enforce ACLs and handle/path race security.
    Existing files at the byte ceiling are rejected, never rotated/deleted here.
    """
    def __init__(self, approved_path, *, approved=False, max_bytes=65536):
        self._path = Path(approved_path).absolute()
        self._approved = approved is True
        self._max = max_bytes if type(max_bytes) is int and 128 <= max_bytes <= 65536 else 65536

    def emit(self, code):
        if not self._approved or code not in AUDIT_CODES:
            raise PolicyError('AUDIT_UNAVAILABLE')
        p = self._path
        if '..' in p.parts or any(q.is_symlink() or q.is_junction() for q in (p, *p.parents)):
            raise PolicyError('AUDIT_UNAVAILABLE')
        data = (json.dumps({'event': code}, separators=(',', ':')) + '\n').encode('ascii')
        with p.open('ab') as out:
            st = os.fstat(out.fileno())
            if st.st_nlink != 1 or getattr(st, 'st_file_attributes', 0) & 0x400 or st.st_size + len(data) > self._max:
                raise PolicyError('AUDIT_UNAVAILABLE')
            out.write(data)
            out.flush()
            os.fsync(out.fileno())


class ReadOnlyMarketAdapter:
    """Proxy must represent an already attached session; this class never attaches.

    handshake_ok/session_consent are trusted host assertions, not authorization
    that an untrusted request may set. Actual live wiring is intentionally absent.
    """
    def __init__(self, proxy, *, handshake_ok=False, session_consent=False, audit_sink=None):
        self._proxy = proxy
        self._authorized = handshake_ok is True and session_consent is True
        self._audit = []
        self._sink = audit_sink

    def _emit(self, code):
        if self._sink is None:
            raise PolicyError('AUDIT_UNAVAILABLE')
        try:
            self._sink.emit(code)
        except Exception:
            raise PolicyError('AUDIT_UNAVAILABLE') from None
        self._audit.append(code)
        del self._audit[:-256]

    @property
    def audit_events(self):
        """In-memory fixed codes only; host owns persistence and access control."""
        return tuple(self._audit)

    def request_api(self, name, *args):
        """No method-name dispatch is supported, including allowlisted reads."""
        self._emit('API_DENIED')
        raise PolicyError('API_DENIED')

    def inspect(self, *, symbol=SYMBOL, count=100):
        result = {'ok': False, 'symbol': SYMBOL, 'count': 0, 'error': 'AUTH_REQUIRED'}
        if not self._authorized:
            return result
        if symbol != SYMBOL:
            return {**result, 'error': 'SYMBOL_DENIED'}
        if type(count) is not int or not 1 <= count <= 100:
            return {**result, 'error': 'COUNT_DENIED'}
        try:
            # Trusted proxy normalizes SDK enums; no account fields escape.
            self._emit('ACCOUNT_GUARD')
            account = self._proxy.account_info()
            if not isinstance(account, dict) or account.get('mode') != 'DEMO':
                return {**result, 'error': 'DEMO_REQUIRED'}
            if account.get('broker') != 'Eplanet':
                return {**result, 'error': 'BROKER_DENIED'}
            self._emit('SYMBOL_GUARD')
            info = self._proxy.symbol_info(SYMBOL)
            if not isinstance(info, dict) or info.get('name') != SYMBOL:
                return {**result, 'error': 'SYMBOL_DENIED'}
            self._emit('MARKET_READ')
            rows = self._proxy.copy_rates_from_pos(SYMBOL, 'M15', 1, count)
            if not isinstance(rows, (list, tuple)) or len(rows) > count:
                return {**result, 'error': 'DATA_INVALID'}
            if not rows:
                return {**result, 'error': 'HISTORY_UNAVAILABLE'}
            for row in rows:
                if not isinstance(row, dict) or set(row) != {'time', 'open', 'high', 'low', 'close'}:
                    return {**result, 'error': 'DATA_INVALID'}
                if type(row['time']) is not int or row['time'] < 0 or row['time'] % 900:
                    return {**result, 'error': 'DATA_INVALID'}
                if any(type(row[k]) not in (int, float) or not math.isfinite(row[k]) or row[k] <= 0 for k in ('open', 'high', 'low', 'close')):
                    return {**result, 'error': 'DATA_INVALID'}
                if not row['low'] <= min(row['open'], row['close']) <= max(row['open'], row['close']) <= row['high']:
                    return {**result, 'error': 'DATA_INVALID'}
            return {**result, 'ok': True, 'count': len(rows), 'error': 'OK'}
        except PolicyError:
            return {**result, 'error': 'AUDIT_UNAVAILABLE'}
        except Exception:
            try:
                self._emit('SDK_ERROR')
            except Exception:
                return {**result, 'error': 'AUDIT_UNAVAILABLE'}
            return {**result, 'error': 'SDK_ERROR'}


class RobotObserver:
    """Read one host-approved status file, never infer status from processes.

    Approval must identify the exact canonical file outside untrusted requests.
    Parent symlinks/reparse points are rejected. Not a hostile-local-user sandbox:
    Windows handle-based no-follow enforcement belongs to the bridge host.
    """
    def __init__(self, approved_path=None, *, trusted_status=False, max_bytes=4096):
        self._path = Path(approved_path).absolute() if approved_path is not None else None
        self._trusted = trusted_status is True
        self._bound = max_bytes if type(max_bytes) is int and 1 <= max_bytes <= 4096 else 4096

    def observe(self, *, now, max_age=60):
        result = {'ok': False, 'status': 'unknown', 'error': 'PATH_APPROVAL_REQUIRED'}
        if self._path is None or not self._trusted:
            return result
        try:
            path = self._path
            if '..' in path.parts or any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
                return {**result, 'error': 'PATH_DENIED'}
            if path.resolve() != path or not path.is_file():
                return {**result, 'error': 'PATH_DENIED'}
            with path.open('rb') as handle:
                stat = os.fstat(handle.fileno())
                if stat.st_nlink != 1 or getattr(stat, 'st_file_attributes', 0) & 0x400:
                    return {**result, 'error': 'PATH_DENIED'}
                raw = handle.read(self._bound + 1)
            if len(raw) > self._bound:
                return {**result, 'error': 'STATUS_TOO_LARGE'}
            obj = json.loads(raw)
            if not isinstance(obj, dict) or set(obj) != {'schema', 'status', 'heartbeat_epoch'}:
                return {**result, 'error': 'STATUS_INVALID'}
            stamp = obj['heartbeat_epoch']
            if (obj['schema'] != 1 or type(obj['schema']) is not int or
                obj['status'] not in ('running', 'stopped') or type(stamp) not in (int, float) or
                not math.isfinite(stamp) or type(now) not in (int, float) or not math.isfinite(now) or
                type(max_age) not in (int, float) or not 0 < max_age <= 300):
                return {**result, 'error': 'STATUS_INVALID'}
            if not 0 <= now - stamp <= max_age:
                return {**result, 'error': 'STATUS_STALE'}
            return {'ok': True, 'status': obj['status'], 'error': 'OK'}
        except Exception:
            return {**result, 'error': 'STATUS_READ_ERROR'}
