# Race Results Web Extractor

This directory contains tools for extracting race results from JavaScript-rendered web pages and converting them to a format compatible with the KoKe orienteering parser.

## Files

- **extract_web_results.py** - Main command-line tool for extracting and displaying race results
- **simple_extractor.py** - Core extraction logic using HTTP requests first, with Selenium fallback
- **extractor.py** - Advanced Selenium-based extractor for complex JavaScript sites
- **web_results_parser.py** - Alternative parser interface

## Usage

### Basic Usage

```bash
# Extract and display race results in KoKe format
python3 extract_web_results.py "https://example.com/race-results"

# Show raw extracted data
python3 extract_web_results.py "https://example.com/race-results" --format raw

# Show parsed data structure
python3 extract_web_results.py "https://example.com/race-results" --format parsed
```

### Navisport.com Support

The extractor specifically supports navisport.com race results pages:

```bash
python3 extract_web_results.py "https://navisport.com/events/.../results/..."
```

### Integration with Existing Parser

The extracted data is compatible with the existing `parseri.py` parseResults() function format:

```
position    first_name last_name    team    time
```

## Expected Output Format

The extractor produces output matching the KoKe orienteering parser format:

```
    Tapahtuman etusivu
    Tulokset
    Väliajat

A|
Hyvinkään Iltarastit 2025, Paukunharju/2024
A
6.53 km
Hyväksytty 9
Hylätty 0
Keskeytti 0
Osallistujat 9

    1    Orrainen Severi    HyRa    56:27
    2    Pasi Romppainen    Hyvinkään Rasti    56:29    + 2
    3    Mika Similä    Hyvinkään Rasti    57:56    + 1:29
    ...
```

## Dependencies

- requests - for HTTP requests
- beautifulsoup4 - for HTML parsing
- lxml - for XML/HTML parsing
- selenium - for JavaScript rendering (optional)

Install with:
```bash
pip install requests beautifulsoup4 lxml selenium
```

## Architecture

1. **Simple HTTP First**: Tries to extract results using simple HTTP requests and HTML parsing
2. **JavaScript Fallback**: Falls back to Selenium-based rendering for dynamic content
3. **Format Compatibility**: Ensures extracted data works with existing KoKe parser infrastructure

## Extending Support

To add support for new race result websites:

1. Add URL detection logic in the extractor
2. Implement site-specific parsing in `_parse_results_html()`
3. Test with the site's specific HTML structure

The extractor uses multiple parsing strategies:
- Table-based extraction
- Pattern matching for race result text
- Flexible name/team/time field detection