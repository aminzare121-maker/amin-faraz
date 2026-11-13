#!/usr/bin/env python3
"""Opt-in research DEMO bypass. Never authorizes live broker orders.

The teacher verification gate remains intact. A caller can use this result
only for an isolated simulated/paper account, never as teacher approval.
"""
from dataclasses import dataclass
from typing import Any

class DemoBypassError(ValueError):pass

@dataclass(frozen=True)
class DemoPermission:
    mode:str
    broker_order_allowed:bool
    paper_order_allowed:bool
    teacher_method_verified:bool
    reason:str

def permission(*, account_kind:str, owner_opt_in:bool, candidate:Any,
               teacher_review:dict, enable_broker_demo_orders:bool=False)->DemoPermission:
    if account_kind!='DEMO':
        raise DemoBypassError('REAL_ACCOUNT_NEVER_ALLOWED')
    if not owner_opt_in:
        return DemoPermission('DISABLED',False,False,False,'OWNER_OPT_IN_REQUIRED')
    if not isinstance(teacher_review,dict) or teacher_review.get('rules_checked')!=13:
        raise DemoBypassError('REQUIRE_13_ROUTE_TEACHER_REVIEW')
    if not isinstance(candidate,dict) or candidate.get('side') not in ('BUY','SELL'):
        raise DemoBypassError('REQUIRE_EXPLICIT_CANDIDATE_SIDE')
    if not candidate.get('source') or not candidate.get('closed_bar_timestamp'):
        raise DemoBypassError('REQUIRE_CLOSED_BAR_AND_SOURCE')
    # Never issue a broker order from this research bypass. No verified entry
    # price, SL, TP, spreads, or teacher context has been established here.
    return DemoPermission('RESEARCH_PAPER_ONLY',False,True,False,
        'OWNER_APPROVED_UNVERIFIED_METHOD_PAPER_EXPERIMENT_NOT_TEACHER_APPROVAL')
