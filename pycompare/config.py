from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class RegexRule:
    pattern: str
    replacement: str
    _compiled: Any = field(repr=False, default=None)

    def __post_init__(self):
        try:
            self._compiled = re.compile(self.pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{self.pattern}': {e}")

    def apply(self, value: str) -> str:
        return self._compiled.sub(self.replacement, value)


@dataclass
class FieldConfig:
    name: str
    source: Optional[str] = None
    type: str = "string"
    cleaning_regex: list[RegexRule] = field(default_factory=list)
    format: Optional[str] = None
    start: Optional[int] = None
    length: Optional[int] = None
    column_index: Optional[int] = None

    def __post_init__(self):
        valid_types = {"string", "datetime", "integer", "decimal"}
        if self.type not in valid_types:
            raise ValueError(f"Invalid field type '{self.type}'. Must be one of: {valid_types}")
        if self.type == "datetime" and not self.format:
            raise ValueError(f"Field '{self.name}' is datetime but no format specified")


@dataclass
class FileConfig:
    file_type: str
    separator: Optional[str] = None
    fields: list[FieldConfig] = field(default_factory=list)

    def __post_init__(self):
        valid_types = {"csv", "fixed_length"}
        if self.file_type not in valid_types:
            raise ValueError(f"Invalid file type '{self.file_type}'. Must be one of: {valid_types}")

        names = [f.name for f in self.fields]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate field names: {names}")

        for f in self.fields:
            if self.file_type == "csv":
                if f.source is None and f.column_index is None:
                    raise ValueError(
                        f"CSV field '{f.name}' must have either 'source' (column name) "
                        f"or 'column_index' (0-based column position)"
                    )
                if self.separator is None:
                    raise ValueError("CSV file type requires a separator")
            elif self.file_type == "fixed_length":
                if f.start is None or f.length is None:
                    raise ValueError(
                        f"Fixed-length field '{f.name}' must have start and length"
                    )

    def get_field(self, name: str) -> Optional[FieldConfig]:
        for f in self.fields:
            if f.name == name:
                return f
        return None


@dataclass
class MatchingFieldConfig:
    field: str
    tolerance_seconds: Optional[int] = None
    tolerance: Optional[float] = None

    def has_tolerance(self) -> bool:
        return self.tolerance_seconds is not None or self.tolerance is not None

    def get_tolerance(self, field_type: str) -> Optional[float]:
        if field_type in ("datetime", "integer"):
            return float(self.tolerance_seconds) if self.tolerance_seconds is not None else None
        if field_type == "decimal":
            return float(self.tolerance) if self.tolerance is not None else None
        return None


@dataclass
class MatchConfig:
    matching_fields: list[MatchingFieldConfig] = field(default_factory=list)

    def __post_init__(self):
        names = [f.field for f in self.matching_fields]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate matching fields: {names}")

    def get_matching_field(self, name: str) -> Optional[MatchingFieldConfig]:
        for mf in self.matching_fields:
            if mf.field == name:
                return mf
        return None


def _parse_regex_rules(rules_data: list[dict]) -> list[RegexRule]:
    return [RegexRule(pattern=r["pattern"], replacement=r["replacement"]) for r in rules_data]


def load_file_config(path: str | Path) -> FileConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"Config must be a JSON object, got {type(data).__name__}")

    if "file_type" not in data:
        raise ValueError("Missing required key 'file_type' in config")
    if "fields" not in data:
        raise ValueError("Missing required key 'fields' in config")
    if not isinstance(data["fields"], list) or len(data["fields"]) == 0:
        raise ValueError("'fields' must be a non-empty array")

    fields = []
    for i, fd in enumerate(data["fields"]):
        if not isinstance(fd, dict):
            raise ValueError(f"Field at index {i} must be a JSON object")
        if "name" not in fd:
            raise ValueError(f"Field at index {i} missing required key 'name'")
        if "type" not in fd:
            raise ValueError(f"Field at index {i} missing required key 'type'")

        cleaning_regex = _parse_regex_rules(fd.get("cleaning_regex", []))

        fields.append(
            FieldConfig(
                name=fd["name"],
                source=fd.get("source"),
                type=fd["type"],
                cleaning_regex=cleaning_regex,
                format=fd.get("format"),
                start=fd.get("start"),
                length=fd.get("length"),
                column_index=fd.get("column_index"),
            )
        )

    return FileConfig(
        file_type=data["file_type"],
        separator=data.get("separator"),
        fields=fields,
    )


def load_match_config(path: str | Path) -> MatchConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Matching config file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"Matching config must be a JSON object, got {type(data).__name__}")

    if "matching_fields" not in data:
        raise ValueError("Missing required key 'matching_fields' in matching config")
    if not isinstance(data["matching_fields"], list) or len(data["matching_fields"]) == 0:
        raise ValueError("'matching_fields' must be a non-empty array")

    matching_fields = []
    for i, mfd in enumerate(data["matching_fields"]):
        if not isinstance(mfd, dict):
            raise ValueError(f"Matching field at index {i} must be a JSON object")
        if "field" not in mfd:
            raise ValueError(f"Matching field at index {i} missing required key 'field'")

        matching_fields.append(
            MatchingFieldConfig(
                field=mfd["field"],
                tolerance_seconds=mfd.get("tolerance_seconds"),
                tolerance=mfd.get("tolerance"),
            )
        )

    return MatchConfig(matching_fields=matching_fields)
