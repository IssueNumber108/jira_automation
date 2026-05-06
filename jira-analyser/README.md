# jira-analyser

A modular Python toolkit for bulk Jira issue analysis — fetch, inspect fields, validate values, and produce charts — all wired in a sequential pipeline.

## Project layout

```
src/jira_analyser/
├── cert/        certificate generation (cryptography)
├── client/      httpx Jira REST API v2 client with retry
├── config/      pydantic-settings — loads .env
├── fields/      field discovery (standard + custom), select/exclude
├── filters/     bulk issue fetcher, auto-pagination
├── pipeline/    orchestrator (runner.py) + Typer CLI (cli.py)
├── plotting/    8 chart types via matplotlib / seaborn
├── utils/       shared domain models, rich logging
└── validation/  field presence + allowed-value checks
tests/unit/      28 pure-logic tests (no network required)
examples/        end-to-end usage example
```

## Quickstart

```bash
pip install uv
git clone <repo> && cd jira-analyser
uv sync                          # install from uv.lock into .venv

cp .env.example .env             # fill in JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_CERT_PATH

# generate a self-signed cert (dev only)
uv run jira-analyser cert --out-dir certs/ --cn your-org.atlassian.net

# run the pipeline
uv run jira-analyser run \
    --filter 12345 --filter 67890 \
    --chart "bar:status" \
    --chart "stacked_bar:status:priority" \
    --chart "time_series:created" \
    --chart burndown \
    --output-dir outputs/
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `JIRA_URL` | ✓ | — | Jira base URL |
| `JIRA_EMAIL` | ✓ | — | Account email |
| `JIRA_API_TOKEN` | ✓ | — | API token / PAT |
| `JIRA_CERT_PATH` | ✓ | — | Path to PEM certificate |
| `JIRA_MAX_RESULTS_PER_PAGE` | | 100 | Page size |
| `JIRA_REQUEST_TIMEOUT` | | 30 | Request timeout (s) |
| `JIRA_MAX_RETRIES` | | 3 | Retry attempts |
| `OUTPUT_DIR` | | outputs/ | Chart output directory |

## Chart spec format

`--chart type:field[:field2]`  — examples:

| Spec | Output |
|---|---|
| `bar:status` | Horizontal bar — value counts |
| `stacked_bar:status:priority` | Stacked bar |
| `pie:priority` | Pie chart |
| `time_series:created` | Line — issues over time |
| `heatmap:status:assignee` | Cross-tab heatmap |
| `scatter:story_points:time_spent` | Scatter |
| `histogram:story_points` | Distribution histogram |
| `burndown` | Cumulative open vs closed |

## Development

```bash
uv sync --all-extras
uv run pytest                  # 28 unit tests
uv run ruff check src tests
uv run mypy
```
