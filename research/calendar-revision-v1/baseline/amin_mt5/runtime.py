"""One owner-controlled Windows worker; durable commands and continuous broker monitor."""
import argparse
from dataclasses import asdict
from decimal import ROUND_FLOOR
import json
from pathlib import Path
import threading
import time
import subprocess
import sys
from .analysis import analyze
from .account_profiles import selection,presentation,execution_guard,commission_reserve
from .connectivity import BrokerConnection
from .execution import Execution
from .locking import exclusive
from .model import Intent,Policy,Stage,dec
from .mt5 import MT5Broker
from .news import NewsGate
from .performance import summarize
from .finance import FinancialLedger,account_key
from .risk import update_stage
from .security import Auth
from .store import Store
from .strategy import plan,size_and_target,version,artifact_hash,validate_artifact,approved_plan
from .alerts import Alerts
from .capital_notice import reason as capital_reason
from .calendar_policy import assess as assess_calendar,decision as calendar_decision,policy_version as calendar_version,digest,evidence_fingerprint,HORIZON_MS


class Worker:
    def __init__(self,config,auth,broker=None):
        self.config,self.auth,self.injected=config,auth,broker
        self.stop=threading.Event()
        self.research_process=None
        self.research_output=None
        self.last_research=0
        self.source_process=None;self.source_output=None;self.last_sources=0
        self.iran_process=None;self.iran_output=None;self.last_iran=0
        self.backup_process=None;self.backup_output=None;self.last_backup=0
        self.last_finance=0
        self.clock_process=None;self.last_clock_start=0

    def continuation_pending(self):
        from .continuation import requested
        return requested(self)

    def continuation_cycle(self,store):
        if not self.continuation_pending():return
        from .continuation import quiescent,publish,request_path
        from .rolling_worker import atomic
        folder=Path(self.config['_continuation_folder'])
        token=None
        try:
            token=request_path(self).read_text().strip()
            if quiescent(self):
                publish(self,store,token)
                atomic(folder/'continuation-ready.json',{'token':token})
        except (OSError,ValueError,KeyError,TypeError) as error:
            try:atomic(folder/'continuation-refused.json',{'token':token,'reason':str(error)})
            except OSError:pass
            # Upgrade refusal is not a market/connection fault.

    def calendar_cycle(self,store,snapshot,side,now,baseline_sha256=None,baseline_side=None,policy=None):
        """Local forward observation only. No model call, command or broker send."""
        from .forecast_evaluation import ForecastRegistry
        registry=ForecastRegistry(Path(self.config['database']).parent/'research'/'forecasts.sqlite3')
        report=store.get('amin_economic_calendar')
        policy_digest=calendar_version(baseline_sha256)
        forecast_side=side if baseline_side is None else baseline_side
        cost_policy=policy or Policy()
        quote_valid=(snapshot.account.mode=='demo' and snapshot.market.connected and
                     0<=now-snapshot.market.tick_ms<=2000)
        if quote_valid:
            mid=(dec(snapshot.market.ask)+dec(snapshot.market.bid))/2
            # Includes two spreads/slippage reserves and the policy commission.
            leg_cost=(dec(snapshot.market.ask)-dec(snapshot.market.bid)+dec(cost_policy.max_slippage)+
                      dec(commission_reserve(store.get('account_profile'),cost_policy.commission_per_lot))/dec(snapshot.spec.contract_size))/mid
            for forecast in registry.pending(now):
                if forecast['target_ms']<=snapshot.market.tick_ms<=forecast['target_ms']+60000:
                    registry.settle(forecast['id'],{'price':str(mid),'observed_ms':snapshot.market.tick_ms,
                        'received_ms':now,'cost_fraction':str(dec(forecast.get('entry_cost_fraction','0'))+leg_cost),'source':'broker-demo'},now)
            signal=report.get('decision_signal') if isinstance(report,dict) else None
            direction=signal.get('short_term',{}).get('direction') if isinstance(signal,dict) else None
            raw=assess_calendar(report,now,direction,self.config['symbol'])
            identity=digest({'report_id':raw['report_id'],'baseline':baseline_sha256})
            if (raw['allowed'] or raw['reason']=='CALENDAR_UNCERTAINTY_HIGH') and direction in ('buy','sell') and forecast_side in ('buy','sell') and not registry.contains(identity):
                forecast={'id':identity,'generated_ms':now,'target_ms':now+HORIZON_MS,
                          'entry_price':str(mid),'entry_observed_ms':snapshot.market.tick_ms,
                          'direction':direction,'uncertainty':raw['uncertainty'],'baseline_direction':forecast_side,
                          'policy_sha256':policy_digest,'source_ids':raw['source_ids'],'evidence_sha256':evidence_fingerprint(report['evidence'],raw['source_ids']),
                          'entry_cost_fraction':str(leg_cost),
                          'symbol':'XAUUSD','report_generated_ms':report['generated_ms']}
                registry.register_forecast(forecast,now,simulation=self.injected is not None or self.config.get('simulation',False))
            # Seven-day outlooks are evaluated separately, never as entry orders.
            if isinstance(signal,dict) and forecast_side in ('buy','sell'):
                import copy
                long_report=copy.deepcopy(report)
                long_report['decision_signal']['short_term']=copy.deepcopy(signal.get('long_term'))
                long_report['decision_signal']['long_term']={'direction':'neutral','uncertainty':'high','source_ids':[]}
                long_side=signal.get('long_term',{}).get('direction')
                long_raw=assess_calendar(long_report,now,long_side,self.config['symbol'])
                identity=digest({'report_id':digest(report),'horizon_ms':604800000,'baseline':baseline_sha256})
                if long_raw['allowed'] and not registry.contains(identity):
                    registry.register_forecast({'id':identity,'generated_ms':now,'target_ms':now+604800000,
                        'entry_price':str(mid),'entry_observed_ms':snapshot.market.tick_ms,'direction':long_side,
                        'uncertainty':long_raw['uncertainty'],'baseline_direction':forecast_side,'policy_sha256':policy_digest,
                        'source_ids':long_raw['source_ids'],'evidence_sha256':evidence_fingerprint(report['evidence'],long_raw['source_ids']),
                        'entry_cost_fraction':str(leg_cost),
                        'symbol':'XAUUSD','report_generated_ms':report['generated_ms']},now,
                        simulation=self.injected is not None or self.config.get('simulation',False))
        signal=report.get('decision_signal',{}) if isinstance(report,dict) else {}
        short_sources=signal.get('short_term',{}).get('source_ids',[]) if isinstance(signal,dict) else []
        long_sources=signal.get('long_term',{}).get('source_ids',[]) if isinstance(signal,dict) else []
        evaluation=registry.summarize(policy_digest,now,horizon_ms=HORIZON_MS,source_ids=short_sources)
        long_evaluation=registry.summarize(policy_digest,now,horizon_ms=604800000,source_ids=long_sources)
        from .calendar_policy import entry_decision
        news=NewsGate(self.config['news_file']).inspect(now) if self.config.get('news_file') else None
        effect=entry_decision(cost_policy,news,report,evaluation,now,side,self.config['symbol'],baseline_sha256)
        store.transaction('calendar_decision',effect,states={'calendar_decision':effect,'calendar_evaluation':evaluation,
                                                          'calendar_evaluation_long':long_evaluation})
        return effect

    def financial_cycle(self,store,broker,snapshot,positions,now):
        if now-self.last_finance<60000 or not hasattr(broker,'financial_deals'):return
        self.last_finance=now
        try:
            prior=store.db.execute('SELECT started_ms FROM financial_accounts WHERE account=?',(account_key(snapshot.account.identity),)).fetchone()
            since=prior['started_ms'] if prior else now-30*86400000
            deals=broker.financial_deals(since)
            floating=sum((dec(p.get('profit',0))+dec(p.get('swap',0)) for p in positions),dec(0))
            FinancialLedger(store).observe(snapshot.account,deals,floating,now)
            store.transaction('financial_collection_status',{'available':True},states={'financial_collection':{'available':True,'observed_ms':now,'floating_pnl':str(floating)}})
        except Exception as error:
            store.transaction('financial_collection_status',{'available':False,'error_type':type(error).__name__},states={'financial_collection':{'available':False,'observed_ms':now}})

    def backup_cycle(self,store,now):
        if not self.config.get('_config_path') or not self.config.get('backup_enabled',True):return
        if self.backup_process:
            if self.backup_process.poll() is None:return
            if self.backup_output.exists():
                report=json.loads(self.backup_output.read_text())
                store.transaction('operational_backup_verified',report,states={'operational_backup':report})
                Alerts(store).condition('backup_failed',False,'critical','', '',now)
            else:Alerts(store).condition('backup_failed',True,'critical','پشتیبان تأیید نشد','نسخه پشتیبان تازه قابل تأیید نیست؛ بازیابی و فضای دیسک را بررسی کن.',now)
            self.backup_process=None;return
        if self.continuation_pending() or now-self.last_backup<6*3600000:return
        root=Path(self.config['database']).parent;self.last_backup=now
        directory=self.config.get('backup_directory',str(root/'encrypted-backups'))
        key=self.config.get('backup_key',str(root/'recovery-key.secret'))
        self.backup_output=root/f'backup-job-{now}.json'
        self.backup_process=subprocess.Popen([sys.executable,'-m','amin_mt5.recovery','create',self.config['_config_path'],directory,key,
                                              '--report',str(self.backup_output)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def iran_cycle(self,store,now):
        if self.iran_process:
            if self.iran_process.poll() is None:
                if now-self.last_iran>120000:self.iran_process.terminate()
                return
            if self.iran_output.exists():
                report=json.loads(self.iran_output.read_text(encoding='utf-8'))
                from .research_ledger import ResearchLedger
                ledger=ResearchLedger(Path(self.config['database']).parent/'research'/'ledger.sqlite3')
                report['changes']=ledger.register_iran([r for item in report.get('series',[]) for r in item.get('observations',[])])
                store.transaction('iran_statistical_update',{'changes':report['changes'],'used_for_trading':False},states={'iran_research':report})
                from .local_research import iran_report,persist
                persist(store,iran_report(report,now))
            self.iran_process=None;return
        if self.continuation_pending() or now-self.last_iran<3600000:return
        root=Path(self.config['database']).parent/'iran-research';root.mkdir(exist_ok=True)
        self.last_iran=now;self.iran_output=root/f'observation-{now}.json'
        self.iran_process=subprocess.Popen([sys.executable,'-m','amin_mt5.iran_research',str(root/'raw'),str(self.iran_output)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def independent_sources(self,store,now):
        try:self.iran_cycle(store,now)
        except Exception as error:
            self.last_iran=now;self.iran_process=None
            store.transaction('iran_statistical_fault',{'type':type(error).__name__,'used_for_trading':False})
        try:self.source_cycle(store,now)
        except Exception as error:
            self.last_sources=now;self.source_process=None
            store.transaction('supplemental_sources_fault',{'type':type(error).__name__},
                              states={'supplemental_source_fault':{'type':type(error).__name__,'observed_ms':now}})

    def source_cycle(self,store,now):
        if self.source_process:
            if self.source_process.poll() is None:
                if now-self.last_sources>120000:self.source_process.terminate()
                return
            if self.source_output.exists():
                report=json.loads(self.source_output.read_text())
                discoveries=[r for s in report['sources'] if s.get('data',{}).get('metadata_only') is True for r in s.get('data',{}).get('records',[])]
                if discoveries:
                    from .research_ledger import ResearchLedger
                    ledger=ResearchLedger(Path(self.config['database']).parent/'research'/'ledger.sqlite3')
                    report['new_research_count']=ledger.discover(discoveries)
                    report['total_research_count']=ledger.counts()['discoveries']
                else:report['new_research_count']=0
                store.transaction('supplemental_sources_update',{'sources':[{k:s.get(k) for k in ('id','status','received_ms')} for s in report['sources']], 'new_research_count':report['new_research_count']},states={'supplemental_sources':report})
                from .local_research import calendar_report,persist
                prior=store.get('local_public_report',{})
                local=calendar_report(report,now,prior.get('foresight_framework'))
                prior_time=prior.get('generated_ms')
                refresh_factual=(type(prior_time) is not int or now-prior_time>=120000)
                if refresh_factual or local['facts_fingerprint']!=prior.get('facts_fingerprint') or local['analysis_version']!=prior.get('analysis_version'):
                    active=store.get('amin_economic_calendar',{})
                    preserve_model=(active.get('provider')=='netarz' and type(active.get('generated_ms')) is int and 0<=now-active['generated_ms']<=180000)
                    persist(store,local,select=not preserve_model)
            self.source_process=None;return
        if store.get('sources_polling_enabled',True) is not True:return
        if self.continuation_pending() or now-self.last_sources<60000:return
        folder=Path(self.config['database']).parent/'supplemental';folder.mkdir(exist_ok=True)
        self.source_output=folder/f'observation-{now}.json';self.last_sources=now
        self.source_process=subprocess.Popen([sys.executable,'-m','amin_mt5.sources',str(folder/'raw'),str(self.source_output)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def research_cycle(self,store,broker,now):
        from .research_supervision import retry_delay,validate_result
        job=store.get('research_job_status',{})
        def failed(reason):
            failures=int(job.get('consecutive_failures',0))+1
            state={'state':'retry_wait','reason':reason,'observed_ms':now,
                   'consecutive_failures':failures,'retry_at_ms':now+retry_delay(failures)}
            store.transaction('research_retry_scheduled',state,states={'research_job_status':state})
        if self.research_process:
            if self.research_process.poll() is None:
                if now-self.last_research>60000 and job.get('state')!='stopping':
                    self.research_process.terminate()
                    store.transaction('research_timeout',{'reason':'RESEARCH_JOB_TIMEOUT'},states={
                        'research_job_status':{**job,'state':'stopping','observed_ms':now}})
                return
            try:
                if self.research_process.returncode!=0:raise ValueError('RESEARCH_JOB_FAILED')
                if self.research_output is None or not self.research_output.is_file():raise ValueError('RESEARCH_OUTPUT_MISSING')
                if self.research_output.stat().st_size>10000000:raise ValueError('RESEARCH_OUTPUT_TOO_LARGE')
                result=validate_result(json.loads(self.research_output.read_text()),now)
                store.transaction('research_result',result,states={'research':result,'research_job_status':{
                    'state':'completed','observed_ms':now,'consecutive_failures':0,'next_run_ms':self.last_research+3600000}})
            except (ValueError,KeyError,TypeError,OSError):
                failed('RESEARCH_OUTPUT_OR_PROCESS_INVALID')
            self.research_process=None
            return
        retry=job.get('state')=='retry_wait'
        if self.continuation_pending() or (retry and now<job.get('retry_at_ms',now)) or (not retry and now-self.last_research<3600000):return
        try:
            bars=broker.candles('15m',2000)
            store.remember_bars(self.config['symbol'],'15m',bars,now)
            folder=Path(self.config['database']).parent/'research';folder.mkdir(exist_ok=True)
            self.research_output=folder/f'evaluation-{now}.json';self.last_research=now
            self.research_process=subprocess.Popen([sys.executable,'-m','amin_mt5.research_worker',self.config['database'],
                                                    self.config['symbol'],str(self.research_output)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            store.transaction('research_job_started',{'started_ms':now},states={'research_job_status':{
                'state':'running','started_ms':now,'consecutive_failures':job.get('consecutive_failures',0)}})
        except (OSError,ValueError):
            self.research_process=None;failed('RESEARCH_START_FAILED')

    def close_all(self,execution,store,broker,request_id):
        if not store.verify_chain():raise RuntimeError('Audit invalid; close command blocked')
        execution.pause_new_orders('Owner close request: block new orders first')
        if store.unresolved():return {'status':'BLOCKED','reason':'Resolve unknown orders before manual close'}
        results=[]
        for p in broker.positions():
            if p['symbol']!=self.config['symbol']:continue
            rid=request_id+':'+str(p['ticket'])
            with exclusive(execution.lock):
                if store.intent(rid):continue
                store.transaction('close_reserved',{'position':p['ticket']},intent=(rid,'RESERVED',{'position':p['ticket']},None,'Explicit owner close'))
                try:receipt=broker.close_position(p['ticket'],rid)
                except Exception:receipt=None
                status=receipt.status if receipt else 'UNKNOWN'
                store.transaction('close_result',{'request_id':rid,'status':status},intent=(rid,status,{},receipt.reference if receipt else None,'Owner close'))
                results.append({'ticket':p['ticket'],'status':status})
                if status=='UNKNOWN':execution.reconciled=False;break
        return {'positions':results,'note':'Pending orders are not cancelled by close positions'}

    def timed_exits(self,execution,store,broker,positions,now):
        if self.config.get('observe_only',False):return
        if self.stop.is_set() or store.unresolved() or not getattr(broker,'supports_automatic',False):return
        owned={MT5Broker.comment(row['request_id']):json.loads(row['payload']) for row in store.db.execute(
            "SELECT request_id,payload FROM intents WHERE status='ACCEPTED' AND request_id LIKE 'auto-%'") if not row['request_id'].startswith('auto-close-')}
        for position in positions:
            original=owned.get(position.get('comment'))
            if not original or position.get('symbol')!=self.config['symbol'] or position.get('magic')!=580015:continue
            limit=original.get('max_holding_seconds',0)
            if not limit or now-original['created_ms']<limit*1000:continue
            request_id=f"auto-close-{position['ticket']}-{original['created_ms']}"
            with exclusive(execution.lock):
                if store.intent(request_id):continue
                if store.unresolved():return
                if not store.verify_chain():raise RuntimeError('Audit invalid; timed close blocked')
                store.transaction('timed_close_reserved',{'position':position['ticket'],'holding_seconds':limit},
                                  intent=(request_id,'RESERVED',{'position':position['ticket']},None,'Pre-approved strategy time exit'))
                try:receipt=broker.close_position(position['ticket'],request_id)
                except Exception:receipt=None
                status=receipt.status if receipt else 'UNKNOWN'
                store.transaction('timed_close_result',{'request_id':request_id,'status':status},
                                  intent=(request_id,status,{},receipt.reference if receipt else None,'Strategy time exit'))
                if status=='UNKNOWN':execution.reconciled=False;break

    def command(self,cmd,execution,store,broker,now):
        payload=json.loads(cmd['payload']);action=cmd['action']
        if self.config.get('observe_only',False) and action not in {'pause','reconcile','acknowledge_historical_cashflow','enable_manual_protection','disable_demo_autonomy'}:
            raise PermissionError('OBSERVATION_ONLY')
        connection=store.get('broker_connection')
        if connection is not None and action in {'resume','demo_order','approve_demo_strategy','close_all','acknowledge_restore','enable_manual_protection','enable_demo_autonomy'}:
            if connection.get('verified') is not True or not connection.get('generation') or payload.get('_connection_generation')!=connection['generation']:
                raise ValueError('Connection changed; submit a fresh owner command')
        if time.time()-cmd['created']>60 and action not in {'pause','reconcile'}:
            raise ValueError('Command stale; owner must send a fresh command')
        if action=='pause':
            from .demo_autonomy import disarm
            disarm(store,'Authenticated owner pause')
            execution.pause_new_orders('Authenticated owner command');return {'paused':True}
        if action=='enable_demo_autonomy':
            from .demo_autonomy import arm
            with exclusive(execution.lock):return arm(store,broker,now,payload,cmd['id'])
        if action=='disable_demo_autonomy':
            from .demo_autonomy import disarm
            with exclusive(execution.lock):disarm(store,'Authenticated owner disabled autonomy')
            return {'armed':False,'paused':True}
        if action=='resume':execution.resume_new_orders('Authenticated owner command',now);return {'paused':False}
        if action=='reconcile':return {'complete':execution.reconcile(now)}
        if action=='enable_manual_protection':
            if self.config.get('manual_protection_capable') is not True:raise PermissionError('Manual protection unavailable in this service')
            from .protection_manager import activate
            with exclusive(execution.lock):
                return activate(store,broker,self.config['symbol'],now,payload.get('code'),payload.get('include_existing'),cmd['id'])
        if action=='acknowledge_historical_cashflow':
            from .cashflow_review import acknowledge
            with exclusive(execution.lock):
                account=broker.snapshot(now).account
                return acknowledge(store,account,payload.get('review_sha256'),cmd['id'],now)
        if action=='set_account_profile':
            from .demo_autonomy import disarm
            disarm(store,'Owner changed account profile')
            account=broker.snapshot(now).account
            selected=selection(payload.get('profile_id'),account.identity,now)
            execution.pause_new_orders('Owner changed account product; review before resuming')
            with exclusive(execution.lock):
                store.transaction('account_profile_selected',{'profile_id':selected['profile_id'],'command_id':cmd['id']},
                    states={'account_profile':selected,'demo_strategy_approval':None,'paused':True})
            return {'profile_id':selected['profile_id'],'new_orders_paused':True,'strategy_approval_cleared':True,
                    'product_name_verified_by_broker':False}
        if action=='acknowledge_restore':
            if payload.get('confirmation')!='RECONCILED DEMO RESTORE' or not store.get('restore_review_required'):raise ValueError('Explicit recovery review required')
            if not execution.reconcile(now):raise ValueError('Broker reconciliation incomplete')
            snapshot=broker.snapshot(now);stage=store.get('stage',{})
            if stage.get('account_identity')!=snapshot.account.identity:raise ValueError('Restored account differs')
            store.transaction('owner_restore_review',{'command_id':cmd['id']},states={'restore_review_required':False})
            return {'reviewed':True,'new_orders_paused':True,'recovery_halt_until_ms':store.get('recovery_halt_until_ms')}
        if action=='disable_demo_strategy':
            from .demo_autonomy import disarm
            disarm(store,'Authenticated owner disabled strategy')
            store.transaction('demo_strategy_disabled',{},states={'demo_strategy_approval':None});return {'enabled':False}
        if action=='approve_demo_strategy':
            result=store.get('research',{})
            if not result.get('demo_review_eligible') or result.get('fresh_holdout') is not True or result.get('engine_sha256')!=version():raise ValueError('No current eligible independent research result')
            artifact=validate_artifact(result['artifact']);identity=artifact_hash(artifact)
            if payload.get('strategy_sha256')!=identity or result.get('strategy_sha256')!=identity:raise ValueError('Owner must confirm the exact candidate artifact')
            if artifact['training_end_ms']>now:raise ValueError('Future training data')
            if not getattr(broker,'supports_automatic',False):raise ValueError('Automatic strategy requires a validated hedging account')
            account=broker.snapshot(now).account.identity
            approval={'strategy_sha256':identity,'engine_sha256':version(),'artifact':artifact,'account':account,
                      'approved_ms':now,'expires_ms':now+7*86400000,'command_id':cmd['id']}
            store.transaction('owner_demo_strategy_approval',approval,states={'demo_strategy_approval':approval})
            return {'enabled':True,'scope':'DEMO account only','strategy_sha256':identity}
        if action=='close_all':return self.close_all(execution,store,broker,cmd['id'])
        if action=='demo_order':
            s=broker.snapshot(now);side=payload['side']
            intent=Intent(cmd['id'],self.config['symbol'],side,str(payload['volume']),str(payload['stop_loss']),
                          s.market.ask if side=='buy' else s.market.bid,now,'Authenticated owner DEMO test',('owner-request','broker-snapshot'),
                          '0','0',str(payload.get('take_profit','0')))
            return execution.execute(intent,now)
        raise ValueError('Unknown action')

    def cycle(self,store,broker,execution,now):
        if self.stop.is_set():return
        phase_start=time.perf_counter();phase_last=phase_start;phase_ms={}
        def mark_phase(name):
            nonlocal phase_last
            current=time.perf_counter();phase_ms[name]=round((current-phase_last)*1000,3);phase_last=current
        cycle_started_ms=now
        collected=time.monotonic()
        frames={f:broker.candles(f,120) for f in ('1m','3m','5m','15m','1h','4h','1D','1W','1M')}
        mark_phase('candles')
        now+=max(0,int((time.monotonic()-collected)*1000))
        selected=store.get('account_profile')
        if hasattr(broker,'commission_reserve'):broker.commission_reserve=commission_reserve(selected,execution.policy.commission_per_lot)
        snapshot=broker.snapshot(now)
        now=max(now,snapshot.market.account_ms)
        mark_phase('snapshot')
        source=getattr(broker,'native_clock_source',None)
        if self.config.get('_external_clock_collector') and isinstance(source,dict):
            if store.get('native_clock_source')!=source:
                store.transaction('native_clock_source_verified',{},states={'native_clock_source':source})
        if (not self.config.get('_external_clock_collector') and self.injected is None and isinstance(source,dict) and all(source.get(k) for k in ('commondata_path','data_path'))
                and (self.clock_process is None or not self.clock_process.is_alive()) and now-self.last_clock_start>=60000):
            import multiprocessing
            from .native_history import run_collector
            if self.clock_process is not None:self.clock_process.join(timeout=1)
            self.clock_process=multiprocessing.get_context('spawn').Process(target=run_collector,
                args=(self.config['database'],source,snapshot.account.identity,self.config['symbol'],self.stop),
                name='amin-native-clock-collector',daemon=True)
            self.last_clock_start=now;self.clock_process.start()
        account_profile=presentation(selected,broker.account_conditions() if hasattr(broker,'account_conditions') else {})
        original=store.get('stage')
        stage=Stage(**original) if original else Stage.initial(__import__('datetime').datetime.fromtimestamp(now/1000,__import__('datetime').timezone.utc).date().isoformat(),snapshot.account)
        if stage.account_identity!=snapshot.account.identity:raise PermissionError('Account changed')
        stage=update_stage(stage,snapshot.account.equity,now,execution.policy)
        price_asof=(now//1000+snapshot.market.clock_offset_seconds) if snapshot.market.clock_mapping_verified else None
        analysis=analyze(frames,now//1000,price_asof=price_asof)
        for frame,bars in frames.items():store.remember_bars(self.config['symbol'],frame,bars,now)
        mark_phase('analysis_and_bar_archive')
        positions=broker.positions()
        if self.config.get('manual_protection_capable') is True:
            from .protection_manager import cycle as protection_cycle
            try:protection_cycle(store,broker,snapshot,frames['15m'],now,capable=True)
            except Exception as error:
                store.transaction('manual_protection_fault',{'error_type':type(error).__name__},states={
                    'manual_protection_status':{'observed_ms':now,'fault':type(error).__name__,'positions':[]}})
        assurance_deals=broker.deals()
        performance=summarize(assurance_deals)
        from .strategy_assurance import closed_positions,performance_drift
        try:
            completed=closed_positions(assurance_deals,positions,now,symbol=self.config['symbol'])
            performance['closed_position_statistics']=completed['statistics']
            reference=store.get('performance_monitor_reference')
            active_approval=store.get('demo_strategy_approval',{}) or {}
            if reference and reference.get('strategy_sha256')!=active_approval.get('strategy_sha256'):reference=None
            drift=performance_drift(completed['rows'],reference,now)
        except (ValueError,KeyError,TypeError,ArithmeticError):
            drift={'state':'invalid_monitoring_evidence','block_new_entries':True}
        if drift.get('block_new_entries') and not store.get('paused',True):
            execution.pause_new_orders('Performance monitor requires review; open-position protection retained')
        mark_phase('positions_protection_and_deals')
        if self.injected is None:
            # Full audit/protection reads can take longer than quote freshness.
            # Re-observe price AND exposure after that work; never refresh the
            # timestamp on the old quote or reuse pre-modification exposure.
            now=cycle_started_ms+max(0,int((time.monotonic()-collected)*1000))
            snapshot=broker.snapshot(now)
            now=max(now,snapshot.market.account_ms)
            price_asof=(now//1000+snapshot.market.clock_offset_seconds) if snapshot.market.clock_mapping_verified else None
            analysis=analyze(frames,now//1000,price_asof=price_asof)
            mark_phase('post_audit_snapshot')
        reinvestment={'ready':False,'reason':'ACCOUNTING_ADAPTER_UNAVAILABLE','rule':'retained-booked-profit-two-thirds-v1'}
        if hasattr(broker,'capital_accounting'):
            from .profit_reinvestment import apply as reinvest_profit
            try:
                capital_observation=broker.capital_accounting()
                now=max(now,capital_observation['observed_ms'])
                stage,reinvestment=reinvest_profit(store,stage,snapshot.account,capital_observation,now)
                if reinvestment.get('ready'):
                    # Full ticket history avoids expiring deposits from a rolling
                    # 30-day window or missing server-clock-labelled same-day rows.
                    performance=summarize(capital_observation['deals'])
                    from .profit_reinvestment import initialize_cashflow_reference
                    initialize_cashflow_reference(store,stage,snapshot.account,capital_observation,now)
            except Exception as error:
                reinvestment={'ready':False,'reason':'ACCOUNTING_UNAVAILABLE','error_type':type(error).__name__,
                              'rule':'retained-booked-profit-two-thirds-v1'}
        if not self.config.get('observe_only',False) and not analysis.get('invalid_frames'):
            from .adaptive_exit import cycle as adaptive_exit_cycle
            try:adaptive_exit_cycle(store,broker,snapshot,frames['15m'],positions,now)
            except Exception as error:
                store.transaction('adaptive_exit_fault',{'error_type':type(error).__name__},states={
                    'adaptive_exit_status':{'installed':True,'fault':type(error).__name__,'observed_ms':now}})
        if store.unresolved() and not execution.reconciled:
            execution.reconcile(now)
        self.timed_exits(execution,store,broker,positions,now)
        carry_status={'installed':True,'positions':[],'entry_blocked':False}
        if not self.config.get('observe_only',False):
            from .carry_policy import cycle as carry_cycle
            try:carry_status=carry_cycle(store,broker,execution,snapshot,positions,analysis,frames['15m'],now)
            except Exception as error:carry_status={'installed':True,'positions':[],'entry_blocked':True,'fault':type(error).__name__}
        target=dec(stage.day_start_equity)*(1+dec(execution.policy.daily_profit_target))
        target_reached=dec(snapshot.account.equity)>=target
        if target_reached and execution.policy.daily_profit_target_halts and not store.get('paused',True):execution.pause_new_orders('Daily equity profit target reached; open positions retained')
        from .account_risk_diagnostics import assess as assess_account_risk
        account_risk_guard=assess_account_risk(stage,snapshot,execution.policy)
        breached=account_risk_guard['breached']
        if breached and not store.get('paused',True):execution.pause_new_orders('Independent account exposure/drawdown guard')
        cashflow_reference=store.get('cashflow_reference',performance['cashflow_usd'])
        cashflow_changed=dec(cashflow_reference)!=dec(performance['cashflow_usd'])
        if cashflow_changed and not store.get('paused',True):execution.pause_new_orders('Account cashflow changed; owner rebase review required')
        from .demo_autonomy import maintain_candidate,advance as advance_autonomy,valid_mandate
        maintain_candidate(store,snapshot,now,observation_only=self.config.get('observe_only',False))
        approval=store.get('demo_strategy_approval')
        approved=bool(approval and getattr(broker,'supports_automatic',False) and approval.get('engine_sha256')==version() and approval.get('account')==snapshot.account.identity
                      and approval.get('expires_ms',0)>now and artifact_hash(approval.get('artifact'))==approval.get('strategy_sha256'))
        if approved and approval.get('authorization')=='owner-demo-autonomy-mandate' and not valid_mandate(store,snapshot):approved=False
        proposal=approved_plan(frames['15m'],now//1000,approval['artifact'],price_asof=price_asof) if approved and not analysis.get('invalid_frames') else None
        side=proposal['side'] if proposal else analysis['side']
        # An expired approval may still supply its frozen artifact for shadow
        # measurement; it never becomes permission to submit orders.
        shadow=approval if isinstance(approval,dict) else store.get('research',{})
        shadow_artifact=shadow.get('artifact') if isinstance(shadow,dict) else None
        shadow_identity=None;shadow_proposal=None
        try:
            if shadow_artifact is not None:
                validate_artifact(shadow_artifact)
                shadow_identity=artifact_hash(shadow_artifact)
                shadow_proposal=approved_plan(frames['15m'],now//1000,shadow_artifact,price_asof=price_asof) if not analysis.get('invalid_frames') else None
        except (ValueError,TypeError,KeyError):shadow_identity=None
        # Owner separation: calendar/sentiment/Iran research are reports only.
        # Do not even read their reports or evaluate their models on this path.
        calendar_effect={'mode':'report-only','affects_trade_decisions':False,
                         'can_authorize_orders':False,'observed_ms':now}
        context=[analysis['features'].get(f,{}) for f in ('1h','4h','1D')]
        mark_phase('candidate_and_calendar')
        expected='up' if side=='buy' else 'down'
        aligned=side in ('buy','sell') and all(f.get('ready') and f.get('trend')==expected for f in context)
        reasons=[]
        if store.get('owner_order_hold',False):reasons.append('OWNER_ORDER_HOLD')
        if hasattr(broker,'capital_accounting') and not reinvestment['ready']:reasons.append('REINVESTMENT_ACCOUNTING_UNVERIFIED')
        if self.config.get('observe_only',False):reasons.append('OBSERVATION_ONLY')
        profile_guard=execution_guard(selected,snapshot.account.identity,account_profile.get('observed'))
        if profile_guard:reasons.append(profile_guard)
        if analysis.get('invalid_frames'):reasons.append('INVALID_MARKET_DATA')
        if not snapshot.market.news_clear:reasons.append('NEWS_NOT_CLEARED')
        if not execution.reconciled:reasons.append('RECONCILIATION_REQUIRED')
        if store.get('paused',True):reasons.append('NEW_ORDERS_PAUSED')
        if store.unresolved():reasons.append('UNKNOWN_ORDER')
        if not aligned or (approved and not proposal):reasons.append('NO_ALIGNED_SETUP')
        if drift.get('block_new_entries'):reasons.append('PERFORMANCE_MONITOR_VETO')
        timing=[analysis['features'].get(f,{}) for f in ('1m','3m','5m')]
        # This is entry trend confirmation, not UTC clock/freshness validation.
        # Without a directional candidate there is no entry trend to confirm.
        if side in ('buy','sell') and sum(bool(f.get('ready')) and f.get('trend')==expected for f in timing)<2:
            reasons.append('EXECUTION_TIMING_NOT_ALIGNED')
        if breached:reasons.append('ACCOUNT_RISK_GUARD')
        if target_reached and execution.policy.daily_profit_target_halts:reasons.append('DAILY_PROFIT_TARGET_REACHED')
        if not -250<=now-snapshot.market.tick_ms<=2000:reasons.append('FRESH_PRICE_REQUIRED')
        if cashflow_changed:reasons.append('CASHFLOW_REVIEW_REQUIRED')
        if carry_status.get('entry_blocked'):reasons.append('BROKER_BREAK_APPROACHING')
        from .auto_sizing import calculate as calculate_volume
        automatic_sizing=calculate_volume(proposal,snapshot.market.ask if proposal and proposal['side']=='buy' else snapshot.market.bid,
            stage.active_capital,snapshot.account.equity,snapshot.spec,policy=execution.policy,exposure=snapshot.exposure,
            commission=commission_reserve(selected,execution.policy.commission_per_lot))
        capital_block=capital_reason(stage.active_capital,snapshot.account.equity,execution.policy.minimum_active,
            valid=not analysis.get('invalid_frames') and -250<=now-snapshot.market.tick_ms<=2000,
            candidate=proposal,entry=(snapshot.market.ask if proposal and proposal['side']=='buy' else snapshot.market.bid),spec=snapshot.spec,
            policy=execution.policy,exposure=snapshot.exposure,commission=commission_reserve(selected,execution.policy.commission_per_lot))
        if capital_block:reasons.append(capital_block)
        autonomy=advance_autonomy(store,execution,snapshot,now,reasons,approved=approved,
                                  observation_only=self.config.get('observe_only',False))
        if autonomy['state']=='running':reasons=[r for r in reasons if r!='NEW_ORDERS_PAUSED']
        dashboard={'connected':True,'data_source':'broker-demo','execution_mode':'demo-only','observation_only':self.config.get('observe_only',False),'observed_ms':now,'account_profile':account_profile,
                   'snapshot':asdict(snapshot),'stage':asdict(stage),'positions':positions,'paused':store.get('paused',True),
                   'daily_target_equity':str(target),'daily_target_reached':target_reached,
                   'daily_equity_change':str(dec(snapshot.account.equity)-dec(stage.day_start_equity)),
                   'daily_pnl':None if analysis.get('invalid_frames') or cashflow_changed else str(dec(snapshot.account.equity)-dec(stage.day_start_equity)),
                   'daily_pnl_status':'unverified_time_or_cashflow' if analysis.get('invalid_frames') or cashflow_changed else 'equity_change',
                   'floating_pnl':str(sum((dec(p.get('profit',0))+dec(p.get('swap',0)) for p in positions),dec(0))),
                   'decision':{'action':'candidate_for_risk_check' if approved and not reasons else 'no_trade',
                               'reasons':reasons or ([] if approved else ['AWAITING_VALIDATED_RESEARCH_APPROVAL']), 'analysis':analysis,
                               'calendar':calendar_effect},
                   'capital_warning':capital_block,'automatic_orders_enabled':approved,'demo_autonomy':autonomy,'latency_ms':snapshot.market.roundtrip_ms,'performance_monitor':drift,
                   'data_stale':not -250<=now-snapshot.market.tick_ms<=2000,'cashflow_changed':cashflow_changed,
                   'active_risk_policy':asdict(execution.policy),'adaptive_exit':store.get('adaptive_exit_status',{})}
        dashboard['automatic_sizing']=automatic_sizing
        dashboard['profit_reinvestment']=reinvestment
        dashboard['carry_decision']=carry_status
        dashboard['account_risk_guard']=account_risk_guard
        states={'dashboard':dashboard,'stage':asdict(stage),'performance':performance,'cashflow_reference':cashflow_reference}
        if self.config.get('news_file'):
            states['scheduled_calendar']=NewsGate(self.config['news_file']).inspect(now)
        phase_ms['total_before_publish']=round((time.perf_counter()-phase_start)*1000,3)
        dashboard['cycle_timing_ms']=phase_ms
        for frame,bars in frames.items():states['candles:'+frame]={'bars':bars,'observed_ms':now,'source':'broker-demo'}
        store.transaction('market_decision',{'action':dashboard['decision']['action'],'reasons':dashboard['decision']['reasons'],'observed_ms':now,
                                            'analysis':analysis,'calendar':calendar_effect,'snapshot':asdict(snapshot)},states=states)
        self.financial_cycle(store,broker,snapshot,positions,now)
        self.research_cycle(store,broker,now)
        self.backup_cycle(store,now)
        alerts=Alerts(store)
        alerts.condition('broker_connection',False,'critical','اختلال ارتباط بروکر','',now)
        alerts.condition('account_risk',breached,'critical','محافظ ریسک فعال شد','سفارش جدید مسدود است؛ وضعیت سرمایه و معاملات باز را بررسی کن.',now)
        alerts.condition('profit_target',target_reached,'info','هدف روزانه حاصل شد',
                         'سفارش جدید متوقف شده است؛ معاملات باز جدا مدیریت می‌شوند.' if execution.policy.daily_profit_target_halts else
                         'هدف ثبت شد؛ ادامهٔ سفارش فقط با عبور از همهٔ شرایط و حدود ریسک ممکن است.',now)
        alerts.condition('news_coverage',not snapshot.market.news_clear,'warning','محدودیت خبر','پوشش خبر تأیید نشده یا زمان خبر پراثر است؛ سفارش جدید مسدود می‌شود.',now)
        alerts.condition('capital_for_trade',capital_block is not None,'warning','سرمایه یا حجم مجاز کافی نیست','برای این موقعیت، سرمایهٔ قابل‌استفاده یا حجم مجاز کافی نیست؛ سفارشی ارسال نشد. محدودیت ریسک تغییر نکرد.',now)
        alerts.condition('quote_stale',dashboard['data_stale'],'warning','قیمت کهنه است','برای تصمیم معاملاتی، قیمت تازه در دسترس نیست.',now)
        alerts.condition('cashflow',cashflow_changed,'critical','تغییر سرمایه حساب','مبنای سرمایه به بررسی مالک نیاز دارد.',now)
        alerts.condition('unknown_order',bool(store.unresolved()),'critical','نتیجه سفارش نامعلوم است','پیش از سفارش جدید، وضعیت با بروکر تطبیق داده شود.',now)
        if self.stop.is_set():
            execution.pause_new_orders('Owner server shutdown requested');return
        cmd=self.auth.claim()
        if cmd:
            command_now=cycle_started_ms+max(0,int((time.monotonic()-collected)*1000))
            try:result=self.command(cmd,execution,store,broker,command_now);self.auth.complete(cmd['id'],'DONE',result)
            except Exception as error:self.auth.complete(cmd['id'],'FAILED',{'type':type(error).__name__,'reason':str(error)[:200]})
        elif approved and not reasons:
            candidate=proposal
            if candidate:
                price=snapshot.market.ask if candidate['side']=='buy' else snapshot.market.bid
                sizing=automatic_sizing['order']
                request_id=f"auto-{candidate['signal_time']}-{approval['strategy_sha256'][:16]}"
                if sizing and not store.intent(request_id):
                    intent=Intent(request_id,self.config['symbol'],candidate['side'],sizing['volume'],sizing['stop_loss'],price,now,
                                  'Owner-approved DEMO price candidate; research reports independent',
                                  ('closed-M15-break','higher-timeframe-alignment',version()),
                                  '0','0','0',0)
                    execution.execute(intent,now)

    def run(self):
        store=Store(self.config['database']);broker=None;execution=None;connection=None
        owns_lock=False
        try:
            with exclusive(self.config['database']+'.worker.lock'):
                owns_lock=True
                from .worker_lifecycle import fingerprint
                import os
                worker_code=self.config.get('_worker_code',fingerprint())
                if self.config.get('_continuation_token'):
                    from .continuation import restore
                    restore(self,store,self.config['_continuation_token'])
                self.auth.recover()
                from .rolling_worker import migrate_mandate
                migrate_mandate(store,self.config)
                store.transaction('worker_start',{'demo_only':True},states={'paused':True})
                from .model import configured_policy
                store.transaction('active_account_risk_policy',{},states={'active_risk_policy':asdict(configured_policy(self.config))})
                store.transaction('observation_mode',{},states={'observation_only':self.config.get('observe_only',False)})
                if self.config.get('manual_protection_capable') is True:
                    store.transaction('manual_protection_capability_installed',{},states={'manual_protection_capability_installed':True})
                store.transaction('backup_requirement',{},states={'backup_required':bool(self.config.get('_config_path') and self.config.get('backup_enabled',True))})
                if not self.injected:
                    import secrets
                    connection=BrokerConnection(self.config,store,self.stop,jitter=lambda:secrets.randbelow(1000))
                else:
                    broker=self.injected;execution=Execution(store,broker,policy=configured_policy(self.config))
                    execution.reconcile(int(time.time()*1000))
                while not self.stop.is_set():
                    now=int(time.time()*1000)
                    from .demo_autonomy import expire_due
                    expire_due(store,now)
                    store.transaction('worker_heartbeat',{},states={'worker_heartbeat':{'pid':os.getpid(),'code':worker_code,'observed_ms':now}})
                    try:
                        self.independent_sources(store,now)
                        # Source synthesis can take seconds. Do not carry its
                        # starting clock into a new broker observation.
                        now=int(time.time()*1000)
                        if connection:
                            broker=connection.step(now);execution=connection.execution
                            if broker is None:
                                self.stop.wait(1);continue
                        if not store.get('account_profile') and self.config.get('account_profile_id'):
                            selected=selection(self.config['account_profile_id'],self.config['account_identity'],now,'owner-declared-during-setup')
                            store.transaction('account_profile_initialized',{'profile_id':selected['profile_id']},states={'account_profile':selected,'demo_strategy_approval':None})
                        now=int(time.time()*1000)
                        self.cycle(store,broker,execution,now)
                        self.continuation_cycle(store)
                    except Exception as error:
                        if execution:execution.reconciled=False
                        store.transaction('monitor_fault',{'type':type(error).__name__},states={
                            'paused':True,'dashboard':{'connected':False,'observed_ms':now,'execution_mode':'demo-only','reason':type(error).__name__}})
                        if connection:connection.lost(now,type(error).__name__)
                        Alerts(store).condition('broker_connection',True,'critical','اختلال ارتباط یا داده','سفارش جدید متوقف شد؛ اتصال و وضعیت حساب باید تطبیق داده شوند.',now)
                    # A three-second idle exceeds the two-second quote guard.
                    # Poll more often; never relax freshness to mask stale reads.
                    self.stop.wait(.5)
                if self.continuation_pending():
                    from .continuation import publish,request_path
                    publish(self,store,request_path(self).read_text().strip(),final=True)
                store.transaction('worker_drained_for_upgrade',{'unresolved_orders':len(store.unresolved()),
                    'positions_preserved':True,'orders_closed_for_upgrade':0})
        except Exception as error:
            if owns_lock:store.transaction('worker_unavailable',{'type':type(error).__name__},states={'paused':True,'dashboard':{'connected':False,'reason':type(error).__name__,'observed_ms':int(time.time()*1000)},'broker_connection':{'state':'failed','verified':False,'observed_ms':int(time.time()*1000)}})
        finally:
            if self.clock_process is not None:
                self.clock_process.join(timeout=3)
                if self.clock_process.is_alive():self.clock_process.terminate();self.clock_process.join(timeout=3)
            if self.backup_process and self.backup_process.poll() is None:
                self.backup_process.terminate();self.backup_process.wait(timeout=5)
            if self.iran_process and self.iran_process.poll() is None:
                self.iran_process.terminate();self.iran_process.wait(timeout=5)
            if self.source_process and self.source_process.poll() is None:
                self.source_process.terminate();self.source_process.wait(timeout=5)
            if self.research_process and self.research_process.poll() is None:
                self.research_process.terminate();self.research_process.wait(timeout=5)
            if connection:connection.close()
            elif broker and hasattr(broker,'shutdown'):broker.shutdown()
            store.close()


def run_worker_process(config,stop):
    auth=Auth(config['auth_database'],config['totp_secret'],config['pairing_hash'],config['pairing_expires'])
    worker=Worker(config,auth)
    worker.stop=stop
    worker.run()


def service_configuration(config,observe_only):
    config=dict(config)
    config['observe_only']=observe_only
    if observe_only:config['broker_routes']=[]
    # Encrypted local backups are not broker actions; preserve the owner's
    # backup setting while observation mode continues to prohibit orders.
    return config


def serve(config_path,observe_only=False,manual_protection_capable=False,managed_updates=False):
    if managed_updates:
        from .rolling_worker import serve_managed
        return serve_managed(config_path,observe_only,manual_protection_capable)
    import multiprocessing
    import uvicorn
    from .api import create_app
    config=service_configuration(json.loads(Path(config_path).read_text()),observe_only)
    config['manual_protection_capable']=manual_protection_capable is True
    config['_config_path']=str(Path(config_path).resolve())
    auth=Auth(config['auth_database'],config['totp_secret'],config['pairing_hash'],config['pairing_expires'])
    from .worker_lifecycle import ChildJob,fingerprint,ready
    config['_worker_code']=fingerprint()
    # The Windows MT5 extension can hold the GIL while loading broker history.
    # Isolate it so the owner API and TLS handshake remain responsive.
    context=multiprocessing.get_context('spawn')
    stop=context.Event()
    worker=context.Process(target=run_worker_process,args=(config,stop),name='amin-mt5-worker')
    job=ChildJob()
    worker.start()
    try:
        job.assign(worker.pid)
    except Exception:
        worker.terminate();worker.join(timeout=5);job.close();raise
    def worker_health():
        if not worker.is_alive() or config['_worker_code']!=fingerprint():return False
        store=Store(config['database'],read_only=True)
        try:return ready(store.get('worker_heartbeat'),worker.pid,config['_worker_code'],int(time.time()*1000))
        finally:store.close()
    app=create_app(config['database'],auth,observation_only=observe_only,worker_health=worker_health,
                   manual_protection_capable=manual_protection_capable)
    try:uvicorn.run(app,host=config['bind'],port=config['port'],
                    ssl_certfile=config['tls_cert'],ssl_keyfile=config['tls_key'],proxy_headers=False,access_log=False)
    finally:
        stop.set();worker.join(timeout=10)
        if worker.is_alive():worker.terminate();worker.join(timeout=5)
        job.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('config');p.add_argument('--observe-only',action='store_true');p.add_argument('--manual-protection-capable',action='store_true');p.add_argument('--managed-updates',action='store_true');a=p.parse_args();serve(a.config,a.observe_only,a.manual_protection_capable,a.managed_updates)
