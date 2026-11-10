#!/usr/bin/env python3
"""Offline local-artifact consistency check for the MetaEditor compile-only receipt.

This cannot authenticate the publisher of a Windows executable or prove its
execution, MT5 connection, teacher fidelity, or the absence of trading in MT5.
It checks only exact source/EX5/log hashes against the supplied receipt.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

SOURCE_SHA = '66f65c92275999e41835a1c414263cf7c5dd0ef4ea219dbef0e96b030bdcd361'
SOURCE_NAME = 'ArtinV13_ShadowProbe_RecoveryV2_DemoOnly.mq5'
LOG_NAME = 'ArtinV13_ShadowProbe_RecoveryV2_DemoOnly.log'
EX5_NAME = 'ArtinV13_ShadowProbe_RecoveryV2_DemoOnly.ex5'


def check_receipt(receipt: dict, source: bytes, log: bytes, ex5: bytes) -> dict:
    reasons = []
    if not isinstance(receipt, dict):
        return {'passed': False, 'reasons': ['INVALID_RECEIPT']}
    if receipt.get('schema') != 'artin_mt5_metaeditor_compile_receipt_v3':
        reasons.append('WRONG_SCHEMA')
    if receipt.get('status') != 'COMPILE_CONFIRMED_LOCAL_METAEDITOR_ONLY':
        reasons.append('COMPILE_NOT_CONFIRMED_BY_RECEIPT')
    if receipt.get('source_sha256_verified') is not True:
        reasons.append('SOURCE_UNVERIFIED')
    sha=lambda b: hashlib.sha256(b).hexdigest()
    if sha(source) != SOURCE_SHA or receipt.get('source_sha256_expected') != SOURCE_SHA:
        reasons.append('SOURCE_MISMATCH')
    if not ex5 or receipt.get('ex5_sha256') != sha(ex5):
        reasons.append('EX5_MISSING_OR_HASH_MISMATCH')
    if not log or receipt.get('log_sha256') != sha(log):
        reasons.append('COMPILER_LOG_MISSING_OR_HASH_MISMATCH')
    decoded=log.decode('utf-16',errors='replace') if log.startswith((b'\xff\xfe',b'\xfe\xff')) else log.decode('utf-8-sig',errors='replace')
    if not re.search(r'(?im)(?<!\d)0\s+errors?\b',decoded):
        reasons.append('ZERO_ERROR_LINE_MISSING')
    if re.search(r'(?im)(?<!\d)[1-9]\d*\s+errors?\b',decoded):
        reasons.append('COMPILER_ERRORS_REPORTED')
    if receipt.get('log_reports_zero_errors') is not True or receipt.get('log_reports_errors') is not False:
        reasons.append('RECEIPT_LOG_STATUS_MISMATCH')
    if receipt.get('demo_runtime_tested') is not False or receipt.get('mt5_orders_sent') != 0 or receipt.get('teacher_semantics_certified') is not False:
        reasons.append('UNJUSTIFIED_RUNTIME_OR_SEMANTIC_CLAIM')
    return {'passed': not reasons, 'reasons': reasons,
            'scope': 'FILES_MATCH_COMPILE_ONLY_RECEIPT_NOT_PROOF_OF_ACTUAL_MT5_RUNTIME',
            'mt5_demo_runtime_tested': False, 'teacher_semantics_certified': False,
            'orders_authorized': 0}


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument('receipt',type=Path)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--log',type=Path,required=True)
    p.add_argument('--ex5',type=Path,required=True)
    a=p.parse_args()
    receipt=json.loads(a.receipt.read_text(encoding='utf-8-sig'))
    r=check_receipt(receipt,a.source.read_bytes(),a.log.read_bytes(),a.ex5.read_bytes())
    print(json.dumps(r,ensure_ascii=False,indent=2))
    raise SystemExit(0 if r['passed'] else 1)

if __name__ == '__main__': main()