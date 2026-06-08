# PyCompare — File Reconciliation Tool

PyCompare is a desktop Windows application for comparing two heterogeneous data files and producing reconciliation statistics and reports. It is fully configurable via JSON — **no hardcoded domain logic** — making it suitable for telecom, finance, log analysis, and any data-matching task.

---
<img src="./assets/logo/pyCompare.png" width="200" />

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Input Format: CSV](#input-format-csv)
- [Input Format: Fixed-Length](#input-format-fixed-length)
- [JSON Configuration](#json-configuration)
  - [File Configuration](#1-file-configuration)
  - [Match Configuration](#2-match-configuration)
- [Normalization Rules](#normalization-rules)
  - [string](#string)
  - [datetime](#datetime)
  - [integer](#integer)
  - [decimal](#decimal)
- [Matching Algorithm](#matching-algorithm)
- [Output](#output)
  - [Statistics](#statistics)
  - [Reports](#reports)
- [Worked Example](#worked-example)
  - [CSV files](#step-1--the-csv-files)
  - [File configurations](#step-2--file-json-configurations)
  - [Match configuration](#step-3--match-json-configuration)
  - [Run](#step-4--run)
  - [Results](#step-5--results)
- [Fixed-Length Example](#fixed-length-example)
- [GUI Reference](#gui-reference)
- [Error Handling](#error-handling)
- [Performance](#performance)
- [Build Executable](#build-executable)
- [Dependencies](#dependencies)
- [License](#license)

---

## Features

- **Parse** CSV (configurable separator) and fixed-length files
- **Select fields by column name (`source`) or column position (`column_index`)** — only the fields needed for comparison; unmentioned columns are ignored
- **Normalize** fields with per-field regex cleaning chains, datetime parsing, integer/decimal conversion
- **Match** records using a hash-indexed O(n) algorithm — no nested loops
- **Tolerances** — configurable tolerance for datetime (seconds), integer (units), and decimal values
- **Reports** — generates `reconciled.xlsx`, `only_file1.xlsx`, `only_file2.xlsx`, `statistics.csv` with record sequence numbers
- **GUI** — Tkinter interface with real-time logging, progress spinner, and custom color theme
- **100 % configurable** — no domain-specific logic baked in

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the GUI
python main.py
# or
python -m pycompare

# Build a standalone .exe
python build_exe.py
# → dist/PyCompare.exe
```

---

## Input Format: CSV

Any delimiter-separated file with a header row. Supported separators:

| Separator | `separator` value |
|-----------|-------------------|
| Semicolon | `";"` |
| Comma     | `","` |
| Pipe      | `"|"` |
| Tab       | `"TAB"` |

Example file (`calls.csv`):

```csv
CLI;CLD;START_TIME;DURATION
+39 347-1234567;+39 02-12345678;01/01/2024 10:00:00;120
+39 347-2345678;+39 02-23456789;01/01/2024 10:05:00;60
```

Fields can be selected **by column name** (using the `source` key) or **by 0-based column position**
(using the `column_index` key). You only need to specify the fields you care about; extra columns
are silently ignored. Files with UTF-8 BOM are handled automatically.

---

## Input Format: Fixed-Length

A text file where every record occupies a fixed number of characters and each field is extracted by its start position and length.

Example file (`cdrs.txt`):

```
+39 347-1234567     +39 02-12345678     01/01/2024 10:00:00  120
+39 347-2345678     +39 02-23456789     01/01/2024 10:05:00   60
```

Field positions are defined in the JSON configuration (see below).

---

## JSON Configuration

Two JSON configuration files are needed — one per source file — plus a match configuration file.

---

### 1. File Configuration

```json
{
  "file_type": "csv",
  "separator": ";",
  "fields": [
    {
      "name": "caller",
      "source": "CLI",
      "type": "string",
      "cleaning_regex": [
        { "pattern": "\\D", "replacement": "" },
        { "pattern": "^39", "replacement": "" }
      ]
    },
    {
      "name": "start_time",
      "source": "START_TIME",
      "type": "datetime",
      "format": "%d/%m/%Y %H:%M:%S"
    },
    {
      "name": "duration",
      "source": "DURATION",
      "type": "integer"
    },
    {
      "name": "amount",
      "source": "AMOUNT",
      "type": "decimal"
    }
  ]
}
```

#### Top-level keys

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `file_type` | `string` | yes | `"csv"` or `"fixed_length"` |
| `separator` | `string` | for CSV | The column delimiter (`";"`, `","`, `"|"`, `"TAB"`) |
| `fields` | `array` | yes | Array of field descriptors (see below) |

#### Field descriptor

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `name` | `string` | yes | Normalized field name used in matching |
| `source` | `string` | for CSV (unless `column_index` is given) | Column header name in the CSV file |
| `column_index` | `int` | for CSV (unless `source` is given) | 0-based column position in the CSV file |
| `type` | `string` | yes | `"string"`, `"datetime"`, `"integer"`, or `"decimal"` |
| `cleaning_regex` | `array` | no | Ordered list of regex substitutions applied before matching |
| `format` | `string` | for datetime | `strptime` format string, e.g. `"%d/%m/%Y %H:%M:%S"` |
| `start` | `int` | for fixed-length | Zero-based start position |
| `length` | `int` | for fixed-length | Number of characters |

You may specify only the fields you need for comparison — there is no requirement to list every column
present in the file. Unmentioned columns are simply ignored.

**Selecting fields by column name** (`source`):

```json
{
  "file_type": "csv",
  "separator": ";",
  "fields": [
    { "name": "caller", "source": "CLI", "type": "string" },
    { "name": "called", "source": "CLD", "type": "string" }
  ]
}
```

**Selecting fields by column position** (`column_index`, 0-based):

```json
{
  "file_type": "csv",
  "separator": ";",
  "fields": [
    { "name": "caller", "column_index": 0, "type": "string" },
    { "name": "called", "column_index": 1, "type": "string" },
    { "name": "start_time", "column_index": 2, "type": "datetime", "format": "%d/%m/%Y %H:%M:%S" },
    { "name": "duration", "column_index": 3, "type": "integer" }
  ]
}
```

A field can include **both** `source` and `column_index`; when both are present, `column_index`
takes precedence (useful as documentation or for fallback).

#### Regex rule

```json
{ "pattern": "\\D", "replacement": "" }
```

Each rule applies `re.sub(pattern, replacement, value)` in order.

---

### 2. Match Configuration

```json
{
  "matching_fields": [
    { "field": "caller" },
    { "field": "start_time", "tolerance_seconds": 3 },
    { "field": "duration", "tolerance_seconds": 5 },
    { "field": "amount", "tolerance": 0.01 }
  ]
}
```

| Key | Type | Description |
|-----|------|-------------|
| `field` | `string` | The normalized field name (must match `name` in both file configs) |
| `tolerance_seconds` | `int` | Tolerance for `datetime` or `integer` fields — `abs(a - b) ≤ value` |
| `tolerance` | `float` | Tolerance for `decimal` fields — `abs(a - b) ≤ value` |

Fields **without** a tolerance are part of the composite hash key (exact match required).

---

## Normalization Rules

### string

1. If `cleaning_regex` is present, each regex is applied in order.
2. If no regex rules, the raw string is used as-is.

```
Input:    +39 347-1234567
Regex 1:  \D → ""      → "393471234567"
Regex 2:  ^39 → ""     → "3471234567"
Result:                 "3471234567"
```

### datetime

1. Strips whitespace.
2. Parsed with `datetime.strptime(value, format)` using the configured `format`.

```
Input:    "01/01/2024 10:00:00"
Format:   "%d/%m/%Y %H:%M:%S"
Result:   datetime(2024, 1, 1, 10, 0, 0)
```

### integer

1. Strips whitespace.
2. Tries `int(value)`.
3. Falls back to applying `cleaning_regex` (if any), then retries.

```
Input:    " 120 "
Result:   120
```

### decimal

1. Strips whitespace and replaces `,` with `.`.
2. Tries `Decimal(value)`.
3. Falls back to applying `cleaning_regex`, then retries.

```
Input:    "1.234,56"
Result:   Decimal("1234.56")
```

---

## Matching Algorithm

The algorithm avoids O(n²) nested loops by using a **hash index**:

1. **Classify fields** — Fields with no tolerance (or `type="string"`) become **key fields**; fields with tolerance become **tolerance fields**.
2. **Build composite key** — For the key fields, a tuple of values is used as a dictionary key.
3. **Index File B** — A `dict[tuple, list[index]]` maps every distinct composite key to the record indices in File B.
4. **Iterate File A** — For each record:
   - Compute its composite key and look up candidates in the index.
   - For each candidate not already matched, apply the tolerance checks.
   - If all tolerances pass, the pair is recorded and the candidate is marked as used.
5. **Result** — Unmatched indices are returned as *only in file 1* / *only in file 2*.

**Complexity: O(n)** — a single pass over file A with hash lookups against file B.

---

## Output

### Statistics

Displayed in the GUI and written to `statistics.csv`:

| Metric | Description |
|--------|-------------|
| Total File 1 | Number of parsed and normalized records in File 1 |
| Total File 2 | Number of parsed and normalized records in File 2 |
| Reconciled | Pairs of records that matched |
| Only File 1 | Records in File 1 with no match in File 2 |
| Only File 2 | Records in File 2 with no match in File 1 |
| Match % | `(Reconciled / Total File 1) × 100` |
| Processing Time | Wall-clock time in seconds |

### Reports

All written to the output directory:

| File | Content |
|------|---------|
| `reconciled.xlsx` | Side-by-side view of matched records. Columns: `F1_Row` (record position in File 1, 1-based), `F2_Row` (record position in File 2, 1-based), `F1_{fields}`, `F2_{fields}`, `Diff_{numeric/datetime fields}` |
| `only_file1.xlsx` | Records present only in File 1. First column `Row` shows the record's 1-based position from the original input file. |
| `only_file2.xlsx` | Records present only in File 2. First column `Row` shows the record's 1-based position from the original input file. |
| `statistics.csv` | Summary metrics |

---

## Worked Example

### Step 1 – The CSV files

**file1.csv** (5 call records):

```csv
CLI;CLD;START_TIME;DURATION
+39 347-1234567;+39 02-12345678;01/01/2024 10:00:00;120
+39 347-2345678;+39 02-23456789;01/01/2024 10:05:00;60
+39 347-3456789;+39 02-34567890;01/01/2024 10:10:00;90
+39 347-4567890;+39 02-45678901;01/01/2024 10:15:00;45
+39 347-5678901;+39 02-56789012;01/01/2024 10:20:00;30
```

**file2.csv** (4 call records, slightly different formatting):

```csv
CLI;CLD;START_TIME;DURATION
393471234567;390212345678;01/01/2024 10:00:02;118
393472345678;390223456789;01/01/2024 10:05:01;62
393473456789;390234567890;01/01/2024 10:10:00;91
999999999999;999999999999;01/01/2024 11:00:00;10
```

### Step 2 – File JSON configurations

**file1_config.json**: removes all non-digits then strips the Italian prefix `39` from caller/called.

```json
{
  "file_type": "csv",
  "separator": ";",
  "fields": [
    {
      "name": "caller",
      "source": "CLI",
      "type": "string",
      "cleaning_regex": [
        { "pattern": "\\D", "replacement": "" },
        { "pattern": "^39", "replacement": "" }
      ]
    },
    {
      "name": "called",
      "source": "CLD",
      "type": "string",
      "cleaning_regex": [
        { "pattern": "\\D", "replacement": "" },
        { "pattern": "^39", "replacement": "" }
      ]
    },
    {
      "name": "start_time",
      "source": "START_TIME",
      "type": "datetime",
      "format": "%d/%m/%Y %H:%M:%S"
    },
    {
      "name": "duration",
      "source": "DURATION",
      "type": "integer"
    }
  ]
}
```

**file2_config.json**: uses `column_index` (0-based) to select fields by position instead of by header name. The header row is still consumed but ignored for field lookup.

```json
{
  "file_type": "csv",
  "separator": ";",
  "fields": [
    {
      "name": "caller",
      "column_index": 0,
      "type": "string",
      "cleaning_regex": [
        { "pattern": "^39", "replacement": "" }
      ]
    },
    {
      "name": "called",
      "column_index": 1,
      "type": "string",
      "cleaning_regex": [
        { "pattern": "^39", "replacement": "" }
      ]
    },
    {
      "name": "start_time",
      "column_index": 2,
      "type": "datetime",
      "format": "%d/%m/%Y %H:%M:%S"
    },
    {
      "name": "duration",
      "column_index": 3,
      "type": "integer"
    }
  ]
}
```

### Step 3 – Match JSON configuration

```json
{
  "matching_fields": [
    { "field": "caller" },
    { "field": "called" },
    { "field": "start_time", "tolerance_seconds": 3 },
    { "field": "duration", "tolerance_seconds": 5 }
  ]
}
```

`caller` and `called` are exact-match string fields (the composite key).  
`start_time` allows ±3 seconds.  
`duration` allows ±5 units.

### Step 4 – Run

```python
from pycompare.reconcile import ReconcileEngine

engine = ReconcileEngine()
stats = engine.run(
    file1_path="file1.csv",
    file1_config_path="file1_config.json",
    file2_path="file2.csv",
    file2_config_path="file2_config.json",
    match_config_path="match_config.json",
    output_dir="output",
)
```

### Step 5 – Results

```
Total File 1:   5
Total File 2:   4
Reconciled:     3    ← records 1, 2, 3 matched
Only File 1:    2    ← records 4, 5 had no counterpart
Only File 2:    1    ← record 4 had no counterpart
Match %:       60.00%
```

**What happened under the hood:**

| Record | File 1 (normalized) | File 2 (normalized) | Match? |
|--------|---------------------|---------------------|--------|
| 1 | caller=3471234567, called=0212345678, start=10:00:00, dur=120 | caller=3471234567, called=0212345678, start=10:00:02, dur=118 | **Yes** (times within 2s, durations within 2) |
| 2 | caller=3472345678, called=0223456789, start=10:05:00, dur=60 | caller=3472345678, called=0223456789, start=10:05:01, dur=62 | **Yes** (times within 1s, durations within 2) |
| 3 | caller=3473456789, called=0234567890, start=10:10:00, dur=90 | caller=3473456789, called=0234567890, start=10:10:00, dur=91 | **Yes** (exact time, durations within 1) |
| 4 | caller=3474567890, called=045678901, start=10:15:00, dur=45 | (no matching key) | No |
| 5 | caller=3475678901, called=056789012, start=10:20:00, dur=30 | (no matching key) | No |
| — | (no matching key) | caller=9999999999, called=9999999999, start=11:00:00, dur=10 | No |

---

## Fixed-Length Example

**Configuration** — each field declares `start` (zero-based) and `length`:

```json
{
  "file_type": "fixed_length",
  "fields": [
    { "name": "caller",     "source": "CLI",        "type": "string",   "start": 0,  "length": 20 },
    { "name": "called",     "source": "CLD",        "type": "string",   "start": 20, "length": 20 },
    { "name": "start_time", "source": "START_TIME",  "type": "datetime", "start": 40, "length": 19,
      "format": "%d/%m/%Y %H:%M:%S" },
    { "name": "duration",   "source": "DURATION",   "type": "integer",  "start": 59, "length": 5 }
  ]
}
```

**Data file** (`cdrs.txt`):

```
+39 347-1234567     +39 02-12345678     01/01/2024 10:00:00  120
+39 347-2345678     +39 02-23456789     01/01/2024 10:05:00   60
```

Each line is exactly 64 characters. The fields are sliced as:
- `line[0:20]`  → caller
- `line[20:40]` → called
- `line[40:59]` → start_time
- `line[59:64]` → duration

---

## GUI Reference

1. **Input Configuration** — Fill in the six fields using the Browse buttons (or type paths manually):
   - File 1, Config File 1 JSON, File 2, Config File 2 JSON, Matching Config JSON
2. **Output Directory** — Defaults to `./output`; change via the Output Dir button.
3. **Compare** — Starts the pipeline. A modal progress popup with a spinner and logo appears.
4. **Results** — After completion the seven metrics update automatically.
5. **Log** — Scrollable text area showing every pipeline step with timestamps.
6. **Close** — If a comparison is running, you are prompted to confirm exit.

---

## Error Handling

All errors are surfaced as descriptive message boxes and logged:

| Scenario | Behavior |
|----------|----------|
| File not found | Error popup listing missing files |
| Invalid JSON | Error popup with the parse error |
| Missing required keys | Validation error with details |
| Regex compilation failure | ValueError with pattern and error |
| Datetime parse failure | Warning recorded, record skipped (after 100 errors the process aborts) |
| Column not found in CSV | Error popup listing missing columns |
| Export error | Exception logged, error popup shown |

---

## Performance

Tested on 200 000 records per file (190 000 matches):

| Stage | Throughput |
|-------|------------|
| CSV parsing (csv.DictReader) | ~150 000 rec/s |
| Normalization | ~30 000 rec/s |
| Hash-indexed matching | ~130 000 rec/s |
| Excel report generation | depends on output size |

**The algorithm is O(n)** and scales linearly — 1 000 000 records per file is supported.

---

## Build Executable

```bash
python build_exe.py
```

Output: `dist/PyCompare.exe` — a single-file, no-console Windows application built with PyInstaller.

---

## Dependencies

- Python ≥ 3.12
- [pandas](https://pandas.pydata.org/) ≥ 2.0.0
- [openpyxl](https://openpyxl.readthedocs.io/) ≥ 3.1.0
- [Pillow](https://python-pillow.org/) ≥ 10.0.0
- [PyInstaller](https://pyinstaller.org/) ≥ 6.0.0 (for builds)

---

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE 3.0 License - see the [LICENSE](LICENSE) file for details 
