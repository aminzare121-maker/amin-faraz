"""Fail-closed decision boundary for Artin research engine.

No teacher trading rule is inferred here. No broker connection or order API.
Only independently verified, time-anchored rule outcomes may enter the
decision arbitration; conflicting or incomplete inputs never produce ENTER.
"""
from dataclasses import dataclass
from typing import Iterable

KINDS = frozenset({"entry", "exit", "exception", "decision_order", "risk"})
ACTIONS = frozenset({"ENTER", "EXIT", "NO_TRADE", "HOLD"})

@dataclass(frozen=True)
class RuleOutcome:
    rule_id: str
    kind: str
    action: str
    verified: bool
    evidence_id: str
    priority: int
    session: int

def decide(outcomes: Iterable[RuleOutcome], *, demo_only: bool = True,
           replay_approved_rule_ids: Iterable[str] = ()) -> dict:
    """Return a non-executable decision. Unresolved precedence blocks entry."""
    rows = tuple(outcomes)
    # Caller assertions (verified=True and evidence_id) are not independent
    # audio/chart replay approval. Default deny all entry candidates.
    # A string is not a collection of independently reviewed rule IDs.
    if isinstance(replay_approved_rule_ids, (str, bytes)):
        return {"decision": "BLOCKED", "reason": "INVALID_REPLAY_APPROVALS", "executable": False}
    try:
        approved_rows = tuple(replay_approved_rule_ids)
        if any(not isinstance(x, str) or not x.strip() for x in approved_rows):
            return {"decision": "BLOCKED", "reason": "INVALID_REPLAY_APPROVALS", "executable": False}
        approved = frozenset(approved_rows)
    except (TypeError, ValueError):
        return {"decision": "BLOCKED", "reason": "INVALID_REPLAY_APPROVALS", "executable": False}
    if not demo_only:
        return {"decision": "BLOCKED", "reason": "REAL_DISABLED"}
    if not rows:
        return {"decision": "BLOCKED", "reason": "NO_VERIFIED_TEACHER_RULES"}
    for row in rows:
        if (not isinstance(row, RuleOutcome) or
            not isinstance(row.rule_id, str) or not row.rule_id.strip() or
            row.kind not in KINDS or row.action not in ACTIONS or
            type(row.priority) is not int or type(row.session) is not int or
            not 1 <= row.session <= 25 or
            type(row.verified) is not bool or not row.verified or
            (row.kind == "entry" and row.action not in ("ENTER", "NO_TRADE", "HOLD")) or
            (row.kind == "exit" and row.action == "ENTER") or
            (row.kind in ("risk", "exception", "decision_order") and row.action in ("ENTER", "EXIT")) or
            not isinstance(row.evidence_id, str) or
            not row.evidence_id.strip()):
            return {"decision": "BLOCKED", "reason": "UNVERIFIED_OR_INVALID_RULE"}
    ids = [r.rule_id for r in rows]
    if len(ids) != len(set(ids)):
        return {"decision": "BLOCKED", "reason": "DUPLICATE_RULE_ID"}
    # A veto prevents NEW entries, but must not silently override an EXIT
    # for an already open position. Position context and teacher precedence
    # are not established here: unresolved exit/veto conflict fails closed.
    if (any(r.kind in ("exception", "risk") and r.action == "NO_TRADE" for r in rows)
            and any(r.kind == "exit" and r.action == "EXIT" for r in rows)):
        return {"decision": "BLOCKED", "reason": "EXIT_VETO_PRECEDENCE_UNVERIFIED",
                "executable": False}
    # A verified exception or risk veto dominates entry regardless of rank.
    if any(r.kind in ("exception", "risk") and r.action == "NO_TRADE" for r in rows):
        # A caller-supplied verified flag cannot establish a teacher-approved veto.
        if not all(r.rule_id in approved for r in rows):
            return {"decision": "BLOCKED", "reason": "REPLAY_APPROVAL_MISSING",
                    "executable": False}
        return {"decision": "NO_TRADE", "reason": "VERIFIED_VETO", "executable": False}
    # An entry NO_TRADE cannot be outranked by ENTER without replay evidence.
    if (any(r.kind == "entry" and r.action == "ENTER" for r in rows)
            and any(r.action == "NO_TRADE" for r in rows)):
        return {"decision": "BLOCKED",
                "reason": "ENTRY_NO_TRADE_PRECEDENCE_UNVERIFIED",
                "executable": False}
    # Do not silently override a simultaneous EXIT with a higher-ranked ENTER.
    # Teacher-specific precedence is not yet evidenced, so block arbitration.
    if any(r.kind == "entry" and r.action == "ENTER" for r in rows) and any(
        r.kind == "exit" and r.action == "EXIT" for r in rows
    ):
        return {"decision": "BLOCKED", "reason": "ENTRY_EXIT_PRECEDENCE_UNVERIFIED", "executable": False}
    # Never silently suppress an EXIT signal behind a higher-ranked HOLD.
    # Without time-anchored replay proving exit precedence, fail closed.
    if any(r.kind == "exit" and r.action == "EXIT" for r in rows) and any(
        r.action == "HOLD" for r in rows
    ):
        return {"decision": "BLOCKED", "reason": "EXIT_HOLD_PRECEDENCE_UNVERIFIED",
                "executable": False}
    # HOLD and standalone NO_TRADE must not be presented as verified teacher
    # arbitration solely from caller-supplied flags and evidence identifiers.
    if not all(r.rule_id in approved for r in rows):
        return {"decision": "BLOCKED", "reason": "REPLAY_APPROVAL_MISSING",
                "executable": False}
    highest = max(r.priority for r in rows)
    top = [r for r in rows if r.priority == highest]
    if len({r.action for r in top}) != 1:
        return {"decision": "BLOCKED", "reason": "PRIORITY_CONFLICT"}
    action = top[0].action
    if action == "ENTER":
        # Only an entry rule may authorize an entry candidate.
        if not any(r.kind == "entry" and r.action == "ENTER" for r in top):
            return {"decision": "BLOCKED", "reason": "NO_TOP_RANKED_ENTRY_RULE"}
        # An entry requires independently reviewed exit and risk rules.
        if not any(r.kind == "exit" for r in rows) or not any(r.kind == "risk" for r in rows):
            return {"decision": "BLOCKED", "reason": "EXIT_OR_RISK_UNVERIFIED"}
        if not all(r.rule_id in approved for r in rows):
            return {"decision": "BLOCKED", "reason": "REPLAY_APPROVAL_MISSING", "executable": False}
    if action == "EXIT" and not all(r.rule_id in approved for r in rows):
        return {"decision": "BLOCKED", "reason": "REPLAY_APPROVAL_MISSING", "executable": False}
    return {"decision": action, "reason": "VERIFIED_RULE_ARBITRATION",
            "rule_ids": [r.rule_id for r in top], "executable": False}
