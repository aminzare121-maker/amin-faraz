"""V13 optional-model evidence bridge.

Safely combines output *already generated* by independent models with original
SHA-anchored V12 evidence. No model inference, media edits, or trading decisions.
"""
from __future__ import annotations
from copy import deepcopy
import re

HEX = re.compile(r'^[0-9a-f]{64}$')
TOOL_KINDS = {
    'whisperx': {'audio'},
    'paddleocr': {'chat', 'board'},
    'qwen3-vl': {'chat', 'board', 'video_frame'},
    'videorag': {'audio', 'chat', 'board', 'video_frame'},
}


def _sha(value):
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def merge_evidence(source_sha256, originals, reports):
    """Fail closed on origin/time mismatch; never certify semantic correctness.

    originals: [{'id':str,'kind':str,'sha256':hex64,'start':float,'end':float}]
    reports: [{'tool':str,'source_sha256':hex64,
               'items':[{'id':str,'original_sha256':hex64,
                         'start':number,'end':number,'content':str}]}]
    """
    if not _sha(source_sha256) or not isinstance(originals, list) or not originals:
        raise ValueError('Original source SHA and evidence required')
    if not isinstance(reports, list):
        raise ValueError('Optional-model reports must be a list')
    anchors = {}
    for node in originals:
        if not isinstance(node, dict):
            raise ValueError('Malformed original evidence')
        ident, sha, kind = node.get('id'), node.get('sha256'), node.get('kind')
        if not isinstance(ident, str) or not ident or ident in anchors or not _sha(sha):
            raise ValueError('Missing/duplicate original evidence identifier or SHA')
        if kind not in {'audio', 'chat', 'board', 'video_frame'}:
            raise ValueError('Unknown original evidence kind')
        a,b = node.get('start'), node.get('end')
        if type(a) not in (float,int) or type(b) not in (float,int) or not 0 <= a <= b:
            raise ValueError('Original evidence timestamp invalid')
        anchors[ident] = node
    by_id = {ident: [] for ident in anchors}
    seen = set()
    used = []
    for report in reports:
        if not isinstance(report, dict):
            raise ValueError('Malformed optional-model report')
        tool = report.get('tool')
        if tool not in TOOL_KINDS:
            raise ValueError('Unapproved model adapter')
        if report.get('source_sha256') != source_sha256:
            raise ValueError('Model output belongs to another movie')
        if tool in used:
            raise ValueError('Duplicate model report')
        used.append(tool)
        items = report.get('items')
        if not isinstance(items, list):
            raise ValueError('Model evidence items absent')
        for item in items:
            if not isinstance(item, dict):
                raise ValueError('Malformed model evidence item')
            ident = item.get('id')
            if ident not in anchors or (tool, ident) in seen:
                raise ValueError('Missing/duplicate referenced original evidence')
            seen.add((tool,ident))
            anchor = anchors[ident]
            if anchor['kind'] not in TOOL_KINDS[tool] or item.get('original_sha256') != anchor['sha256']:
                raise ValueError('Original evidence kind or SHA mismatch')
            a,b = item.get('start'), item.get('end')
            if type(a) not in (int,float) or type(b) not in (int,float) or a < anchor['start']-.001 or b > anchor['end']+.001 or a > b:
                raise ValueError('Model evidence outside original timestamp')
            content = item.get('content')
            if not isinstance(content,str) or not content.strip():
                raise ValueError('Empty model evidence content')
            if any(k in item for k in ('execute_trade','trading_allowed','verified_teacher_rule','human_verified')):
                raise ValueError('Model cannot self-authorize teacher meaning or trading')
            by_id[ident].append({'tool':tool,'content_candidate':content,
                                 'start':a,'end':b,'human_verified':False,
                                 'teacher_rule_verified':False})
    output = []
    for node in originals:
        result = deepcopy(node)
        result['supplementary_candidates'] = by_id[node['id']]
        result['original_preserved'] = True
        output.append(result)
    return {'schema':'video001_v13_optional_evidence_bridge_v1',
            'source_video_sha256':source_sha256,
            'original_evidence_count':len(originals),
            'merged_original_evidence_count':len(output),
            'optional_tools_reported':used,
            'tools_not_run':[t for t in TOOL_KINDS if t not in used],
            'teacher_semantic_accuracy_verified':False,
            'verified_teacher_rules':0,'trading_allowed':False,
            'source_movie_modified':False,'evidence':output}
