"""Transparent public calendar identity and bounded failure backoff."""
from email.utils import parsedate_to_datetime

USER_AGENT = 'Amin-MT5-Calendar/1.0 (public weekly calendar reader)'


def failure(code, body, retry_after, now):
    reason = ('CALENDAR_CLIENT_SIGNATURE_REJECTED' if code == 403 and '1010' in body
              else 'CALENDAR_RATE_LIMITED' if code == 429
              else 'CALENDAR_HTTP_ACCESS_DENIED' if code == 403
              else 'CALENDAR_TRANSPORT_UNAVAILABLE')
    wait = 3600000
    if retry_after:
        try:
            delay = int(retry_after)*1000
        except (ValueError, TypeError):
            try: delay = int(parsedate_to_datetime(retry_after).timestamp()*1000)-now
            except (ValueError, TypeError, OverflowError): delay = 0
        wait = max(wait, delay)
    return {'reason_code':reason,'retry_not_before_ms':now+wait,
            'market_closed_inferred':False,'bypass_attempted':False}
