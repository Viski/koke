# KoKe Race Results Web Extractor

This enhancement adds web extraction capabilities to the KoKe orienteering race results parser, enabling it to work with JavaScript-rendered pages like navisport.com.

## Problem Solved

The existing parser only worked with static YAML files. This extension allows extraction of race results directly from dynamic web pages, specifically addressing the issue with navisport.com results pages that require JavaScript to render content.

## Solution

The implementation provides a two-tier approach:

1. **HTTP-first extraction**: Attempts to extract results using simple HTTP requests and HTML parsing
2. **JavaScript fallback**: Uses Selenium WebDriver for sites requiring JavaScript rendering

## Usage

### Command Line Tool

```bash
# Extract and display results in KoKe format
python3 extract_web_results.py "https://navisport.com/events/.../results/..."

# Show different output formats
python3 extract_web_results.py URL --format raw      # Raw extracted data
python3 extract_web_results.py URL --format parsed   # Parsed data structure
python3 extract_web_results.py URL --format display  # Formatted output (default)
```

### Example Output

For the navisport.com URL from the issue:
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
    2    Pasi Romppainen    Hyvinkään Rasti    56:29    + 0:02
    3    Mika Similä    Hyvinkään Rasti    57:56    + 1:29
    4    Pietari Marko    HyRa    1:05:51    + 9:24
    5    Ustinov Jarkko    Seura    1:08:37    + 12:10
    6    Viero Jukka    Hyvinkään Rasti    1:15:08    + 18:41
    7    Aaltonen Tero        1:25:55    + 29:28
    8    Poussu Jukka    KoKe    1:30:11    + 33:44
    9    Ahoniemi Sakke    Hyvinkään Rasti    1:36:04    + 39:37
```

## Files Added

- **extract_web_results.py** - Main command-line extractor tool
- **parseri/simple_extractor.py** - Core HTTP-based extraction logic
- **parseri/extractor.py** - Advanced Selenium-based extractor
- **parseri/web_results_parser.py** - Alternative parser interface
- **parseri/README.md** - Detailed technical documentation
- **test_extractor.py** - Test suite for the extraction functionality

## Dependencies

```bash
pip install requests beautifulsoup4 lxml selenium unidecode pyyaml
```

For full JavaScript support, Chrome/Chromium browser is also needed for Selenium.

## Architecture

### Compatibility Layer
The extractor produces output in the same format expected by the existing `parseResults()` function:

```
position    first_name last_name    team    time
```

### Multi-Strategy Parsing
- Table-based HTML extraction
- Text pattern matching
- Flexible field detection for different website layouts
- Robust error handling and fallbacks

### Integration
The extractor integrates seamlessly with the existing KoKe parser infrastructure while adding new web capabilities.

## Testing

```bash
# Run the test suite
python3 test_extractor.py

# Test different output formats
python3 extract_web_results.py URL --format raw
python3 extract_web_results.py URL --format parsed
python3 extract_web_results.py URL --format display
```

## Extending Support

To add support for additional race result websites:

1. Add URL detection logic in `simple_extractor.py`
2. Implement site-specific parsing methods
3. Test with the site's HTML structure
4. Add to the test suite

The extractor uses multiple parsing strategies to handle different website formats automatically.