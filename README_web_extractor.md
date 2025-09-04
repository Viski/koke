# Web Page Text Extractor

A Python tool for fetching web pages and extracting their text content to simple txt files.

## Overview

This tool (`web_page_extractor.py`) is designed to fetch web pages and extract their readable text content, saving it to text files for further processing. It's useful for:

- Extracting content from web pages for analysis
- Converting web content to plain text format
- Batch processing of web URLs
- Creating text archives of web content

## Features

- Extracts clean text content from web pages
- Removes HTML tags, scripts, and styling
- Cleans up whitespace and formatting
- Handles various text encodings
- Auto-generates appropriate filenames based on URL
- Shows preview of extracted content
- Configurable request timeout
- Error handling for network issues

## Requirements

- Python 3.6+
- `requests` library
- `beautifulsoup4` library

## Installation

The required libraries can be installed using pip:

```bash
pip install requests beautifulsoup4
```

## Usage

### Basic Usage

```bash
python web_page_extractor.py <url>
```

### Specify Output File

```bash
python web_page_extractor.py <url> <output_file>
```

### Examples

Extract content from a website (auto-generated filename):
```bash
python web_page_extractor.py https://example.com
```

Extract content with custom filename:
```bash
python web_page_extractor.py https://navisport.com/events/6b72e840-b6c6-4a0a-83e2-bcff31c3db04/results/50b7098a-d794-4027-91ca-b025cb2f6095 results.txt
```

Set custom timeout and disable preview:
```bash
python web_page_extractor.py https://example.com --timeout 60 --no-preview
```

### Command Line Options

- `url` - The URL to fetch (required)
- `output_file` - Output filename (optional, auto-generated if not provided)
- `--timeout TIMEOUT` - Request timeout in seconds (default: 30)
- `--no-preview` - Skip content preview output

## Output

The tool creates text files containing the extracted content with:
- All HTML tags removed
- Clean text formatting
- Proper line breaks
- UTF-8 encoding

## Limitations

This tool fetches the initial HTML content of web pages. For pages that load content dynamically with JavaScript after the initial page load, the extracted text may not include all content. In such cases, you may need browser automation tools like Selenium.

## Example Output

When run successfully, the tool will output:
```
Auto-generated output filename: example_com.txt
Fetching: https://example.com
Retrieved 1234 characters
Extracting text content...
Content saved to: example_com.txt
File size: 456 bytes
Successfully extracted 456 characters

Content preview (first 15 lines):
============================================================
 1: Example Domain
 2: This domain is for use in illustrative examples...
 3: More information...
============================================================

Complete content saved to: example_com.txt
```

## Integration with KoKe Project

This tool is a standalone addition to the KoKe orienteering results processing project. It can be used to:
- Extract results from web-based competition systems
- Archive competition information
- Process text data for further analysis

The tool does not modify any existing functionality in the KoKe project.