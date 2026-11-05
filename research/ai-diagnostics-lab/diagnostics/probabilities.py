"""Inference-only diagnostics of frozen artifacts; no training or selection.

Public output contains aggregates and hashes, never weights, feature vectors,
quotes, individual scores or trade rows.  Returned score_maps are private work
products for the caller. T/C use original usable label rows and are in-sample
diagnostics; V/E are already-seen historical development, not future tests.
"""

import hashlib
import json
import math
from collections import Counter
from statistics import mean, pstdev

from faraz_lab.learning import (
    THRESHOLD, predict_calibrated, predict_logistic, predict_tree,
)
from faraz_lab.runner import window_rows
from faraz_lab.statistics import probability_metrics


TARGETS = ('M1_raw', 'M1_cal', 'M2_raw', 'M2_cal', 'BASE_C')
MODEL_TARGETS = TARGETS[:4]
PHASE_NAMES = {'T': 'train', 'C': 'calibration', 'V': 'validation', 'E': 'evaluation'}


def _digest(value):
    if value is None:
        return None
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _quantile(ordered, fraction):
    position = (len(ordered) - 1) * fraction
    low = int(math.floor(position))
    high = int(math.ceil(position))
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _distribution(values):
    """Population SD and fixed linear quantiles, before probability clipping."""
    ordered = sorted(values)
    counts = [0] * 5
    for value in ordered:
        counts[min(4, int(value * 5))] += 1
    histogram = [
        {'bin': index, 'lower_inclusive': index / 5,
         'upper': (index + 1) / 5, 'upper_inclusive': index == 4, 'n': count}
        for index, count in enumerate(counts)
    ]
    result = {'n': len(ordered), 'min': None, 'p05': None, 'p25': None,
              'median': None, 'p75': None, 'p95': None, 'max': None,
              'mean': None, 'sd': None, 'histogram': histogram,
              'sd_definition': 'population', 'quantile_method': 'linear-(n-1)*q'}
    if ordered:
        result.update(min=ordered[0], p05=_quantile(ordered, .05),
                      p25=_quantile(ordered, .25), median=_quantile(ordered, .5),
                      p75=_quantile(ordered, .75), p95=_quantile(ordered, .95),
                      max=ordered[-1], mean=mean(ordered), sd=pstdev(ordered))
    return result


def _predict(target, artifacts, features, base_c):
    if target == 'BASE_C':
        return base_c
    arm = target[:2]
    artifact = artifacts.get(arm) or {}
    model = artifact.get('model')
    if model is None:
        return None
    predictor = predict_logistic if arm == 'M1' else predict_tree
    raw = predictor(model, features)
    if target.endswith('_raw'):
        return raw
    calibration = artifact.get('calibration')
    if calibration is None:
        return None
    return predict_calibrated(calibration, raw)


def _checked_predict(target, artifacts, features, base_c):
    try:
        value = _predict(target, artifacts, features, base_c)
        if value is None:
            return None, 'artifact_or_base_rate_unavailable'
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not math.isfinite(value) or not 0 <= value <= 1):
            return None, 'invalid_probability'
        return float(value), None
    except (ValueError, TypeError, KeyError, ArithmeticError, AttributeError) as error:
        # Type names only: error messages can contain private model/input data.
        return None, type(error).__name__


def _histogram_drift(reference, target):
    n_reference, n_target = reference['n'], target['n']
    if not n_reference or not n_target:
        return {'total_variation': None, 'jensen_shannon_nats': None,
                'reference_score_n': n_reference, 'target_score_n': n_target}
    p = [item['n'] / n_reference for item in reference['histogram']]
    q = [item['n'] / n_target for item in target['histogram']]
    midpoint = [(a + b) / 2 for a, b in zip(p, q)]
    divergence = .5 * sum(a * math.log(a / m) if a else 0.0
                           for a, m in zip(p, midpoint))
    divergence += .5 * sum(b * math.log(b / m) if b else 0.0
                            for b, m in zip(q, midpoint))
    return {'total_variation': .5 * sum(abs(a - b) for a, b in zip(p, q)),
            'jensen_shannon_nats': divergence,
            'reference_score_n': n_reference, 'target_score_n': n_target}


