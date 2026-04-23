#!/usr/bin/env python3
"""
Downloader module for KoKe orienteering race results.

Downloads results from web pages and generates YAML source files
for use with parseri.py.

Supported sources:
- Generic HTML pages (EResults and similar, default for all URLs)
- Navisport JSON API (navisport.com only)

Usage:
    python downloader.py <url> [-o OUTPUT_DIR]
"""

import argparse
import re
import sys
from urllib.parse import urlparse

import requests
import yaml
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Source detection
# ---------------------------------------------------------------------------

def detect_source(url):
    """Detect the result source type from the URL domain."""
    host = urlparse(url).hostname or ""
    if "navisport.com" in host:
        return "navisport"
    return "html"


# ---------------------------------------------------------------------------
# Generic HTML backend
# ---------------------------------------------------------------------------

def fetch_html_page(url):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def parse_html_results(html):
    """Parse an HTML results page (EResults-style).

    Returns (tracks, metadata) where:
      tracks: dict of {track_name: {length, results: [...]}}
      metadata: dict with auto-detected fields (date, title)
    """
    soup = BeautifulSoup(html, "html.parser")
    metadata = {}

    # Try to extract title / date from <H2>
    h2 = soup.find("h2")
    if h2:
        text = h2.get_text(strip=True)
        # Common format: "Location, map info DD.MM.YYYY - ..."
        date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', text)
        if date_match:
            full_date = date_match.group(1)
            # Store as D.M. (without year)
            parts = full_date.split('.')
            metadata["date"] = f"{int(parts[0])}.{int(parts[1])}."
        metadata["title"] = text.split(" - ")[0].strip() if " - " in text else text

    tracks = {}
    current_track = None
    current_length = None

    for element in soup.find_all(["h3", "pre"]):
        if element.name == "h3":
            track_text = element.get_text(strip=True)
            # Parse "Rata A 5,3km" or "A 5,3 km"
            match = re.match(
                r'(?:Rata\s+)?(\S+)\s+([\d,]+\s*km)',
                track_text,
                re.IGNORECASE
            )
            if match:
                current_track = match.group(1)
                current_length = match.group(2)
                # Normalize: ensure space before km
                current_length = re.sub(r'\s*km', ' km', current_length)
            else:
                # Fall back: use whole text as track name
                current_track = track_text
                current_length = ""

        elif element.name == "pre" and current_track:
            results = parse_html_track_results(element.get_text())
            tracks[current_track] = {
                "length": current_length,
                "results": results,
            }
            current_track = None

    return tracks, metadata


def parse_html_track_results(pre_text):
    """Parse results from a <PRE> block.

    Returns list of dicts: {position, name, club, time, timediff, status}
    """
    results = []
    for line in pre_text.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue

        # Skip info lines like "(Lähti: 25, Keskeytti: 0, Hylätty: 0)"
        if stripped.startswith('(') and stripped.endswith(')'):
            continue

        # Parse result line. Formats:
        #   1. Lastname Firstname                                        24.49
        #   1. Lastname Firstname           Club                         24.49    +03.23
        #      Lastname Firstname                                       ei aikaa
        #      Lastname Firstname                                         hyl.

        # Try to match a positioned result
        match = re.match(
            r'^\s*(\d+)\.\s+'       # position
            r'(.+?)\s{2,}'          # name (+ optional club, separated by 2+ spaces)
            r'(\d[\d.:]+)'          # time
            r'(?:\s+(\+[\d.:]+))?'  # optional time diff
            r'\s*$',
            line
        )
        if match:
            pos = int(match.group(1))
            name_club = match.group(2).strip()
            time_str = match.group(3)
            timediff = match.group(4) or ""

            name, club = split_name_club(name_club)
            results.append({
                "position": pos,
                "name": name,
                "club": club,
                "time": time_str,
                "timediff": timediff,
                "status": "ok",
            })
            continue

        # Try to match "ei aikaa" (DNF)
        match = re.match(
            r'^\s*(?:(\d+)\.\s+)?'  # optional position
            r'(.+?)\s{2,}'          # name (+ optional club)
            r'ei\s+aikaa'           # no time marker
            r'\s*$',
            line,
            re.IGNORECASE,
        )
        if match:
            name_club = match.group(2).strip()
            name, club = split_name_club(name_club)
            results.append({
                "position": None,
                "name": name,
                "club": club,
                "time": None,
                "timediff": "",
                "status": "dnf",
            })
            continue

        # Try to match "hyl." (disqualified)
        match = re.match(
            r'^\s*(?:(\d+)\.\s+)?'
            r'(.+?)\s{2,}'
            r'hyl\.'
            r'\s*$',
            line,
            re.IGNORECASE,
        )
        if match:
            name_club = match.group(2).strip()
            name, club = split_name_club(name_club)
            results.append({
                "position": None,
                "name": name,
                "club": club,
                "time": None,
                "timediff": "",
                "status": "dsq",
            })
            continue

    return results


