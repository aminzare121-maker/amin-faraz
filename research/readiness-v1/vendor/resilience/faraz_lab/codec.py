"""Explicit, version-independent value codec for the synthetic lab journal.

Only the listed frozen core contracts can be reconstructed. Tags never name an
importable module, and decoding does not evaluate code or import a supplied type.
JSON numbers cannot silently turn into floats or Decimal approximations.
"""
from dataclasses import fields
from decimal import Decimal
import json

from faraz_core.authorization import EntryAuthorization, PolicyPin
from faraz_core.decision import EntryContext
from faraz_core.execution import BrokerEvent, DemoBinding, Intent, Phase, TraceEntry
from faraz_core.numbers import dec
from faraz_core.risk import ExposureAmount, LinearRiskModel, RiskRequest, VolumeRules
from faraz_core.temporal import Quote


class CodecError(ValueError):
    pass


_CLASSES = (EntryAuthorization, PolicyPin, EntryContext, BrokerEvent, DemoBinding,
            Intent, TraceEntry, ExposureAmount, LinearRiskModel, RiskRequest,
            VolumeRules, Quote)
_TYPES = {"core." + item.__name__: item for item in _CLASSES}
_NAMES = {value: key for key, value in _TYPES.items()}
MAX_DEPTH = 64
MAX_TEXT = 1_000_000


def canonical_bytes(value):
    """Canonical JSON for already explicit JSON primitives/envelopes."""
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise CodecError("NONCANONICAL_JSON_VALUE") from error


def _depth(depth):
    if depth > MAX_DEPTH:
        raise CodecError("CODEC_DEPTH_EXCEEDED")


def to_data(value, _depth_value=0):
    _depth(_depth_value)
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if len(str(abs(value))) > 128:
            raise CodecError("INTEGER_BOUND_EXCEEDED")
        return value
    if type(value) is str:
        if len(value) > MAX_TEXT:
            raise CodecError("TEXT_BOUND_EXCEEDED")
        return value
    if type(value) is Decimal:
        try:
            dec(value)
        except ValueError as error:
            raise CodecError("INVALID_EXACT_DECIMAL") from error
        return {"$type": "Decimal", "value": str(value)}
    if type(value) is Phase:
        return {"$type": "enum.Phase", "value": value.value}
    if type(value) is tuple:
        return {"$type": "tuple", "items": [to_data(item, _depth_value + 1) for item in value]}
    if type(value) in _NAMES:
        return {"$type": _NAMES[type(value)],
                "fields": {item.name: to_data(getattr(value, item.name), _depth_value + 1)
                           for item in fields(value) if item.init}}
    raise CodecError("UNREGISTERED_OR_MUTABLE_VALUE")


def from_data(value, _depth_value=0):
    _depth(_depth_value)
    if value is None or type(value) in (bool, int, str):
        # Apply the same integer/text bounds on both directions.
        return to_data(value)
    if type(value) is not dict or type(value.get("$type")) is not str:
        raise CodecError("EXPLICIT_TYPE_TAG_REQUIRED")
    tag = value["$type"]
    if tag == "Decimal":
        if set(value) != {"$type", "value"} or type(value["value"]) is not str:
            raise CodecError("INVALID_DECIMAL_TAG")
        try:
            result = dec(value["value"])
        except ValueError as error:
            raise CodecError("INVALID_EXACT_DECIMAL") from error
        if str(result) != value["value"]:
            raise CodecError("NONCANONICAL_DECIMAL_TAG")
        return result
    if tag == "enum.Phase":
        if set(value) != {"$type", "value"} or type(value["value"]) is not str:
            raise CodecError("INVALID_ENUM_TAG")
        try:
            return Phase(value["value"])
        except ValueError as error:
            raise CodecError("UNKNOWN_ENUM_VALUE") from error
    if tag == "tuple":
        if set(value) != {"$type", "items"} or type(value["items"]) is not list:
            raise CodecError("INVALID_TUPLE_TAG")
        return tuple(from_data(item, _depth_value + 1) for item in value["items"])
    if tag not in _TYPES:
        raise CodecError("UNKNOWN_TYPE_TAG")
    cls = _TYPES[tag]
    expected = {item.name for item in fields(cls) if item.init}
    if (set(value) != {"$type", "fields"} or type(value["fields"]) is not dict
            or set(value["fields"]) != expected):
        raise CodecError("UNKNOWN_OR_MISSING_CONTRACT_FIELD")
    arguments = {key: from_data(item, _depth_value + 1)
                 for key, item in value["fields"].items()}
    try:
        result = cls(**arguments)
    except (ValueError, TypeError, ArithmeticError, AttributeError) as error:
        raise CodecError("INVALID_CONTRACT_PAYLOAD") from error
    # Constructors may normalize values; untyped wire substitutions must not
    # pass merely because the core constructor accepts an equivalent string.
    if to_data(result, _depth_value) != value:
        raise CodecError("NONCANONICAL_CONTRACT_PAYLOAD")
    return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CodecError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def parse_json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_unique_object,
                          parse_constant=lambda unused: (_ for _ in ()).throw(
                              CodecError("NONFINITE_JSON_NUMBER")))
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        if isinstance(error, CodecError):
            raise
        raise CodecError("INVALID_JSON") from error


def dumps(value):
    return canonical_bytes(to_data(value))


def loads(raw):
    data = parse_json(raw)
    result = from_data(data)
    encoded = raw.encode("utf-8") if type(raw) is str else raw
    if type(encoded) is not bytes or dumps(result) != encoded:
        raise CodecError("NONCANONICAL_ENCODING")
    return result


encode = dumps
decode = loads
