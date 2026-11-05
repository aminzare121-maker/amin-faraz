"""Deterministic offline models, explicit failure, JSON-only artifacts.

fit(rows) preserves the frozen stdlib logistic-l2-v1 arithmetic.  Each row is
{'learning_features': seven finite numbers, 'net': numeric net outcome,
 'time': actual exit Unix seconds}.  fit_logistic(X, y) has no exit timestamps;
its returned training_latest_exit is therefore None, never a fabricated time.
Unlike the engine's rules arm, predict_logistic(None, x) always raises.

Tree: depth <=2, min leaf20, binary Gini splits, Laplace leaf probability.
Calibrator: Platt sigmoid on logit(clipped p), fixed L2=0.05, Newton optimizer
with at most100 steps and bounded loss-decreasing line search. Constants are
frozen before outcomes; optimizer iterations only fit the calibration sample.
There is no hyperparameter search or validation/evaluation selection.
"""

import hashlib
import json
import math


FEATURES = (
    'price_slope', 'body', 'wick_imbalance', 'range_expansion',
    'relative_tick_volume', 'location', 'side',
)
THRESHOLD = .55
SOURCE_PROVENANCE = {
    'release': '20261031T061122830201Z',
    'learning_source_sha256': '85d6392fb53b67d60a0e95c6d099d36acc944df2abd45b6f4d4c8c9ecbb0561f',
    'logistic_numeric_algorithm': 'exact-logistic-l2-v1-160-steps-lr.1-l2.05',
    'intentional_difference': 'model=None is unavailable, never a rules fallback',
    'tree': 'predeclared-independent-depth2-minleaf20-laplace-v1',
    'calibration': 'predeclared-Platt-logit-L2.05-Newton100-linesearch24-v1',
}


def sigmoid(x):
    return 1 / (1 + math.exp(-max(-30, min(30, x))))


def fit(rows):
    """Safe stdlib copy of release learning.py:12-27; net>0 is the label."""
    if len(rows) < 30:
        return None
    # Validation is the only addition to the copied numeric fitting algorithm.
    for row in rows:
        _vector(row['learning_features'])
        if (not isinstance(row['net'], (int, float)) or not math.isfinite(row['net'])
                or type(row['time']) is not int or row['time'] < 0):
            raise ValueError('Finite net outcome and nonnegative exit time required')
    x = [list(r['learning_features']) for r in rows]
    y = [float(r['net'] > 0) for r in rows]
    if min(y) == max(y):
        return None
    if any(len(row) != len(FEATURES) or any(not math.isfinite(v) for v in row) for row in x):
        raise ValueError('Invalid features')
    n = len(x)
    means = [sum(row[j] for row in x) / n for j in range(7)]
    scales = [max((sum((row[j] - means[j]) ** 2 for row in x) / n) ** .5, 1e-6) for j in range(7)]
    normalized = [[max(-6, min(6, (row[j] - means[j]) / scales[j])) for j in range(7)] for row in x]
    weights = [0.0] * 7
    bias = math.log((sum(y) + 1) / (n - sum(y) + 1))
    for _ in range(160):
        errors = [sigmoid(bias + sum(w * v for w, v in zip(weights, row))) - label
                  for row, label in zip(normalized, y)]
        bias -= .1 * sum(errors) / n
        weights = [w - .1 * (sum(error * row[j] for error, row in zip(errors, normalized)) / n + .05 * w)
                   for j, w in enumerate(weights)]
    return {
        'kind': 'logistic-l2-v1', 'features': list(FEATURES), 'means': means,
        'scales': scales, 'weights': weights, 'bias': bias, 'training_rows': n,
        'training_latest_exit': max(r['time'] for r in rows),
        'training_sha256': hashlib.sha256(json.dumps([[a, b] for a, b in zip(x, y)], sort_keys=True).encode()).hexdigest(),
    }


def _xy(X, y):
    if len(X) != len(y):
        raise ValueError('Feature and label lengths differ')
    values = [_vector(row) for row in X]
    labels = []
    for value in y:
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value not in (0, 1):
            raise ValueError('Labels must be finite binary outcomes')
        labels.append(float(value))
    return values, labels


def _vector(values):
    if len(values) != len(FEATURES):
        raise ValueError('Expected exactly seven features')
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError('Features must be finite numbers')
    return [float(v) for v in values]