def split_name_club(text):
    """Split 'Lastname Firstname   Club' into (name, club).

    The name and club are separated by 2+ spaces in the original HTML,
    but after our regex captures the group, internal multi-space gaps
    indicate a club follows.
    """
    # If there are 2+ consecutive spaces, split there
    parts = re.split(r'\s{2,}', text.strip())
    if len(parts) >= 2:
        return parts[0].strip(), parts[1].strip()
    # Handle comma-separated names like "Ahlqvist, Kristiina"
    return text.strip(), ""


# ---------------------------------------------------------------------------
# Navisport backend
# ---------------------------------------------------------------------------

NAVISPORT_API = "https://navisport.com/api"


def extract_navisport_slug(url):
    """Extract the event slug from a Navisport URL.

    URL pattern: /tapahtumat/<slug>/tulokset/<class>
    """
    path = urlparse(url).path
    match = re.search(r'/tapahtumat/([^/]+)', path)
    if not match:
        raise ValueError(f"Cannot extract event slug from URL: {url}")
    return match.group(1)


def resolve_navisport_event(slug):
    """Resolve a Navisport slug to event ID and metadata."""
    for term in _build_search_terms(slug):
        event = _search_for_slug(term, slug)
        if event:
            return event
    raise ValueError(f"Could not find Navisport event with slug: {slug}")


def _build_search_terms(slug):
    """Generate candidate API search terms from a Navisport event slug.

    Slug patterns:
      <series>-<YYYY>-<event-name>-<MM>-<DD>     (series includes year)
      <series>-<event-name>-<YYYY>-<MM>-<DD>      (date includes year)

    Event names may have a year suffix: "herunen2024" → "Herunen/2024".
    """
    parts = slug.split("-")
    terms = []

    # Strip trailing date MM-DD (two 2-digit segments)
    if (len(parts) >= 3
            and re.fullmatch(r'\d{2}', parts[-1])
            and re.fullmatch(r'\d{2}', parts[-2])):
        core = parts[:-2]
    else:
        core = list(parts)

    # Find event name: portion after the first standalone 4-digit year
    for i, p in enumerate(core):
        if re.fullmatch(r'\d{4}', p):
            name_parts = core[i + 1:]
            if name_parts:
                raw = "-".join(name_parts)
                # Handle year suffix: "herunen2024" → "Herunen/2024"
                m = re.match(r'^(.*?)(\d{4})$', raw)
                if m and m.group(1):
                    base = m.group(1).rstrip("-").replace("-", " ").title()
                    terms.append(f"{base}/{m.group(2)}")
                    terms.append(base)
                else:
                    terms.append(raw.replace("-", " ").title())
                # For multi-word names, also try first word as fallback
                if len(name_parts) > 1:
                    terms.append(name_parts[0].title())
            else:
                # Event name is before the year (e.g., series-name-YYYY-MM-DD)
                if i > 0 and not re.fullmatch(r'\d+', core[i - 1]):
                    terms.append(core[i - 1].title())
            break

    # Fallback: last non-numeric part of core
    if not terms:
        for p in reversed(core):
            if not re.fullmatch(r'\d+', p):
                terms.append(p.title())
                break

    return terms


