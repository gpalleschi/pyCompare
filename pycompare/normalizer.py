from __future__ import annotations
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from pycompare.config import FieldConfig

logger = logging.getLogger(__name__)


def normalize_records(records: list[dict[str, str]], config_fields: list[FieldConfig]) -> list[dict[str, Any]]:
    logger.info("Normalizing %d records", len(records))

    field_funcs = [_make_normalizer(f) for f in config_fields]
    field_names = [f.name for f in config_fields]

    normalized = [None] * len(records)
    errors = 0

    for i, record in enumerate(records):
        try:
            result = {}
            for j, func in enumerate(field_funcs):
                result[field_names[j]] = func(record.get(field_names[j], ""))
                # print(f"Normalized field '{field_names[j]}': '{record.get(field_names[j], '')}' -> '{result[field_names[j]]}'")
            normalized[i] = result
        except Exception as e:
            errors += 1
            logger.warning("Error normalizing record %d: %s", i, e)
            if errors > 100:
                raise ValueError("Too many normalization errors (>100), aborting")

    if errors:
        normalized = [r for r in normalized if r is not None]

    logger.info("Normalized %d records (%d errors)", len(normalized), errors)
    return normalized


def _make_normalizer(field: FieldConfig) -> Callable:
    if field.type == "string":
        func = _make_string_normalizer(field)
    elif field.type == "datetime":
        func = _make_datetime_normalizer(field)
    elif field.type == "integer":
        func = _make_integer_normalizer(field)
    elif field.type == "decimal":
        func = _make_decimal_normalizer(field)
    else:
        raise ValueError(f"Unknown field type: {field.type}")
    return func


def _make_string_normalizer(field: FieldConfig) -> Callable:
    if field.cleaning_regex:
        def normalize(val: str) -> str:
            for rule in field.cleaning_regex:
                try:
                    val = rule.apply(val)
                except Exception:
                    pass
            return val
    else:
        def normalize(val: str) -> str:
            return val
    return normalize


def _make_datetime_normalizer(field: FieldConfig) -> Callable:
    fmt = field.format
    if not fmt:
        raise ValueError(f"No format specified for datetime field '{field.name}'")

    def normalize(val: str) -> datetime:
        if not val or val.strip() == "":
            raise ValueError(f"Empty datetime value for field '{field.name}'")
        try:
            return datetime.strptime(val.strip(), fmt)
        except ValueError as e:
            raise ValueError(f"Cannot parse datetime '{val}' with format '{fmt}': {e}")

    return normalize


def _make_integer_normalizer(field: FieldConfig) -> Callable:
    regex_rules = field.cleaning_regex

    def normalize(val: str) -> int:
        s = val.strip()
        if not s:
            raise ValueError(f"Empty integer value for field '{field.name}'")
        try:
            return int(s)
        except ValueError:
            for rule in regex_rules:
                try:
                    s = rule.apply(val.strip())
                except Exception:
                    pass
            try:
                return int(s.strip())
            except ValueError as e:
                raise ValueError(f"Cannot parse integer for field '{field.name}': {e}")

    return normalize


def _make_decimal_normalizer(field: FieldConfig) -> Callable:
    regex_rules = field.cleaning_regex

    def normalize(val: str) -> Decimal:
        s = val.strip().replace(",", ".")
        if not s:
            raise ValueError(f"Empty decimal value for field '{field.name}'")
        try:
            return Decimal(s)
        except InvalidOperation:
            for rule in regex_rules:
                try:
                    s = rule.apply(val.strip()).replace(",", ".")
                except Exception:
                    pass
            try:
                return Decimal(s)
            except InvalidOperation as e:
                raise ValueError(f"Cannot parse decimal for field '{field.name}': {e}")

    return normalize
