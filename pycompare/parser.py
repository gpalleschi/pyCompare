from __future__ import annotations
import csv
import logging
from pathlib import Path
from typing import Any

from pycompare.config import FileConfig

logger = logging.getLogger(__name__)


def parse_file(file_path: str | Path, config: FileConfig) -> list[dict[str, str]]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    logger.info("Opening file: %s", path)
    file_size = path.stat().st_size
    logger.info("File size: %d bytes", file_size)

    if config.file_type == "csv":
        return _parse_csv(path, config)
    elif config.file_type == "fixed_length":
        return _parse_fixed_length(path, config)
    else:
        raise ValueError(f"Unsupported file type: {config.file_type}")


def _parse_csv(path: Path, config: FileConfig) -> list[dict[str, str]]:
    sep_map = {
        "TAB": "\t",
        ";": ";",
        ",": ",",
        "|": "|",
    }
    separator = sep_map.get(config.separator, config.separator)
    logger.info("Parsing CSV with separator: %s", repr(separator))

    uses_column_index = any(f.column_index is not None for f in config.fields)

    if uses_column_index:
        return _parse_csv_by_index(path, config, separator)
    else:
        return _parse_csv_by_header(path, config, separator)


def _parse_csv_by_header(path: Path, config: FileConfig, separator: str) -> list[dict[str, str]]:
    source_columns = [f.source for f in config.fields]
    if any(s is None for s in source_columns):
        raise ValueError("All CSV fields must have 'source' when not using column_index")

    records = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=separator)
        if not reader.fieldnames:
            raise ValueError(f"Empty CSV file: {path}")

        missing = [c for c in source_columns if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"Columns not found in CSV: {missing}")

        for row in reader:
            record = {}
            for field in config.fields:
                record[field.name] = row.get(field.source, "")
            records.append(record)

    logger.info("Parsed %d records from CSV (by header)", len(records))
    return records


def _parse_csv_by_index(path: Path, config: FileConfig, separator: str) -> list[dict[str, str]]:
    records = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=separator)

        header = next(reader, None)
        if header is None:
            raise ValueError(f"Empty CSV file: {path}")

        num_cols = len(header)
        for field in config.fields:
            if field.column_index is not None and field.column_index >= num_cols:
                raise ValueError(
                    f"Field '{field.name}' has column_index={field.column_index} "
                    f"but CSV has only {num_cols} columns"
                )

        for row in reader:
            if not row:
                continue
            record = {}
            for field in config.fields:
                if field.column_index is not None:
                    record[field.name] = row[field.column_index] if field.column_index < len(row) else ""
                else:
                    record[field.name] = row[header.index(field.source)] if field.source in header else ""
            records.append(record)

    logger.info("Parsed %d records from CSV (by column index)", len(records))
    return records


def _parse_fixed_length(path: Path, config: FileConfig) -> list[dict[str, str]]:
    logger.info("Parsing fixed-length file")

    records = []
    line_count = 0

    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line:
                continue
            line_count += 1
            record = {}
            for field in config.fields:
                if field.start is None or field.length is None:
                    raise ValueError(
                        f"Field '{field.name}' missing start/length in fixed-length config"
                    )
                raw = line[field.start : field.start + field.length]
                record[field.name] = raw
            records.append(record)

    logger.info("Parsed %d records from fixed-length file", line_count)
    return records