def diagnose_fold(fold, signals, events, bars, artifacts, scenario, policy):
    """Return public aggregates, private E score maps, and past-C activity rates.

    No dictionary supplied by the caller is mutated. A missing model/calibrator
    produces None scores, never a rules or base-rate fallback. q_past is None
    unless every original usable C row has an available score for that target;
    an observed fraction zero remains the distinct, valid activity budget0.
    """
    embargo = policy.max_holding_seconds + (scenario.latency_bars + 1) * 900
    phases = {}
    phase_samples = {}
    for phase in ('T', 'C', 'V'):
        start, end = fold[PHASE_NAMES[phase]]
        rows, original_counts = window_rows(events, signals, start, end, embargo)
        indices = [row['index'] for row in rows]
        labels = {row['index']: row['label'] for row in rows}
        all_indices = [index for index in signals if start <= bars[index].time + 900 < end]
        missing_events = sum(events.get(index) is None for index in all_indices)
        phases[phase] = {'indices': indices, 'labels': labels}
        phase_samples[phase] = {
            'window_start_inclusive': start, 'window_end_exclusive': end,
            'label_cutoff_exclusive': end - embargo, 'embargo_seconds': embargo,
            'candidate_signals_in_window': len(all_indices),
            'candidate_events_missing_in_window': missing_events,
            'scoring_universe_count': len(indices), 'available_label_count': len(labels),
            'positive_labels': sum(labels.values()),
            'label_prevalence': sum(labels.values()) / len(labels) if labels else None,
            'scoring_universe': 'original-usable-label-rows-after-boundary-purge',
            'in_sample_diagnostics_only': phase in ('T', 'C'),
            'historical_development_not_independent_test': phase == 'V',
            'original_window_counts': dict(original_counts),
            'original_global_unavailable_events_scope': 'all-signals-not-this-window',
        }
    start, end = fold['evaluation']
    eval_indices = [index for index in signals if start <= bars[index].time + 900 < end]
    eval_labels = {
        index: int(events[index]['net_per_lot'] > 0)
        for index in eval_indices if events.get(index) is not None
    }
    phases['E'] = {'indices': eval_indices, 'labels': eval_labels}
    phase_samples['E'] = {
        'window_start_inclusive': start, 'window_end_exclusive': end,
        'label_cutoff_exclusive': None, 'embargo_seconds': None,
        'candidate_signals_in_window': len(eval_indices),
        'candidate_events_missing_in_window': len(eval_indices) - len(eval_labels),
        'scoring_universe_count': len(eval_indices), 'available_label_count': len(eval_labels),
        'positive_labels': sum(eval_labels.values()),
        'label_prevalence': sum(eval_labels.values()) / len(eval_labels) if eval_labels else None,
        'scoring_universe': 'all-E-candidate-signals-including-unavailable-outcomes',
        'in_sample_diagnostics_only': False,
        'historical_development_not_independent_test': True,
        'later_settlements_allowed_for_probability_diagnostics': True,
        'future_labels_used_for_scoring_or_selection': False,
    }
    c_labels = phases['C']['labels']
    c_positive = sum(c_labels.values())
    base_c = c_positive / len(c_labels) if c_labels else None
    public_artifacts = {}
    for arm in ('M1', 'M2'):
        artifact = artifacts.get(arm) or {}
        model, calibration = artifact.get('model'), artifact.get('calibration')
        public_artifacts[arm] = {
            'model_present': model is not None, 'calibration_present': calibration is not None,
            'model_sha256': _digest(model), 'calibration_sha256': _digest(calibration),
            'new_fit_performed': False,
        }

    records = []
    record_lookup = {}
    private_scores = {target: {} for target in TARGETS}
    q_past = {}
    for target in TARGETS:
        for phase in ('T', 'C', 'V', 'E'):
            indices = phases[phase]['indices']
            labels = phases[phase]['labels']
            score_map = {}
            errors = Counter()
            for index in indices:
                probability, reason = _checked_predict(target, artifacts, signals[index].features, base_c)
                score_map[index] = probability
                if reason:
                    errors[reason] += 1
            available_scores = [score_map[index] for index in indices if score_map[index] is not None]
            labeled_indices = [index for index in indices if index in labels and score_map[index] is not None]
            metric = probability_metrics([score_map[index] for index in labeled_indices],
                                         [labels[index] for index in labeled_indices])
            gate_count = sum(value >= THRESHOLD for value in available_scores)
            row = {
                'fold': fold['name'], 'phase': phase, 'target': target,
                'status': ('available' if len(available_scores) == len(indices) and indices else
                           'partial' if available_scores else 'unavailable'),
                'threshold': THRESHOLD,
                'gate_count': gate_count, 'gate_denominator': len(indices),
                'gate_fraction': gate_count / len(indices) if indices and not errors else None,
                'scored_candidate_count': len(available_scores),
                'unavailable_score_count': len(indices) - len(available_scores),
                'label_available_count': len(labels),
                'missing_label_count': len(indices) - len(labels),
                'scored_labeled_count': len(labeled_indices),
                'positive_labels': sum(labels.values()),
                'label_prevalence': sum(labels.values()) / len(labels) if labels else None,
                'probability_metrics': metric,
                'score_distribution': _distribution(available_scores),
                'score_unavailability_reasons': dict(sorted(errors.items())),
                'in_sample_diagnostics_only': phase in ('T', 'C'),
                'historical_development_not_independent_test': phase in ('V', 'E'),
                'calibrator_applied': target.endswith('_cal'),
                'empirical_base_rate_only': target == 'BASE_C',
            }
            records.append(row)
            record_lookup[(target, phase)] = row
            if phase == 'C' and target in MODEL_TARGETS:
                q_past[target] = gate_count / len(indices) if indices and not errors else None
            if phase == 'E':
                private_scores[target] = score_map

    drift = {}
    for target in TARGETS:
        reference = record_lookup[(target, 'C')]
        comparisons = {}
        for phase in ('V', 'E'):
            current = record_lookup[(target, phase)]
            reference_rate, current_rate = reference['label_prevalence'], current['label_prevalence']
            comparison = _histogram_drift(reference['score_distribution'], current['score_distribution'])
            comparison.update(
                prevalence_difference=(current_rate - reference_rate
                                       if current_rate is not None and reference_rate is not None else None),
                reference_label_prevalence=reference_rate, target_label_prevalence=current_rate,
                reference_label_n=reference['label_available_count'], target_label_n=current['label_available_count'],
                score_denominator_note=('C/V use original usable label rows; E score histogram uses '
                                        'all candidates and prevalence uses available outcomes only'),
                descriptive_only=True, significance_established=False, cause_established=False,
                formal_label_or_market_drift_established=False,
            )
            comparisons['C_to_' + phase] = comparison
        drift[target] = comparisons
    public = {
        'schema': 1, 'fold': fold['name'], 'threshold': THRESHOLD,
        'phase_samples': phase_samples, 'artifacts': public_artifacts,
        'base_c': {'source_phase': 'C', 'positive_labels': c_positive,
                   'usable_labels': len(c_labels), 'probability': base_c,
                   'smoothing': False, 'fitted': False, 'V_or_E_used': False},
        'records': records, 'drift': drift, 'q_past': dict(q_past),
        'q_past_basis': 'score>=.55 fraction on original usable C rows only',
        'new_fit_performed': False, 'model_or_threshold_selection_performed': False,
        'raw_scores_or_weights_public': False,
        'limitations': [
            'Retrospective fixed simulation, not independent future validation.',
            'Tfit and Ccal metrics are in-sample diagnostics only.',
            'Small and potentially dependent event samples do not prove a drift or failure cause.',
            'Probability metrics exclude unavailable outcomes; E gates include all candidate scores.',
            'Data provenance, session validity, Bid/Ask and execution assumptions remain unverified.',
        ],
    }
    return public, private_scores, q_past
