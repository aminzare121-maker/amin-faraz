# Archive API and limits

Only standard Python modules are used. This component has no broker connection,
account login, order API, background task or ability to approve a trade.

```python
from candle_archive import CandleArchive, verify_archive
archive = CandleArchive(private_runtime_directory)
result = archive.ingest(
    closed_rates_as_dicts,
    current_bar_open=bar_zero_native_integer_time,
    symbol="XAUUSD.st",
    timeframe="M15",
)
report = verify_archive(private_runtime_directory, expected_head=prior_external_pin)
```

Each bar requires `time, open, high, low, close, tick_volume, spread, real_volume`.
Native broker timestamps remain integers; no local/UTC conversion is performed.
`current_bar_open` must be the native time of broker bar zero, not a guessed local
clock. A row at or after that time is rejected. A historical row must be a full
M15 interval earlier and share its opening grid. Numbers are canonical decimal
strings in the archive. Incoming numpy integer scalars are accepted.

`ingest` validates the complete batch before appending. Conflicting duplicates or
invalid bars reject the batch without adding its other bars. Identical duplicates
are counted but not stored again. Unordered input is reported and sorted within
the batch. Earlier missing bars can be backfilled even after later timestamps
were archived: the hash chain records arrival order, while `read_bars()` returns
timestamp order. `latest_time()` supplies the latest native timestamp for a fetch
watermark. It does **not** resolve interior gaps by itself; fetchers should revisit
`gaps` as well as overlap the watermark. A gap is `GAP_UNRESOLVED`, never implicitly
a trading-session closure, corrupt download, teacher FVG or fabricated candle.

The result provides `added`, `duplicates`, `backfilled`, `out_of_order_input`,
`recovered_transaction`, `head`, `gaps` and `timings_seconds`. Timings divide
validation, incremental processing, storage and final verification; `total` also
includes lock acquisition, existing archive verification and recovery. Receiving
data is outside this API and must be measured by the collector separately.
Full integrity scans intentionally revisit existing records; incremental candle
processing means that old bars are not appended or reprocessed into new records.

## Durable state

- `candles.jsonl`: canonical append-only records with index, previous SHA256,
  native bar, symbol/timeframe and current SHA256.
- `checkpoint.json` and `anchor.json`: separately written committed count/head.
- `pending.json`: fsynced intent containing the prior head, exact append bytes,
  prefix length/hash and intended new head. Removed only after both head records
  are durable.
- `writer.lock`: OS advisory lock; released automatically after process death.

An interrupted append is recovered only when existing bytes match the exact
prefix of that saved intent. Invalid/unexpected bytes are preserved and rejected.
A stale checkpoint without matching pending intent is an integrity error, not
silently regenerated state. A fully committed but subsequently truncated tail is
detected against the separate anchor. The independent verifier never repairs or
writes anything and refuses pending transactions until writer recovery is run.
Run verification without a concurrent writer; a live transaction can correctly
return `RECOVERY_REQUIRED` rather than a consistent committed snapshot.

```powershell
python python/verify_archive.py --root PRIVATE_RUNTIME_ROOT
python -m unittest discover -s tests -v
```

The verifier exits 2 on failure and 0 on success. Keep an independently retained
head JSON and pass `--pin-file` or `expected_head` to detect coordinated rollback
of archive **and** both local head files. Hashes are not signatures. If an attacker
rewrites all local records, heads, transaction intent and every independent pin,
this design cannot prove the original history. Empty-directory initialization
interrupted before its three components are created fails closed; it does not
delete partial evidence automatically. The archive is not encrypted and should
remain private. This is integrity checking, not a credential store.

## Thirteen structural paths

`path_registry.PATHS` contains exactly PATH01–PATH13. Names and mappings are
deliberately unset because no validated 13-path teaching specification is
installed. Each slot retains speech/image evidence containers and is
`UNVERIFIED_UNMAPPED`. `evaluate_path` always returns `NEEDS_EVIDENCE` and disables
orders. These are structural slots, not thirteen implemented or verified
strategies. Evidence must preserve source/session IDs, timestamps and media hashes;
mere presence of a transcript or successful unit test does not verify teaching.
