#!/usr/bin/env python3
"""
Test the web extractor with different scenarios.
"""

import sys
import os
import tempfile

# Add parseri directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'parseri'))

from simple_extractor import SimpleRaceExtractor
from extract_web_results import parse_race_results, display_results_formatted


def test_with_mock_html():
    """Test extractor with mock HTML content."""
    print("Testing with mock HTML content...")
    
    # Create mock HTML that might be found on a race results page
    mock_html = """
    <html>
    <body>
        <h1>Race Results</h1>
        <table class="results">
            <tr><th>Pos</th><th>Name</th><th>Team</th><th>Time</th></tr>
            <tr><td>1.</td><td>John Smith</td><td>Team A</td><td>45:30</td></tr>
            <tr><td>2.</td><td>Jane Doe</td><td>Team B</td><td>47:15</td></tr>
            <tr><td>3.</td><td>Bob Wilson</td><td>Team A</td><td>49:22</td></tr>
        </table>
    </body>
    </html>
    """
    
    # Create a temporary HTML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(mock_html)
        temp_file = f.name
    
    try:
        # Test extraction using file:// URL
        file_url = f"file://{temp_file}"
        extractor = SimpleRaceExtractor()
        
        # This should work since it's a local file
        results_data = extractor.extract_results(file_url)
        print("Raw extracted data:")
        print(results_data)
        print()
        
        if results_data:
            parsed_results = parse_race_results(results_data)
            print("Parsed results:")
            for name, data in parsed_results.items():
                print(f"  {name}: {data}")
        else:
            print("No results extracted from mock HTML")
            
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        # Clean up
        os.unlink(temp_file)


def test_parsing_formats():
    """Test different input data formats."""
    print("\nTesting different input formats...")
    
    test_cases = [
        # Standard format
        "1    John Smith    Team A    45:30",
        
        # Without team
        "2    Jane Doe    47:15",
        
        # With time difference
        "3    Bob Wilson    Team B    49:22    + 3:52",
        
        # With leading/trailing spaces
        "  4    Alice Brown    Team C    52:10  ",
        
        # Hour:minute:second format
        "5    Charlie Davis    Team D    1:05:45",
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest case {i}: '{test_case}'")
        try:
            results = parse_race_results(test_case)
            for name, data in results.items():
                print(f"  Parsed: {name} -> {data}")
        except Exception as e:
            print(f"  Error: {e}")


def main():
    """Run all tests."""
    print("Web Results Extractor - Test Suite")
    print("=" * 40)
    
    # Test 1: Mock HTML extraction
    test_with_mock_html()
    
    # Test 2: Parsing formats
    test_parsing_formats()
    
    print("\n" + "=" * 40)
    print("Test suite completed.")


if __name__ == "__main__":
    main()