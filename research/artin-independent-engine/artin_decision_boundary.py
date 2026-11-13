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
    # Invalid/non-iterable input must fail closed rather than crash the
    # decision boundary before it can return a non-executable result.
    try:
        rows = tuple(outcomes)
    except (TypeError, ValueError):
        return {"decision": "BLOCKED", "reason": "INVALID_RULE_OUTCOMES", "executable": False}
    # Caller assertions (verified=True and evidence_id) are not independent
    # audio/chart replay approval. Default deny all entry candidates.
    # A string is not a collection of independently reviewed rule IDs.
    if isinstance(replay_approved_rule_ids, (str, bytes)):
        return {"decision": "BLOCKED", "reason": "INVALID_REPLAY_APPROVALS", "executable": False}
    try:
        approved_rows = tuple(replay_approved_rule_ids)
        if any(not isinstance(x, str) or not x.strip() for x in approved_rows):
            return {"decision": "BLOCKED", "reason": "INVALID_REPLAY_APPROVALS", "executable": False}
        # Duplicate approval IDs are ambiguous audit input, not independent replay.
        if len(approved_rows) != len(set(approved_rows)):
            return {"decision": "BLOCKED", "reason": "DUPLICATE_REPLAY_APPROVAL", "executable": False}
        approved = frozenset(approved_rows)
    except (TypeError, ValueError):
        return {"decision": "BLOCKED", "reason": "INVALID_REPLAY_APPROVALS", "executable": False}
    # Require the literal boolean True; truthy strings/integers must never
    # bypass the research-only DEMO boundary.
    if demo_only is not True:
        return {"decision": "BLOCKED", "reason": "REAL_DISABLED", "executable": False}
    if not rows:
        return {"decision": "BLOCKED", "reason": "NO_VERIFIED_TEACHER_RULES", "executable": False}
    for row in rows:
        if (not isinstance(row, RuleOutcome) or
            not isinstance(row.rule_id, str) or not row.rule_id.strip() or
            not isinstance(row.kind, str) or row.kind not in KINDS or
            not isinstance(row.action, str) or row.action not in ACTIONS or
            type(row.priority) is not int or type(row.session) is not int or
            not 1 <= row.session <= 25 or
            type(row.verified) is not bool or not row.verified or
            (row.kind == "entry" and row.action not in ("ENTER", "NO_TRADE", "HOLD")) or
            (row.kind == "exit" and row.action == "ENTER") or
            (row.kind in ("risk", "exception", "decision_order") and row.action in ("ENTER", "EXIT")) or
            not isinstance(row.evidence_id, str) or
            not row.evidence_id.strip()):
            return {"decision": "BLOCKED", "reason": "UNVERIFIED_OR_INVALID_RULE", "executable": False}
    ids = [r.rule_id for r in rows]
    if len(ids) != len(set(ids)):
        return {"decision": "BLOCKED", "reason": "DUPLICATE_RULE_ID", "executable": False}
    # Replay approvals must refer only to this decision batch. Extra IDs
    # could otherwise be mistaken for independently checked evidence.
    if approved.difference(ids):
        return {"decision": "BLOCKED", "reason": "REPLAY_APPROVAL_SET_MISMATCH",
                "executable": False}
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
    # An entry NO_TRADE and an EXIT describe different position contexts.
    # Do not infer that either one overrides the other from priority alone.
    if (any(r.kind == "entry" and r.action == "NO_TRADE" for r in rows)
            and any(r.kind == "exit" and r.action == "EXIT" for r in rows)):
        return {"decision": "BLOCKED", "reason": "EXIT_ENTRY_NO_TRADE_CONTEXT_UNVERIFIED",
                "executable": False}
    # Conflicting exit instructions cannot be arbitrated by priority alone.
    # An exit NO_TRADE is not proof that an existing position should remain open.
    if (any(r.kind == "exit" and r.action == "EXIT" for r in rows)
            and any(r.kind == "exit" and r.action == "NO_TRADE" for r in rows)):
        return {"decision": "BLOCKED", "reason": "EXIT_NO_TRADE_PRECEDENCE_UNVERIFIED",
                "executable": False}
    # A decision-order NO_TRADE and an EXIT also require teacher-confirmed
    # precedence. Neither a higher EXIT priority nor a higher veto priority
    # establishes which position context the instructor intended.
    if (any(r.kind == "decision_order" and r.action == "NO_TRADE" for r in rows)
            and any(r.kind == "exit" and r.action == "EXIT" for r in rows)):
        return {"decision": "BLOCKED", "reason": "EXIT_DECISION_ORDER_NO_TRADE_UNVERIFIED",
                "executable": False}
    # An exit-scoped NO_TRADE cannot be interpreted as a new-entry veto.
    # Resolve its missing position context before generic HOLD arbitration.
    if (any(r.kind == "exit" and r.action == "NO_TRADE" for r in rows)
            and not any(r.kind == "entry" for r in rows)
            and not any(r.kind in ("risk", "exception") and r.action == "NO_TRADE"
                        for r in rows)):
        return {"decision": "BLOCKED", "reason": "EXIT_NO_TRADE_POSITION_CONTEXT_UNVERIFIED",
                "executable": False}
    # A simultaneous NO_TRADE and HOLD is not resolved by arbitrary numeric
    # priority: the teacher's precedence must be replay-verified first.
    # This is especially important when a high-ranked HOLD would hide a
    # lower-ranked no-entry decision.
    if (any(r.action == "NO_TRADE" for r in rows)
            and any(r.action == "HOLD" for r in rows)):
        return {"decision": "BLOCKED", "reason": "NO_TRADE_HOLD_PRECEDENCE_UNVERIFIED",
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
    # A higher-ranked non-exit signal cannot silently suppress a lower-ranked
    # EXIT. Until teacher replay establishes the precedence, fail closed.
    # This also covers NO_TRADE from an entry rule and decision_order/risk HOLD.
    if any(r.kind == "exit" and r.action == "EXIT" for r in rows) and any(
        r.action != "EXIT" and r.priority >= min(
            e.priority for e in rows if e.kind == "exit" and e.action == "EXIT"
        ) for r in rows
    ):
        return {"decision": "BLOCKED", "reason": "EXIT_PRECEDENCE_UNVERIFIED",
                "executable": False}
    # An exit-scoped NO_TRADE does not establish a no-entry decision.
    # Without position context and a replayed teacher example, do not
    # relabel an exit instruction as an entry veto.
    if (any(r.kind == "exit" and r.action == "NO_TRADE" for r in rows)
            and not any(r.kind == "entry" for r in rows)
            and not any(r.kind in ("risk", "exception") and r.action == "NO_TRADE"
                        for r in rows)):
        return {"decision": "BLOCKED", "reason": "EXIT_NO_TRADE_POSITION_CONTEXT_UNVERIFIED",
                "executable": False}
    # Report missing exit/risk coverage before replay approval for an ENTER
    # candidate. Otherwise a structurally incomplete entry is mislabeled
    # merely as missing replay evidence, hiding the actual decision defect.
    if (any(r.kind == "entry" and r.action == "ENTER" for r in rows)
            and (not any(r.kind == "exit" for r in rows)
                 or not any(r.kind == "risk" for r in rows))):
        return {"decision": "BLOCKED", "reason": "EXIT_OR_RISK_UNVERIFIED",
                "executable": False}
    # HOLD and standalone NO_TRADE must not be presented as verified teacher
    # arbitration solely from caller-supplied flags and evidence identifiers.
    if not all(r.rule_id in approved for r in rows):
        return {"decision": "BLOCKED", "reason": "REPLAY_APPROVAL_MISSING",
                "executable": False}
    highest = max(r.priority for r in rows)
    top = [r for r in rows if r.priority == highest]
    if len({r.action for r in top}) != 1:
        return {"decision": "BLOCKED", "reason": "PRIORITY_CONFLICT", "executable": False}
    action = top[0].action
    if action == "ENTER":
        # Only an entry rule may authorize an entry candidate.
        if not any(r.kind == "entry" and r.action == "ENTER" for r in top):
            return {"decision": "BLOCKED", "reason": "NO_TOP_RANKED_ENTRY_RULE", "executable": False}
        # An entry requires independently reviewed exit and risk rules.
        if not any(r.kind == "exit" for r in rows) or not any(r.kind == "risk" for r in rows):
            return {"decision": "BLOCKED", "reason": "EXIT_OR_RISK_UNVERIFIED", "executable": False}
        if not all(r.rule_id in approved for r in rows):
            return {"decision": "BLOCKED", "reason": "REPLAY_APPROVAL_MISSING", "executable": False}
    if action == "EXIT" and not all(r.rule_id in approved for r in rows):
        return {"decision": "BLOCKED", "reason": "REPLAY_APPROVAL_MISSING", "executable": False}
    return {"decision": action, "reason": "VERIFIED_RULE_ARBITRATION",
            "rule_ids": [r.rule_id for r in top], "executable": False}
