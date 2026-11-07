"""Only integrates reused pure accounting and risk modules with labeled fixtures."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'vendor/resilience'))
from decimal import Decimal as D
from faraz_core.money import open_lot,apply_cash_event,CashEvent,CloseDeal,close_lot,mark_pnl
from faraz_core.risk import VolumeRules,floor_volume

def matrix():
 rows=[]
 for volume in (D('.01'),D('.1'),D('1')):
  rules=VolumeRules('.01','.01','100','100');assert floor_volume(volume,rules)==volume
  lot=open_lot('synthetic-'+str(volume),'BUY','4000.30',volume,'100',confirmed=True)
  lot=apply_cash_event(lot,CashEvent('entry','ENTRY_FEE',-4*volume,True))
  mark=mark_pnl(lot,'4009','4009.30',unpaid_exit_cost=4*volume,slippage_reserve=0)
  part=volume if volume==D('.01') else volume/2
  closed=close_lot(lot,CloseDeal('close',part,'4009',-4*part,True))
  duplicate=close_lot(closed.ledger,CloseDeal('close',part,'4009',-4*part,True))
  remaining=closed.ledger.remaining_volume
  rest=mark_pnl(closed.ledger,'4009','4009.30',unpaid_exit_cost=4*remaining,slippage_reserve=0)
  # A proposed stop changes no ledger; confirmed synthetic close does.
  rows.append({'volume':str(volume),'symbol':'SYNTHETIC_XAU_FIXTURE_NOT_BROKER',
   'contract':'100','spread_hypothetical':'0.30','commission_roundtrip_per_lot_hypothetical':'8',
   'break_even_bid_hypothetical':'4000.38','break_even_net':str(mark_pnl(lot,'4000.38','4000.68',unpaid_exit_cost=4*volume,slippage_reserve=0).net),'gap_close_at_3994_net':str(close_lot(lot,CloseDeal('gap-close',volume,'3994',-4*volume,True)).allocation.money.net),'floating_before':str(mark.net),'realized_before':'0','stop_proposal_realized':'0',
   'confirmed_closed_volume':str(part),'realized_after':str(closed.allocation.money.net),
   'remaining_volume':str(remaining),'remaining_floating':str(rest.net),
   'net_conserved':closed.allocation.money.net+rest.net==mark.net,
   'duplicate_applied':duplicate.applied,'minimum_lot_note':'full close only; .005 below fixture min' if volume==D('.01') else 'partial close on fixture grid',
   'real_order_authority':False})
 return rows