def fit_logistic(X, y):
    values, labels = _xy(X, y)
    # time is not used by fitting or by training_sha256.  The temporary sentinel
    # is erased below so this API cannot claim knowledge of an actual exit time.
    model = fit([{'learning_features': row, 'net': label, 'time': 0}
                 for row, label in zip(values, labels)])
    if model is not None:
        model['training_latest_exit'] = None
        model['training_time_basis'] = 'not-provided-by-X-y-wrapper'
    return model


def predict_logistic(model, values):
    if not isinstance(model, dict):
        raise ValueError('A trained logistic artifact is required')
    if model.get('kind') != 'logistic-l2-v1' or model.get('features') != list(FEATURES):
        raise ValueError('Unrecognized model')
    values = _vector(values)
    try:
        for key in ('weights', 'means', 'scales'):
            if len(model[key]) != 7 or any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in model[key]):
                raise ValueError('Invalid model parameters')
        if any(v <= 0 for v in model['scales']) or not math.isfinite(model['bias']):
            raise ValueError('Invalid model input')
        normalized = [max(-6, min(6, (v - m) / s))
                      for v, m, s in zip(values, model['means'], model['scales'])]
        return sigmoid(model['bias'] + sum(w * v for w, v in zip(model['weights'], normalized)))
    except (KeyError, TypeError, OverflowError) as error:
        raise ValueError('Invalid model parameters') from error


def predict(model, values):
    """Compatibility name, retaining this lab's required-model behavior."""
    return predict_logistic(model, values)


def fit_tree(X, y):
    values, labels = _xy(X, y)
    if len(values) < 30 or len(set(labels)) < 2:
        return None

    def node(indices, depth):
        count = len(indices)
        positives = sum(labels[i] for i in indices)
        leaf = {'leaf': True, 'n': count, 'positives': int(positives),
                'probability': (positives + 1) / (count + 2)}
        if depth >= 2 or count < 40 or positives in (0, count):
            return leaf
        parent_impurity = 2 * positives * (count - positives) / (count * count)
        best_impurity = parent_impurity
        best = None
        for feature in range(7):
            ordered = sorted(indices, key=lambda i: (values[i][feature], i))
            left_positive = 0.0
            for position in range(count - 1):
                left_positive += labels[ordered[position]]
                left_count = position + 1
                right_count = count - left_count
                current = values[ordered[position]][feature]
                following = values[ordered[position + 1]][feature]
                if left_count < 20 or right_count < 20 or current == following:
                    continue
                right_positive = positives - left_positive
                impurity = (2 * left_positive * (left_count - left_positive) / left_count
                            + 2 * right_positive * (right_count - right_positive) / right_count) / count
                if impurity < best_impurity:
                    threshold = current / 2 + following / 2
                    # If adjacent floats round the midpoint to the upper value,
                    # use the lower observed boundary to preserve this partition.
                    if threshold >= following:
                        threshold = current
                    best_impurity = impurity
                    best = (feature, threshold, ordered[:left_count], ordered[left_count:])
        if best is None:
            return leaf
        feature, threshold, left, right = best
        return {'leaf': False, 'n': count, 'feature': feature, 'threshold': threshold,
                'left': node(left, depth + 1), 'right': node(right, depth + 1)}

    return {
        'kind': 'tiny-tree-depth2-laplace-v1', 'features': list(FEATURES),
        'max_depth': 2, 'min_leaf': 20, 'training_rows': len(values),
        'root': node(list(range(len(values))), 0),
        'training_sha256': hashlib.sha256(json.dumps([values, labels], sort_keys=True).encode()).hexdigest(),
    }


def predict_tree(model, values):
    if not isinstance(model, dict) or model.get('kind') != 'tiny-tree-depth2-laplace-v1':
        raise ValueError('A trained tree artifact is required')
    if model.get('features') != list(FEATURES) or model.get('max_depth') != 2 or model.get('min_leaf') != 20:
        raise ValueError('Unrecognized tree contract')
    values = _vector(values)
    try:
        current = model['root']
        for depth in range(3):
            if current.get('leaf') is True:
                probability = current['probability']
                if not isinstance(probability, (int, float)) or not math.isfinite(probability) or not 0 < probability < 1:
                    raise ValueError('Invalid leaf probability')
                return float(probability)
            if depth == 2 or current.get('leaf') is not False:
                raise ValueError('Invalid tree depth or node')
            feature, threshold = current['feature'], current['threshold']
            if type(feature) is not int or not 0 <= feature < 7 or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
                raise ValueError('Invalid split')
            current = current['left'] if values[feature] <= threshold else current['right']
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Invalid tree parameters') from error
    raise ValueError('Invalid tree')


