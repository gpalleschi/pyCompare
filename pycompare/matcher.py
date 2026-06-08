from __future__ import annotations
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from pycompare.config import MatchConfig, MatchingFieldConfig, FieldConfig, FileConfig

logger = logging.getLogger(__name__)

MatchResult = tuple[int, int]
Record = dict[str, Any]


def match_records(
    file1_records: list[Record],
    file2_records: list[Record],
    match_config: MatchConfig,
    file1_config: FileConfig,
    file2_config: FileConfig,
) -> tuple[list[MatchResult], list[int], list[int]]:
    logger.info("Starting matching process")
    logger.info("File 1 records: %d", len(file1_records))
    logger.info("File 2 records: %d", len(file2_records))

    key_field_names, tolerance_fields = _classify_fields(match_config, file1_config, file2_config)

    logger.info("Key fields: %s", key_field_names)
    logger.info("Tolerance fields: %s", [tf.field for tf in tolerance_fields])

    index = _build_index(file2_records, key_field_names)
    logger.info("Built hash index with %d unique keys", len(index))

    matched_b: set[int] = set()
    matched_pairs: list[MatchResult] = []
    matched_a: set[int] = set()

    for a_idx, a_rec in enumerate(file1_records):
        a_key = _make_key(a_rec, key_field_names)
        candidates = index.get(a_key, [])

        for b_idx in candidates:
            if b_idx in matched_b:
                continue
            b_rec = file2_records[b_idx]

            if _check_tolerances(a_rec, b_rec, tolerance_fields):
                matched_pairs.append((a_idx, b_idx))
                matched_a.add(a_idx)
                matched_b.add(b_idx)
                break

    only_file1 = [i for i in range(len(file1_records)) if i not in matched_a]
    only_file2 = [i for i in range(len(file2_records)) if i not in matched_b]

    logger.info("Matched: %d pairs", len(matched_pairs))
    logger.info("Only in File 1: %d", len(only_file1))
    logger.info("Only in File 2: %d", len(only_file2))

    return matched_pairs, only_file1, only_file2


def _classify_fields(
    match_config: MatchConfig,
    file1_config: FileConfig,
    file2_config: FileConfig,
) -> tuple[list[str], list[MatchingFieldConfig]]:
    key_fields: list[str] = []
    tolerance_fields: list[MatchingFieldConfig] = []

    for mf in match_config.matching_fields:
        fc1 = file1_config.get_field(mf.field)
        fc2 = file2_config.get_field(mf.field)

        ftype = None
        if fc1:
            ftype = fc1.type
        elif fc2:
            ftype = fc2.type

        if ftype is None:
            raise ValueError(f"Field '{mf.field}' not found in either file config")

        if ftype == "string" or not mf.has_tolerance():
            key_fields.append(mf.field)
        else:
            tolerance_fields.append(mf)

    return key_fields, tolerance_fields


def _build_index(records: list[Record], key_fields: list[str]) -> dict[tuple, list[int]]:
    index: dict[tuple, list[int]] = defaultdict(list)
    for idx, rec in enumerate(records):
        key = _make_key(rec, key_fields)
        index[key].append(idx)
    return index


def _make_key(record: Record, key_fields: list[str]) -> tuple:
    values = []
    for f in key_fields:
        v = record.get(f)
        if isinstance(v, Decimal):
            v = str(v)
        values.append(v)
    return tuple(values)


def _check_tolerances(a_rec: Record, b_rec: Record, tolerance_fields: list[MatchingFieldConfig]) -> bool:
    for mf in tolerance_fields:
        a_val = a_rec.get(mf.field)
        b_val = b_rec.get(mf.field)

        if a_val is None or b_val is None:
            return False

        if isinstance(a_val, datetime):
            tol = mf.tolerance_seconds
            if tol is not None:
                diff = abs((a_val - b_val).total_seconds())
                if diff > tol:
                    return False
            elif a_val != b_val:
                return False

        elif isinstance(a_val, int):
            tol = mf.tolerance_seconds
            if tol is not None:
                if abs(a_val - b_val) > tol:
                    return False
            elif a_val != b_val:
                return False

        elif isinstance(a_val, Decimal):
            tol = mf.tolerance
            if tol is not None:
                if abs(a_val - b_val) > Decimal(str(tol)):
                    return False
            elif a_val != b_val:
                return False

        else:
            if a_val != b_val:
                return False

    return True