def _search_for_slug(name, target_slug):
    """Search Navisport events by name, paginating to find exact slug match."""
    page_size = 100
    skip = 0
    while True:
        resp = requests.get(
            f"{NAVISPORT_API}/events",
            params={"name": name, "take": page_size, "skip": skip},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        events = data.get("events", [])
        for event in events:
            if event.get("slug") == target_slug:
                return event
        if len(events) < page_size:
            return None
        skip += page_size


def fetch_navisport_event_details(event_id):
    """Fetch full event details including course classes."""
    resp = requests.get(f"{NAVISPORT_API}/events/{event_id}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_navisport_results(event_id):
    """Fetch results for a Navisport event."""
    resp = requests.get(
        f"{NAVISPORT_API}/events/{event_id}/results",
        params={"format": "json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def format_seconds_to_time(seconds):
    """Convert seconds (int) to time string like '24.49' or '1.02.57'."""
    if not seconds or seconds <= 0:
        return None
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}.{m:02d}.{s:02d}"
    else:
        return f"{m}.{s:02d}"


def parse_navisport_results(url):
    """Fetch and parse results from Navisport.

    Returns (tracks, metadata).
    """
    slug = extract_navisport_slug(url)
    event_summary = resolve_navisport_event(slug)
    event_id = event_summary["id"]

    details = fetch_navisport_event_details(event_id)
    raw_results = fetch_navisport_results(event_id)

    # Build class ID → name mapping
    class_map = {}
    for cc in details.get("courseClasses", []):
        class_map[cc["id"]] = cc["name"]

    # Build course ID → info mapping
    course_map = {}
    for c in details.get("courses", []):
        course_map[c["id"]] = {
            "name": c.get("name", ""),
            "length": c.get("length"),
        }

    # Group results by class
    class_results = {}
    for r in raw_results:
        class_id = r.get("classId")
        if not class_id or class_id not in class_map:
            continue
        class_name = class_map[class_id]
        class_results.setdefault(class_name, []).append(r)

    # Build tracks
    tracks = {}
    for class_name, results in class_results.items():
        # Find course length for this class
        course_length = ""
        for r in results:
            cid = r.get("courseId")
            if cid and cid in course_map:
                length_m = course_map[cid].get("length")
                if length_m:
                    km = length_m / 1000
                    course_length = f"{km:.1f} km".replace(".", ",")
                break

        # Sort by position (None/0 last)
        results.sort(key=lambda x: x.get("position") or 99999)

        # Find winner time for time diffs
        winner_time = None
        for r in results:
            if r.get("status") == "Ok" and r.get("time", 0) > 0:
                winner_time = r["time"]
                break

        parsed = []
        for r in results:
            status_str = r.get("status", "")
            time_secs = r.get("time", 0)

            if status_str == "Ok" and time_secs > 0:
                time_str = format_seconds_to_time(time_secs)
                diff = r.get("difference", 0)
                if diff and diff > 0:
                    timediff = "+" + format_seconds_to_time(diff)
                else:
                    timediff = "+0.00"
                status = "ok"
                pos = r.get("position")
            else:
                time_str = None
                timediff = ""
                status = "dnf"
                pos = None

            parsed.append({
                "position": pos,
                "name": r.get("name", ""),
                "club": r.get("club", ""),
                "time": time_str,
                "timediff": timediff,
                "status": status,
            })

        tracks[class_name] = {
            "length": course_length,
            "results": parsed,
        }

    # Build metadata
    metadata = {
        "title": event_summary.get("name", ""),
    }
    begin = event_summary.get("begin", "")
    if begin:
        date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', begin)
        if date_match:
            d = int(date_match.group(3))
            m = int(date_match.group(2))
            metadata["date"] = f"{d}.{m}."

    return tracks, metadata


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------

def prompt_name_order(tracks):
    """Show sample names and ask the user about name order.

    Returns True if names are in "Lastname Firstname" order.
    """
    # Collect sample names
    samples = []
    for track_data in tracks.values():
        for r in track_data["results"]:
            if r["name"] and r["status"] == "ok":
                samples.append(r["name"])
            if len(samples) >= 5:
                break
        if len(samples) >= 5:
            break

    if not samples:
        return True

    print(f"\nSample names from results:")
    for s in samples[:5]:
        print(f"  {s}")

    while True:
        answer = input("\nName order? [L]astname Firstname / [F]irstname Lastname: ").strip().upper()
        if answer in ("L", ""):
            return True
        elif answer == "F":
            return False
        print("Please enter L or F.")


def prompt_series_mapping(track_names):
    """Prompt user to assign tracks to series.

    Returns dict like {"pitkä": "A", "lyhyt": "B"}.
    """
    print(f"\nAvailable tracks: {', '.join(track_names)}")
    print("Assign tracks to series (press Enter to skip):")

    mapping = {}
    for series in ["pitkä", "lyhyt"]:
        while True:
            answer = input(f"  {series} → which track? [{'/'.join(track_names)}]: ").strip()
            if not answer:
                break
            if answer in track_names:
                mapping[series] = answer
                break
            print(f"  Unknown track '{answer}'. Choose from: {', '.join(track_names)}")

    unmapped = [t for t in track_names if t not in mapping.values()]
    if unmapped:
        print(f"  Remaining tracks {', '.join(unmapped)} → available as 'other'")

    return mapping


def prompt_metadata(auto_metadata):
    """Prompt user for event metadata.

    auto_metadata may contain auto-detected 'date' and 'title'.
    """
    print("\nEvent metadata:")

    event_number = input_with_default("  Event number", None)
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


def input_with_default(prompt, default):
    """Prompt for input with an optional default value."""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    else:
        return input(f"{prompt}: ").strip()


# ---------------------------------------------------------------------------
# YAML output
# ---------------------------------------------------------------------------

def format_data_block(results):
    """Format results into a data block string for YAML."""
    lines = []
    for r in results:
        if r["status"] == "ok" and r["time"]:
            pos_str = f"{r['position']}." if r["position"] else "-"
            td = r["timediff"] if r["timediff"] else "+0.00"
            lines.append(f"{pos_str} {r['name']} {r['time']} {td}")
        else:
            lines.append(f"- {r['name']} - -")

    return "\n".join(lines) + "\n"


def generate_yaml(metadata, tracks, series_mapping, source_url, reverse_names=None, source_type=None):
    """Generate YAML content for the source file.

    reverse_names can be set explicitly, or determined automatically from source_type.
    Navisport data always uses Lastname Firstname order (reverse_names=False).
    """
    doc = {}

    if metadata.get("event_number"):
        doc["event_number"] = metadata["event_number"]
    if metadata.get("location"):
        doc["location"] = metadata["location"]
    if metadata.get("date"):
        doc["date"] = metadata["date"]
    if metadata.get("organizer"):
        doc["organizer"] = metadata["organizer"]
    if source_url:
        doc["source_url"] = source_url

    if reverse_names is not None:
        doc["reverse_names"] = reverse_names
    elif source_type == "navisport":
        doc["reverse_names"] = False

    if series_mapping:
        doc["series_mapping"] = series_mapping

    # Build tracks section
    tracks_doc = {}
    for track_name, track_data in tracks.items():
        track_entry = {}
        if track_data.get("length"):
            track_entry["length"] = track_data["length"]
        track_entry["data"] = format_data_block(track_data["results"])
        tracks_doc[track_name] = track_entry

    doc["tracks"] = tracks_doc
    return doc


def write_yaml_file(doc, filepath):
    """Write the YAML document to a file."""
    # Custom representer for multiline strings
    def str_representer(dumper, data):
        if '\n' in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    yaml.add_representer(str, str_representer)

    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(
            doc,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    print(f"\nOutput: {filepath} ✓")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Download orienteering race results and generate YAML source files."
    )
    parser.add_argument("url", help="URL of the results page")
    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Output directory (default: current directory)",
    )
    args = parser.parse_args()

    url = args.url
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
        sys.exit(1)

    if not tracks:
        print("Error: No tracks found in the results page.", file=sys.stderr)
        sys.exit(1)

    track_names = list(tracks.keys())
    print(f"Found {len(track_names)} tracks: {', '.join(track_names)}")
    for name, data in tracks.items():
        count = len(data["results"])
        length = f" ({data['length']})" if data.get("length") else ""
        print(f"  {name}{length}: {count} results")

    # Prompt for name order only when source type doesn't determine it
    reverse_names = None
    if source_type != "navisport":
        reverse_names = prompt_name_order(tracks)

    series_mapping = prompt_series_mapping(track_names)
    metadata = prompt_metadata(auto_metadata)

    doc = generate_yaml(metadata, tracks, series_mapping, url, reverse_names, source_type)

    # Generate output filename
    num = metadata.get("event_number")
    loc = metadata.get("location", "unknown")
    loc_clean = re.sub(r'[^\w\-]', '_', loc)
    if num:
        filename = f"{int(num):02d}_{loc_clean}.yaml"
    else:
        filename = f"{loc_clean}.yaml"

    import os
    filepath = os.path.join(args.output, filename)

    write_yaml_file(doc, filepath)


if __name__ == "__main__":
    main()