def _logit(probability):
    if not isinstance(probability, (int, float)) or not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError('Probability must be finite and in [0, 1]')
    clipped = min(1 - 1e-6, max(1e-6, float(probability)))
    return math.log(clipped / (1 - clipped))


def fit_calibrator(probabilities, labels):
    if len(probabilities) != len(labels):
        raise ValueError('Calibration score and label lengths differ')
    logits = [_logit(probability) for probability in probabilities]
    if any(not isinstance(y, (int, float)) or not math.isfinite(y) or y not in (0, 1) for y in labels):
        raise ValueError('Calibration labels must be binary')
    labels = [float(y) for y in labels]
    n = len(logits)
    if n < 20 or len(set(labels)) < 2:
        return None
    slope = 0.0
    intercept = math.log((sum(labels) + 1) / (n - sum(labels) + 1))
    l2 = .05

    def objective(a, b):
        total = 0.0
        for value, label in zip(logits, labels):
            linear = b + a * value
            total += max(linear, 0) + math.log1p(math.exp(-abs(linear))) - label * linear
        return total / n + .5 * l2 * a * a

    iterations = 0
    for iteration in range(100):
        predictions = [sigmoid(intercept + slope * value) for value in logits]
        errors = [probability - label for probability, label in zip(predictions, labels)]
        variance = [probability * (1 - probability) for probability in predictions]
        gradient_a = sum(error * value for error, value in zip(errors, logits)) / n + l2 * slope
        gradient_b = sum(errors) / n
        hessian_aa = sum(weight * value * value for weight, value in zip(variance, logits)) / n + l2
        hessian_ab = sum(weight * value for weight, value in zip(variance, logits)) / n
        hessian_bb = sum(variance) / n
        determinant = hessian_aa * hessian_bb - hessian_ab * hessian_ab
        if determinant <= 0 or not math.isfinite(determinant):
            raise ValueError('Calibration Hessian is invalid')
        delta_a = (hessian_bb * gradient_a - hessian_ab * gradient_b) / determinant
        delta_b = (hessian_aa * gradient_b - hessian_ab * gradient_a) / determinant
        iterations = iteration + 1
        if max(abs(delta_a), abs(delta_b)) < 1e-10:
            break
        old_objective = objective(slope, intercept)
        step = 1.0
        accepted = False
        for _ in range(24):
            next_slope, next_intercept = slope - step * delta_a, intercept - step * delta_b
            if (math.isfinite(next_slope) and math.isfinite(next_intercept)
                    and objective(next_slope, next_intercept) <= old_objective):
                slope, intercept = next_slope, next_intercept
                accepted = True
                break
            step *= .5
        if not accepted:
            break
    return {
        'kind': 'platt-logit-l2-v1', 'slope': slope, 'intercept': intercept,
        'clip': 1e-6, 'optimizer': 'newton-loss-backtracking',
        'max_iterations': 100, 'line_search_steps': 24, 'tolerance': 1e-10,
        'iterations': iterations, 'l2': l2,
        'training_rows': n,
        'training_sha256': hashlib.sha256(json.dumps([list(probabilities), labels], sort_keys=True).encode()).hexdigest(),
    }


def predict_calibrated(model, probability):
    if not isinstance(model, dict) or model.get('kind') != 'platt-logit-l2-v1':
        raise ValueError('A fitted calibration artifact is required')
    try:
        if model.get('clip') != 1e-6:
            raise ValueError('Unknown calibration clipping')
        slope, intercept = model['slope'], model['intercept']
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in (slope, intercept)):
            raise ValueError('Invalid calibration parameters')
        return sigmoid(intercept + slope * _logit(probability))
    except (KeyError, TypeError) as error:
        raise ValueError('Invalid calibration parameters') from error
