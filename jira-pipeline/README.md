# Jira Data Pipeline

A modular, cross-platform data pipeline for fetching Jira issues, generating
analytics, and producing PDF reports. Runs on Windows, Linux, and macOS.

## Project Structure

```
jira-pipeline/
├── src/
│   ├── ingestion/        # Jira API client & local file loaders
│   ├── processing/       # DataFrame cleaning, transformation, enrichment
│   ├── visualization/    # Matplotlib chart generators
│   └── reporting/        # PDF report assembly
├── config/
│   └── settings.py       # All pipeline configuration
├── data/                 # Raw exports (CSV/Excel) land here
├── reports/              # Generated PDF reports land here
├── tests/                # Test stubs
├── cli.py                # CLI entry point
└── pyproject.toml        # UV / pip project metadata
```

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Set environment variables

```bash
export JIRA_URL="https://jira.example.com"
export JIRA_TOKEN="your-personal-access-token"
export JIRA_CERT="/path/to/client-cert.pem"   # optional
```

On Windows (PowerShell):
```powershell
$env:JIRA_URL = "https://jira.example.com"
$env:JIRA_TOKEN = "your-personal-access-token"
$env:JIRA_CERT = "C:\path\to\client-cert.pem"
```

### 3. Run the pipeline

```bash
# Full pipeline: fetch from Jira → export raw data → generate PDF report
uv run python cli.py

# Specific filter IDs (overrides config defaults)
uv run python cli.py --filters 12345 67890

# Export raw data only (no PDF)
uv run python cli.py --export-raw

# Generate PDF report only (reads from local files in data/)
uv run python cli.py --report-only

# Skip Jira fetch, use local CSV/Excel files configured in settings
uv run python cli.py --local

# Choose export format
uv run python cli.py --format xlsx
uv run python cli.py --format csv
```

### CLI Options

| Flag              | Description                                      |
|-------------------|--------------------------------------------------|
| `--filters`       | Space-separated Jira filter IDs                  |
| `--export-raw`    | Export raw data only, skip PDF generation         |
| `--report-only`   | Generate PDF from existing local data files       |
| `--local`         | Load data from local files instead of Jira        |
| `--format`        | Export format: `csv` or `xlsx` (default from config) |
| `--config`        | Path to an alternative settings module            |

## Configuration

Edit `config/settings.py` to customize:

- Default filter IDs and per-filter report titles
- Jira field mappings
- Issue type inclusion (CR, PR, or both)
- Export format (csv / xlsx)
- Extra user columns (Update_Due_Date, Meeting_Comments)
- Chart selection per report
- Output directories

## Extending

**Add a new chart type:**

1. Create a function in `src/visualization/charts.py` that accepts a DataFrame
   and returns a `matplotlib.figure.Figure`.
2. Register it in the `CHART_REGISTRY` dict.
3. Reference it by key in `config/settings.py` → `REPORT_CHARTS`.

**Add a new report section:**

1. Add a rendering function in `src/reporting/pdf_report.py`.
2. Call it from the report builder's main loop.

## License

Internal / Proprietary
