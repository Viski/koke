#!/usr/bin/env python3
"""
Web Page Text Extractor
Fetches web pages and extracts text content to simple txt files.

This tool is designed to fetch web pages and extract their readable text content,
saving it to text files for further processing. It handles basic HTML parsing
and text cleaning.

Usage:
    python web_page_extractor.py <url> [output_file]

Examples:
    python web_page_extractor.py https://example.com
    python web_page_extractor.py https://navisport.com/events/6b72e840-b6c6-4a0a-83e2-bcff31c3db04/results/50b7098a-d794-4027-91ca-b025cb2f6095 results.txt

Features:
    - Extracts text content from web pages
    - Removes HTML tags and formatting
    - Cleans up whitespace and formatting
    - Handles various text encodings
    - Generates appropriate filenames automatically
    - Shows preview of extracted content

Note: This tool fetches the initial HTML content. For pages that load content
dynamically with JavaScript, you may need additional tools or browser automation.
"""

import argparse
import os
import sys
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


def fetch_page_content(url, timeout=30):
    """Fetch the content of a web page using HTTP requests"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        print(f"Fetching: {url}")
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        print(f"Retrieved {len(response.text)} characters")
        return response.text
    except requests.exceptions.Timeout:
        print(f"Error: Request timed out after {timeout} seconds")
        return None
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP {e.response.status_code} - {e.response.reason}")
        return None
    except Exception as e:
        print(f"Error fetching page: {e}")
        return None


def extract_text_content(html_content):
    """Extract readable text content from HTML"""
    if not html_content:
        return ""
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style", "meta", "link"]):
        script.extract()
    
    # Get text content
    text = soup.get_text()
    
    # Clean up text
    # Split into lines and strip whitespace
    lines = (line.strip() for line in text.splitlines())
    
    # Break multi-spaces into chunks and strip whitespace
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    
    # Remove empty lines and join
    text = '\n'.join(chunk for chunk in chunks if chunk)
    
    return text


def generate_output_filename(url):
    """Generate a suitable output filename based on the URL"""
    parsed_url = urlparse(url)
    
    # Use domain and path to create filename
    domain = parsed_url.netloc.replace('.', '_')
    path = parsed_url.path.replace('/', '_').replace('-', '_')
    
    # Remove query parameters and fragment
    if parsed_url.query:
        path += "_" + parsed_url.query.replace('=', '_').replace('&', '_')
    
    # Clean up filename - keep only alphanumeric, underscores, hyphens, and dots
    filename = f"{domain}{path}.txt"
    filename = re.sub(r'[^\w\-_.]', '', filename)
    
    # Remove multiple underscores
    filename = re.sub(r'_+', '_', filename)
    
    # Ensure it's not too long (filesystem limit consideration)
    if len(filename) > 150:
        filename = filename[:150] + ".txt"
    
    # Ensure it ends with .txt
    if not filename.endswith('.txt'):
        filename += '.txt'
    
    # Ensure it's not empty
    if filename == '.txt':
        filename = 'webpage_content.txt'
    
    return filename


def save_text_to_file(text, filename):
    """Save text content to a file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True) if os.path.dirname(filename) else None
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"Content saved to: {filename}")
        
        # Show file size
        file_size = os.path.getsize(filename)
        print(f"File size: {file_size} bytes")
        
        return True
    except Exception as e:
        print(f"Error saving to file: {e}")
        return False


def show_content_preview(text, max_lines=15):
    """Show a preview of the extracted content"""
    if not text.strip():
        print("No content to preview")
        return
    
    preview_lines = text.split('\n')[:max_lines]
    print(f"\nContent preview (first {min(len(preview_lines), max_lines)} lines):")
    print("=" * 60)
    
    for i, line in enumerate(preview_lines, 1):
        if line.strip():
            # Truncate very long lines
            display_line = line[:100] + "..." if len(line) > 100 else line
            print(f"{i:2d}: {display_line}")
    
    total_lines = len([l for l in text.split('\n') if l.strip()])
    if total_lines > max_lines:
        print(f"... ({total_lines - max_lines} more lines)")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Extract text content from web pages and save to txt files",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('url', help='URL to fetch')
    parser.add_argument('output_file', nargs='?', help='Output filename (optional, auto-generated if not provided)')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds (default: 30)')
    parser.add_argument('--no-preview', action='store_true', help='Skip content preview')
    
    args = parser.parse_args()
    
    # Validate URL
    if not args.url.startswith(('http://', 'https://')):
        print("Error: URL must start with http:// or https://")
        print(f"Got: {args.url}")
        sys.exit(1)
    
    # Determine output filename
    if args.output_file:
        output_filename = args.output_file
    else:
        output_filename = generate_output_filename(args.url)
        print(f"Auto-generated output filename: {output_filename}")
    
    # Fetch page content
    html_content = fetch_page_content(args.url, timeout=args.timeout)
    if not html_content:
        print("Failed to fetch page content")
        sys.exit(1)
    
    # Extract text content
    print("Extracting text content...")
    text_content = extract_text_content(html_content)
    
    if not text_content.strip():
        print("Warning: No text content extracted from page")
        print("This could mean:")
        print("- The page is empty")
        print("- The content is loaded dynamically with JavaScript")
        print("- The page structure is unusual")
    
    # Save to file
    success = save_text_to_file(text_content, output_filename)
    if not success:
        sys.exit(1)
    
    print(f"Successfully extracted {len(text_content)} characters")
    
    # Show preview unless disabled
    if not args.no_preview:
        show_content_preview(text_content)
    
    print(f"\nComplete content saved to: {output_filename}")


if __name__ == "__main__":
    main()