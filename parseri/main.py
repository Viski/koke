#!/usr/bin/env python3
"""
Interactive CLI frontend for KoKe orienteering series management.

Usage:
    python main.py <config_or_folder>

    config_or_folder: Path to config.yaml or the series base folder.

Example:
    uv run parseri/main.py 2025/paiva
    uv run parseri/main.py 2025/paiva/config.yaml
"""

import argparse
import os
import re
import subprocess
import sys

import yaml

# Ensure the parseri package directory is on the path so we can import downloader
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from downloader import (
    detect_source,
    fetch_html_page,
    generate_yaml,
    parse_html_results,
    parse_navisport_results,
    prompt_metadata,
    prompt_name_order,
    prompt_series_mapping,
    write_yaml_file,
)


def resolve_config_path(path):
    """Resolve a config.yaml path from a file or directory argument."""
    if os.path.isdir(path):
        config_path = os.path.join(path, "config.yaml")
    else:
        config_path = path

    if not os.path.isfile(config_path):
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    return config_path


def detect_next_event_number(sources_dir):
    """Scan sources/ for existing YAML files and return the next event number."""
    if not os.path.isdir(sources_dir):
        return 1

    max_num = 0
    for filename in os.listdir(sources_dir):
        if not filename.endswith(".yaml"):
            continue
        match = re.match(r'^(\d+)_', filename)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    return max_num + 1


def show_series_summary(config, sources_dir):
    """Print a brief summary of the series."""
    name = config.get("name", "?")
    year = config.get("year", "?")
    num_events = config.get("number_of_events", "?")

    existing = 0
    if os.path.isdir(sources_dir):
        existing = len([f for f in os.listdir(sources_dir) if f.endswith(".yaml")])

    series_names = list(config.get("series", {}).keys())

    print(f"\n{'='*50}")
    print(f"  Series: {name} {year}")
    print(f"  Tracks: {', '.join(series_names)}")
    print(f"  Events: {existing} / {num_events}")
    print(f"{'='*50}")


def add_event(config, config_path, sources_dir):
    """Interactive flow for adding a new event to the series."""
    import requests

    # 1. Prompt for URL
    url = input("\nResults URL: ").strip()
    if not url:
        print("No URL provided, aborting.")
        return

    # 2. Download and parse
    source_type = detect_source(url)
    print(f"Downloading results from {url}...")

    try:
        if source_type == "navisport":
            tracks, auto_metadata = parse_navisport_results(url)
        else:
            html = fetch_html_page(url)
            tracks, auto_metadata = parse_html_results(html)
    except requests.RequestException as e:
        print(f"Error downloading results: {e}", file=sys.stderr)
        return

    if not tracks:
        print("Error: No tracks found in the results page.", file=sys.stderr)
        return

    # 3. Show track summary
    track_names = list(tracks.keys())
    print(f"\nFound {len(track_names)} tracks: {', '.join(track_names)}")
    for name, data in tracks.items():
        count = len(data["results"])
        length = f" ({data['length']})" if data.get("length") else ""
        print(f"  {name}{length}: {count} results")

    # 4. Interactive prompts
    series_mapping = prompt_series_mapping(track_names)

    # Auto-detect event number
    next_num = detect_next_event_number(sources_dir)
    auto_metadata["event_number_suggestion"] = next_num

    metadata = prompt_metadata_with_auto_number(auto_metadata, next_num)

    # 5. Generate YAML — downloader determines reverse_names for known sources
    doc = generate_yaml(metadata, tracks, series_mapping, url, source_type=source_type)

    # If reverse_names was not set by the downloader, prompt the user
    if "reverse_names" not in doc:
        doc["reverse_names"] = prompt_name_order(tracks)

    num = metadata.get("event_number")
    loc = metadata.get("location", "unknown")
    loc_clean = re.sub(r'[^\w\-]', '_', loc)
    if num:
        filename = f"{int(num):02d}_{loc_clean}.yaml"
    else:
        filename = f"{loc_clean}.yaml"

    os.makedirs(sources_dir, exist_ok=True)
    filepath = os.path.join(sources_dir, filename)

    if os.path.exists(filepath):
        overwrite = input(f"\n{filepath} already exists. Overwrite? [y/N]: ").strip().lower()
        if overwrite != "y":
            print("Aborted.")
            return

    write_yaml_file(doc, filepath)

    # 6. Run parseri to recalculate
    run_parseri(config_path)


def prompt_metadata_with_auto_number(auto_metadata, suggested_number):
    """Prompt for metadata with auto-detected event number."""
    from downloader import input_with_default

    print("\nEvent metadata:")

    event_number = input_with_default("  Event number", str(suggested_number))
    if event_number:
        event_number = int(event_number)

    location = input_with_default("  Location", auto_metadata.get("title"))
    date = input_with_default("  Date", auto_metadata.get("date"))
    organizer = input_with_default("  Organizer", None)

    return {
        "event_number": event_number,
        "location": location,
        "date": date,
        "organizer": organizer,
    }


def run_parseri(config_path):
    """Run parseri.py to recalculate all points."""
    parseri_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parseri.py")

    print(f"\n{'─'*50}")
    print("Running parseri to recalculate points...")
    print(f"{'─'*50}\n")

    result = subprocess.run(
        [sys.executable, parseri_path, config_path],
        cwd=os.getcwd(),
    )

    if result.returncode != 0:
        print(f"\nParseri exited with error (code {result.returncode})", file=sys.stderr)
    else:
        print(f"\n{'─'*50}")
        print("Done! Points recalculated successfully.")
        print(f"{'─'*50}")


def main():
    parser = argparse.ArgumentParser(
        description="Interactive CLI frontend for KoKe orienteering series management."
    )
    parser.add_argument(
        "config",
        help="Path to config.yaml or the series base folder",
    )
    args = parser.parse_args()

    config_path = resolve_config_path(args.config)
    base_dir = os.path.dirname(config_path)
    sources_dir = os.path.join(base_dir, "sources")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    show_series_summary(config, sources_dir)

    print("\nActions:")
    print("  [1] Add event")
    print("  [2] Recalculate points")
    print("  [q] Quit")

    choice = input("\nChoice: ").strip().lower()
    if choice in ("1", "add", "add event"):
        add_event(config, config_path, sources_dir)
    elif choice in ("2", "recalculate"):
        run_parseri(config_path)
    elif choice in ("q", "quit", "exit"):
        print("Bye!")
    else:
        print(f"Unknown choice: {choice}")


if __name__ == "__main__":
    main()
