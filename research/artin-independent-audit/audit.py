"""Evidence audit only. No strategy, price feed, execution engine or Faraz import."""
def assess(rule):
    missing=[]
    for field in ('source_sha256','visual_confirmation','audio_confirmation','entry_definition','stop_definition','volume_definition','causal_confirmation_time'):
        if not rule.get(field):missing.append(field)
    if rule.get('conflicts'):missing.append('unresolved_conflicts')
    sha=rule.get('source_sha256')
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):missing.append('source_hash_invalid')
    for field in ('visual_confirmation','audio_confirmation'):
        if rule.get(field) is not True:missing.append(field+'_unverified')
    for field in ('entry_definition','stop_definition','volume_definition'):
        if not isinstance(rule.get(field),str) or not rule[field].strip():missing.append(field+'_invalid')
    t=rule.get('causal_confirmation_time')
    if type(t) is not int or t<0:missing.append('confirmation_time_invalid')
    # Even a fully described rule is not evidence of market efficacy or authority.
    return dict(extractable_for_review=not missing,missing=missing,trade_authority=False,market_efficacy='NOT_ESTABLISHED',engine_created=False)
