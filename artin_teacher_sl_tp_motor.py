"""FXM + Technical teacher-sourced stop/target decisions on the pinned Artin paper motor.

Sources: Technical(1).pdf pp13-17 (entry families and structural stop;
TP distance=SL distance*RR); FXM.pdf pp2-4 (1-2% risk, drawdown,
RR table, optional 0.8R/1.3R/1.8R ladder). A PDF can document the
rule when no video validation exists, but cannot produce *market facts*.
This module has no execution API and never reports actual fills.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Mapping

from core.capital import Instrument, Costs
from technical_teacher_policy import apply_technical_handout
from fxm_teacher_policy import (AccountRisk, PaperPosition, dec, risk_sized_plan,
    proposed_multi_targets, winrate_target_policy)


@dataclass(frozen=True)
class SingleTargetPaperPosition:
    side: str
    entry: Decimal
    stop: Decimal
    target: Decimal
    volume: Decimal
    pending_exit: str | None = None
    last_at: int | None = None

    def __post_init__(self):
        if self.side not in ('BUY','SELL'):
            raise ValueError('SIDE_REQUIRED')
        for name in ('entry','stop','target','volume'):
            object.__setattr__(self,name,dec(getattr(self,name),name))
        sign=Decimal(1) if self.side=='BUY' else Decimal(-1)
        if not(sign*(self.entry-self.stop)>0 and sign*(self.target-self.entry)>0):
            raise ValueError('STOP_AND_TARGET_MUST_BRACKET_ENTRY')
        if self.pending_exit not in (None,'STOP_TOUCH','TARGET_TOUCH'):
            raise ValueError('INVALID_PENDING_EXIT')
        if self.last_at is not None and (type(self.last_at) is not int or self.last_at<0):
            raise ValueError('INVALID_TIME')

    def observe_quote(self,bid,ask,at):
        if type(at) is not int or at<0 or (self.last_at is not None and at<self.last_at):
            raise ValueError('NONMONOTONIC_OR_INVALID_QUOTE_TIME')
        bid,ask=dec(bid,'bid'),dec(ask,'ask')
        if bid>ask:
            raise ValueError('INVALID_SPREAD')
        if self.pending_exit:
            return self,{'status':'AWAITING_VERIFIED_EXIT_FILL',
                         'pending_exit':self.pending_exit,'orders_enabled':False}
        quote=bid if self.side=='BUY' else ask
        sign=Decimal(1) if self.side=='BUY' else Decimal(-1)
        # Stop check has precedence, even if the market/data have a gap.
        if sign*(quote-self.stop)<=0:
            flag='STOP_TOUCH'; status='PAPER_STOP_TOUCH'
        elif sign*(quote-self.target)>=0:
            flag='TARGET_TOUCH';status='PAPER_SINGLE_TARGET_TOUCH'
        else:
            return replace(self,last_at=at),{'status':'PAPER_HOLD',
                 'stop':str(self.stop),'target':str(self.target),'orders_enabled':False}
        return replace(self,pending_exit=flag,last_at=at),{
            'status':status,'pending_exit':flag,'exit_fill_verified':False,
            'realized_pnl':None,'orders_enabled':False,
            'source':'Technical(1).pdf#page=17'}


def build_plan(*, route, side, decision_at, chart_evidence, account, instrument,
               costs, target_mode, target_mode_source, winrate=None,
               winrate_evidence=None, teacher_core_eligible=False):
    """Create a chart-sourced paper plan; never infer chart observations from a PDF.

    Two explicit, mutually exclusive TP modes: SINGLE_RR uses winrate table;
    THREE_TP uses the exact FXM page-4 schematic. Source label *selects*
    a mode, not proof that a video or market observation was validated.
    """
    def block(reason,**extra):
        return {'status':reason,'orders_enabled':False,'sources':[
            'Technical(1).pdf#pages=13-17','FXM.pdf#pages=2-4'],**extra}
    if teacher_core_eligible is not True:
        return block('WAIT_PINNED_13_ROUTE_ENTRY_CORE')
    if type(decision_at) is not int or decision_at<0:
        return block('INVALID_DECISION_TIME')
    if not isinstance(chart_evidence,Mapping):
        return block('WAIT_SOURCED_MARKET_GEOMETRY')
    if not isinstance(target_mode_source,str) or not target_mode_source.strip():
        return block('WAIT_PREDECLARED_TARGET_MODE_SOURCE')
    if target_mode not in ('SINGLE_RR','THREE_TP'):
        return block('REVIEW_UNLISTED_TARGET_MODE')
    if not isinstance(account,AccountRisk) or not isinstance(instrument,Instrument) or not isinstance(costs,Costs):
        return block('ACCOUNT_AND_ACTUAL_CONTRACT_REQUIRED')
    entry=chart_evidence.get('entry_price');stop=chart_evidence.get('structural_stop_price')
    if not isinstance(entry,Mapping) or not isinstance(stop,Mapping):
        return block('ENTRY_AND_STRUCTURE_STOP_MARKET_FACTS_REQUIRED')
    # These sources must come from the observed chart, not the teaching handout.
    try:
        if any(not isinstance(x.get('source'),str) or not x.get('source').strip()
               or x['source'].startswith(('FXM.pdf','Technical(1).pdf','SYNTHETIC_'))
               for x in (entry,stop)):
            return block('ACTUAL_CHART_PRICE_SOURCE_REQUIRED')
        sized=risk_sized_plan(account,side,entry['value'],stop['value'],instrument,costs,
                  entry_source=entry['source'],stop_source=stop['source'])
    except (KeyError,ValueError,TypeError) as e:
        return block('INVALID_ENTRY_STOP_OR_CONTRACT',detail=type(e).__name__)
    if sized.get('status')!='PAPER_SIZED_ONLY':
        return block('FXM_RISK_GATE_REJECTED',risk=sized)
    # FXM p4 explicitly cancels at <=33% regardless of target mode. The
    # 45%<winrate<66% note accompanies the three-stage management diagram;
    # do not silently apply it to another recorded band or an unknown rate.
    if winrate is None or not isinstance(winrate_evidence,str) or not winrate_evidence.strip():
        return block('WAIT_AUDITED_WINRATE_AND_PROVENANCE')
    try:
        observed_winrate=dec(winrate,'winrate_pct',allow_zero=True)
    except (ValueError,TypeError):
        return block('INVALID_WINRATE_EVIDENCE')
    if observed_winrate>100:return block('INVALID_WINRATE_EVIDENCE')
    if observed_winrate<=33:return block('FXM_CANCEL_LOW_WINRATE')
    if target_mode=='SINGLE_RR':
        try: rr=winrate_target_policy(winrate,evidence_source=winrate_evidence)
        except (ValueError,TypeError):return block('INVALID_WINRATE_EVIDENCE')
        if rr.get('status')!='RR_CANDIDATE_FROM_HANDOUT':
            return block('FXM_RR_UNRESOLVED',rr=rr)
    else:
        if not (Decimal('45')<observed_winrate<Decimal('66')):
            return block('FXM_THREE_TARGET_BAND_UNCONFIRMED')
        # The ladder is a stated alternate plan on FXM p4, not a guessed
        # personal-winrate branch. The source must name the exact handout.
        if target_mode_source!='FXM.pdf#page=4':
            return block('MULTI_TARGET_CHOICE_MUST_CITE_FXM_PAGE_4')
        rr={'status':'RR_CANDIDATE_FROM_HANDOUT','rr':'1.8',
            'source':['FXM.pdf#page=4'],'orders_enabled':False}
    decision=apply_technical_handout(route=route,side=side,at=decision_at,
               evidence=chart_evidence,fxm_sizing=sized,rr=rr)
    if decision.get('status')!='PAPER_TECHNICAL_FXM_CONDITIONS_SATISFIED':
        return block('TECHNICAL_ENTRY_OR_STOP_REJECTED',detail=decision)
    if target_mode=='THREE_TP':
        t=proposed_multi_targets(side,decision['entry'],decision['stop'],
                teacher_branch_confirmed=True,teacher_branch_source=target_mode_source)
        if t['status']!='PAPER_TARGETS_CALCULATED':
            return block('FXM_TP_LEVELS_REJECTED',detail=t)
        position=PaperPosition(side,dec(decision['entry'],'entry'),dec(decision['stop'],'stop'),
               dec(decision['stop'],'stop'),dec(t['tp1'],'tp1'),dec(t['tp2'],'tp2'),
               dec(t['tp3'],'tp3'),dec(decision['lots'],'lots'))
        targets={k:t[k] for k in ('tp1','tp2','tp3')}
    else:
        position=SingleTargetPaperPosition(side,dec(decision['entry'],'entry'),
               dec(decision['stop'],'stop'),dec(decision['target'],'target'),
               dec(decision['lots'],'lots'))
        targets={'tp':decision['target']}
    return {'status':'PAPER_TEACHER_PDF_TRADE_PLAN', 'mode':target_mode,
            'source_selection':target_mode_source,'route':route,'side':side,
            'entry':decision['entry'],'initial_stop':decision['stop'],
            'stop_anchor_kind':decision['stop_anchor_kind'],'lots':decision['lots'],
            'risk_budget':sized['risk_budget'],'modeled_max_loss':sized['modeled_max_loss'],
            'targets':targets,'rr_basis':rr,'chart_sources':decision['chart_source_fields'],
            'source_pages':decision['sources'] + ['FXM.pdf#page=4'],
            'position':position,'broker_fill_verified':False,'orders_enabled':False}


def replay_quotes(plan,quotes):
    """Replay explicit observed BID/ASK quotes: touches only, not actual fills.

    No candle high/low ordering is guessed. No false profits are computed.
    """
    if plan.get('status')!='PAPER_TEACHER_PDF_TRADE_PLAN':
        return {'status':'NO_REPLAY_WITHOUT_TEACHER_PDF_PLAN','orders_enabled':False}
    p=plan['position'];events=[]
    for quote in quotes:
        if not isinstance(quote,Mapping) or not all(k in quote for k in ('bid','ask','at','source')):
            raise ValueError('SOURCED_BID_ASK_EVENT_REQUIRED')
        if not isinstance(quote['source'],str) or not quote['source'].strip():
            raise ValueError('QUOTE_PROVENANCE_REQUIRED')
        p,e=p.observe_quote(quote['bid'],quote['ask'],quote['at'])
        events.append({'at':quote['at'],'source':quote['source'],**e})
        if p.pending_exit:break
    return {'status':'PAPER_QUOTES_REPLAYED','events':events,
            'latest_stop':str(p.current_stop if isinstance(p,PaperPosition) else p.stop),
            'exit_trigger':p.pending_exit,'exit_fill_verified':False,
            'realized_profit':None,'orders_enabled':False}