# KoKe — Orienteering Series Calculator

Points calculator and results manager for [Koneen Kerho ry](https://www.kokesuunnistus.net/) orienteering division series competitions.

## Overview

The tool processes race results from multiple events, calculates series points, and generates HTML result pages. Each series (e.g. `päivä`, `yö`) has its own config with registered participants, scoring rules, and source files for each event.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

## Project Structure

```
├── parseri/
│   ├── main.py          # Interactive CLI frontend
│   ├── parseri.py        # Points calculator & HTML generator
│   ├── downloader.py     # Results downloader (HTML & Navisport)
│   └── simpletable.py    # HTML table generator
├── 2025/
│   ├── paiva/
│   │   ├── config.yaml   # Series config (participants, rules)
│   │   ├── sources/      # Event result YAML files
│   │   └── results/      # Generated HTML output
│   └── yo/
│       ├── config.yaml
│       ├── sources/
│       └── results/
└── pyproject.toml
```

## Usage

### Add a new event (interactive)

The easiest way to add an event is through the interactive frontend:

```bash
uv run parseri/main.py 2025/paiva
```

This will:
1. Show the series summary
2. Offer to add a new event or recalculate points
3. Download and parse results automatically
4. Ask for series mapping and metadata (with smart defaults)
5. Save the source YAML and recalculate all points

### Calculate points

To recalculate points for all events in a series:

```bash
uv run parseri/parseri.py 2025/paiva/config.yaml
```

Options:
- `-s FOLDER` — custom sources folder (default: `sources/` next to config)
- `-r FOLDER` — custom results output folder (default: `results/` next to config)
- `-c` — copy results via scp to the destination defined in config

### Download results manually

To download results from a URL and generate a source YAML file:

```bash
uv run parseri/downloader.py <url> [-o OUTPUT_DIR]
```

Supported sources:
- Generic HTML pages (EResults and similar)
- [Navisport](https://navisport.com) JSON API

## Scoring Rules

- The participant finishing in the **reference position** gets **1000 points**
- If fewer participants than the threshold, the **winner** gets 1000 points
- Winner is capped at **1050 points**; faster finishers scale proportionally
- Every starter gets at least **500 points** (minimum)
- **1 point** per 10 seconds of time difference
- Best N results count toward the series total (configured per series)

## Configuration

### Hardcoded series assignment

Participants are listed directly under each series:

```yaml
series:
    pitkä:
        participant_threshold: 6
        reference_position: 3
        participants:
            - {last: Aaltonen, first: Tero}
            - {last: Viero, first: Jukka}
    lyhyt:
        participant_threshold: 6
        reference_position: 3
        participants:
            - {last: Salmi, first: Veijo}
```

### Automatic series detection

Instead of manually assigning each participant to a series, you can place them under `series.auto.participants`. The tool scans all event source files and assigns each participant to the series whose track they have run most often:

```yaml
series:
    auto:
        participants:
            - {last: Aaltonen, first: Tero}
            - {last: Viero, first: Jukka}
            - {last: Salmi, first: Veijo}
    pitkä:
        participant_threshold: 6
        reference_position: 3
    lyhyt:
        participant_threshold: 6
        reference_position: 3
```

You can mix both approaches — some participants under `auto` and others hardcoded under a specific series.

### Competitor name aliases

If a competitor's name sometimes appears in alternate forms in result data (typos, abbreviations, different transliterations), you can define aliases on the participant entry:

```yaml
participants:
    - {last: Jokelainen, first: Visa, aliases: [{last: Jokelaansen, first: Visa}]}
    - {last: Krüger, first: Andrei, aliases: [{last: Kruger, first: Andrei}, {last: Krüger, first: Andre}]}
```

When results contain an entry matching an alias, the result is attributed to the participant's main name. Main name always takes priority if both exist. Aliases work in both hardcoded and `auto` series modes.
