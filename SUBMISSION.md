# Submission

## Candidate
- **Name:** Namitha
- **Assignment chosen:** A - Interaction Ledger & Reporting Pipeline
- **Time spent:** Approximately 3 hours

## How to run

Requirements: Python 3.11 or later.

Run from the repository root:

```powershell
python -m pip install -r requirements.txt

python assignment-a-data/tools/generate_data.py --seed 42 --scale small --out data

# Generate a private Fernet key and configure AU_PII_KEY.
# Keep the same key for subsequent runs using this database.
$env:AU_PII_KEY = "<your-private-fernet-key>"

python -m solution.cli init
python -m solution.cli ingest data/drop_1
python -m solution.cli ingest data/drop_2
python -m solution.cli report --out reports

python -m pytest -q
```

Do not commit the encryption key, generated database, data, or reports.

## Design

The solution is implemented in Python and uses SQLite for persistent storage.

The implementation is divided into modules:

- `normalization.py` – normalizes and validates input values.
- `lead_ingest.py` – processes lead CSV files, validates records, and handles duplicates and rejected rows.
- `event_ingest.py` – processes call-event JSONL files, handles malformed and duplicate events, and retains events that cannot yet be linked to leads.
- `security.py` – encrypts sensitive values, generates phone hashes for matching, and masks phone numbers in reports.
- `db.py` – defines the SQLite schema and database operations.
- `pipeline.py` – coordinates ingestion and processing.
- `reporting.py` – generates the required reports.
- `cli.py` – provides the command-line interface.

The database separates leads, interaction events, rejected lead rows, quarantined events, ingestion history, and data-quality counters.

Phone numbers are represented using keyed hashes for matching and encrypted ciphertext for protected storage. Customer names are stored in encrypted form. Events that arrive before their corresponding leads are retained so they can be linked later.

## Decisions & assumptions

| Decision | Why | Alternative considered |
|---|---|---|
| SQLite for persistence | Lightweight relational storage without a separate database server. | PostgreSQL or MySQL |
| Keyed phone hashes | Supports matching without storing plaintext phone numbers as lookup values. | Plaintext matching |
| Fernet encryption | Protects sensitive values stored in the database. | Plaintext storage |
| Retain unlinked events | Events may arrive before their lead records. | Rejecting orphan events |
| Quarantine malformed events | Preserves invalid input without stopping the entire ingestion run. | Stopping ingestion |
| Generate reports from stored data | Allows reports to be regenerated independently. | Reporting during ingestion |

## Failure modes considered

- Invalid or missing required lead fields are rejected.
- Invalid phone values are rejected during validation.
- Malformed events are quarantined.
- Duplicate lead records are merged.
- Duplicate events are dropped.
- Events without a matching lead are retained as orphans for later linking.
- Sensitive phone and customer-name values are encrypted.
- Phone numbers are masked in generated reports.
- Data is persisted in SQLite.

Known limitations and possible improvements:
- Encryption could be made more configurable for additional PII fields.
- Batch and file identity handling could be made more portable across machine paths.
- More tests could cover crash recovery and unusual input scenarios.

## Testing

Automated tests are included under `tests/`.

The test files cover:
- Event ingestion.
- Event reporting and disposition handling.
- Late lead linking.
- Lead ingestion.
- Data normalization.
- PII encryption and security.

Test command:

```bash
python -m pytest -q
```

Latest test result in the original repository:

```text
24 passed in 0.38s
```

## Results

The official sample dataset was generated with seed `42` and scale `small`.

Both data drops were ingested successfully, and all five required reports were generated:

- `lead_report.csv`
- `batch_summary.csv`
- `daily_overview.csv`
- `rejections.csv`
- `data_quality.json`

Combined processing results:

| Metric | Result |
|---|---:|
| Lead rows processed | 2,057 |
| Lead rows rejected | 108 |
| Duplicate lead rows merged | 57 |
| Field warnings | 122 |
| Events processed | 8,745 |
| Malformed events | 8 |
| Duplicate events dropped | 237 |
| Orphan events | 462 |
| Unknown disposition events | 18 |

Execution timings were not separately benchmarked.

## If I had another day

1. Expand tests for crash recovery, repeated ingestion, and edge cases.
2. Improve portability of batch and file identity handling.
3. Make sensitive-field encryption more configurable.
4. Add clearer operational logging and error diagnostics.
5. Benchmark performance with larger datasets.