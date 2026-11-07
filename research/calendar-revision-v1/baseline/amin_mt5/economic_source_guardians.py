"""Per-source report diagnostics; no trading, credentials or private provenance."""
def assess(scope,expected,rows,prior,now_ms):
    indexed={str(r.get('id')):r for r in rows if isinstance(r,dict)};result=[]
    old={r['id']:r for r in prior if isinstance(r,dict) and 'id' in r and r.get('scope')==scope}
    for identity in expected:
        row=indexed.get(identity,{});previous=old.get(identity,{})
        status=str(row.get('status','missing'))
        failed=row.get('last_attempt_status')=='unavailable' or status in ('missing','unavailable','error','not_connected')
        error=row.get('last_attempt_error_type') or row.get('error_type') or row.get('error')
        received=row.get('received_ms') or row.get('checked_ms')
        if type(received) is not int or received>now_ms:received=None
        cached=row.get('cached') is True
        success=not failed and received is not None and (status.startswith('available') or status=='usable_supplemental')
        attempt=row.get('last_attempt_ms') or row.get('checked_ms') or row.get('received_ms')
        if type(attempt) is not int or attempt>now_ms:attempt=None
        changed=attempt is not None and attempt!=previous.get('last_attempt_ms')
        failures=(previous.get('consecutive_failures',0)+1 if changed else previous.get('consecutive_failures',0)) if failed else 0
        last_success=received if success else previous.get('last_success_ms')
        reason=('SOURCE_NOT_OBSERVED' if not row else 'FETCH_FAILED_CACHED_DATA_RETAINED' if failed and cached
            else 'FETCH_FAILED' if failed else 'SOURCE_RESPONSE_OBSERVED' if success else 'RESPONSE_NOT_VALIDATED')
        result.append({'id':identity,'scope':scope,'status':status,'reason':reason,
            'error_type':str(error)[:80] if error else None,'last_attempt_ms':attempt,
            'last_success_ms':last_success,'consecutive_failures':failures,'cached':cached,
            'receipt_age_ms':now_ms-received if received is not None else None,
            'data_period':row.get('data_period'),'statistical_period_current':False,
            'next_attempt_ms':now_ms+min(3600000,600000*2**min(failures,2)),
            'market_closure_inferred':False,'can_authorize_orders':False})
    return result
