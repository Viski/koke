# Copilot Instructions — KoKe Orienteering Series Calculator

## Build & Test

```bash
# Run all tests
uv run pytest parseri/tests/

# Run a single test class or method
uv run pytest parseri/tests/test_parseri.py::TestCalculatePoints
uv run pytest parseri/tests/test_parseri.py::TestFormatTime::test_minutes_seconds_dot

# Calculate points for a series
uv run parseri/parseri.py 2026/paiva/config.yaml

# Interactive CLI (add events, recalculate)
uv run parseri/main.py 2026/paiva
```

No linter or type-checker is configured.

## Architecture

The system processes orienteering race results through a pipeline:

1. **Download** (`parseri/downloader.py`) — Fetches results from HTML pages or Navisport JSON API, parses them into a structured format, and writes source YAML files.
2. **Calculate** (`parseri/parseri.py`) — Reads a series `config.yaml` + all source YAML files from `sources/`, calculates points per scoring rules, and generates HTML result tables.
3. **Interactive frontend** (`parseri/main.py`) — CLI that orchestrates downloading + calculating in one flow.

### Data flow

```
Web URL → downloader → sources/NN_location.yaml → parseri → results/*.html
                              ↑                        ↑
                     config.yaml (participants,    config.yaml (series rules,
                      series mapping)               thresholds)
```

### Year/series directory convention

Each competition year has directories like `2026/paiva/` and `2025/yo/` containing:
- `config.yaml` — Participants, series definitions, scoring parameters
- `sources/` — One YAML file per event (numbered `01_Location.yaml`, `02_...`)
- `results/` — Generated HTML output (committed to repo, served as static pages)

## Key Conventions

- **Python 3.12+** with **uv** as the package manager. Always use `uv run` to execute scripts.
- **Source YAML format**: Each event file has `event_number`, `location`, `date`, `organizer`, `source_url`, `firstname_first`, `series_mapping`, and `tracks` with embedded plaintext result data.
- **`firstname_first`**: Controls name parsing order. `true` = data is "Firstname Lastname". `false` = data is "Lastname Firstname" (default for Navisport). Legacy files may use `reverse_names` (same semantics, mapped automatically).
- **Series auto-assignment**: Participants listed under `series.auto.participants` are assigned to whichever series (track) they ran most often across all events.
- **Name aliases**: Participants can have `aliases` list for alternate spellings; the main name always takes priority.
- **Scoring**: Reference position gets 1000 pts, winner capped at 1050, minimum 500 pts for starters, 1 point per 10 seconds difference.
- **`simpletable.py`** is a vendored third-party module — avoid modifying it unless necessary.
- **Result HTML files are committed** to the repo (they are the published output).
