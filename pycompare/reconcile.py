from __future__ import annotations
import logging
import time
from pathlib import Path
from typing import Callable, Optional

from pycompare.config import FileConfig, MatchConfig, load_file_config, load_match_config
from pycompare.matcher import match_records
from pycompare.normalizer import normalize_records
from pycompare.parser import parse_file
from pycompare.report import ReconciliationStats, generate_reports

logger = logging.getLogger(__name__)


class ReconcileEngine:
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.log_callback = log_callback

    def _log(self, message: str, level: str = "INFO"):
        if self.log_callback:
            self.log_callback(f"[{level}] {message}")
        else:
            getattr(logger, level.lower(), logger.info)(message)

    def run(
        self,
        file1_path: str | Path,
        file1_config_path: str | Path,
        file2_path: str | Path,
        file2_config_path: str | Path,
        match_config_path: str | Path,
        output_dir: str | Path,
    ) -> ReconciliationStats:
        start_time = time.time()

        self._log("Loading configurations...")
        file1_config = load_file_config(file1_config_path)
        self._log(f"File 1 config loaded: {file1_config.file_type}, {len(file1_config.fields)} fields")

        file2_config = load_file_config(file2_config_path)
        self._log(f"File 2 config loaded: {file2_config.file_type}, {len(file2_config.fields)} fields")

        match_config = load_match_config(match_config_path)
        self._log(f"Matching config loaded: {len(match_config.matching_fields)} fields")

        self._validate_configs(file1_config, file2_config, match_config)

        self._log("Parsing File 1...")
        raw_records1 = parse_file(file1_path, file1_config)
        self._log(f"File 1: {len(raw_records1)} raw records")

        self._log("Parsing File 2...")
        raw_records2 = parse_file(file2_path, file2_config)
        self._log(f"File 2: {len(raw_records2)} raw records")

        self._log("Normalizing File 1...")
        records1 = normalize_records(raw_records1, file1_config.fields)
        self._log(f"File 1: {len(records1)} normalized records")

        self._log("Normalizing File 2...")
        records2 = normalize_records(raw_records2, file2_config.fields)
        self._log(f"File 2: {len(records2)} normalized records")

        self._log("Starting matching...")
        matched_pairs, only_file1, only_file2 = match_records(
            records1, records2, match_config, file1_config, file2_config
        )
        self._log(
            f"Matching complete: {len(matched_pairs)} matched, "
            f"{len(only_file1)} only in File 1, {len(only_file2)} only in File 2"
        )

        self._log("Generating reports...")
        stats = generate_reports(
            records1,
            records2,
            matched_pairs,
            only_file1,
            only_file2,
            file1_config,
            file2_config,
            match_config,
            output_dir,
        )

        elapsed = time.time() - start_time
        stats.processing_time = elapsed
        self._log(f"Total processing time: {elapsed:.3f}s")
        self._log(f"Reports saved to: {output_dir}")

        return stats

    def _validate_configs(
        self,
        file1_config: FileConfig,
        file2_config: FileConfig,
        match_config: MatchConfig,
    ):
        matched_field_names = {mf.field for mf in match_config.matching_fields}
        f1_names = {f.name for f in file1_config.fields}
        f2_names = {f.name for f in file2_config.fields}

        missing_f1 = matched_field_names - f1_names
        missing_f2 = matched_field_names - f2_names

        if missing_f1:
            self._log(f"Fields not found in File 1 config: {missing_f1}", "WARNING")
        if missing_f2:
            self._log(f"Fields not found in File 2 config: {missing_f2}", "WARNING")

        common = matched_field_names & f1_names & f2_names
        if not common:
            raise ValueError(
                f"No matching fields found in both file configs. "
                f"Missing in File 1: {missing_f1}. Missing in File 2: {missing_f2}"
            )
