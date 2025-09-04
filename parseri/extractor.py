#!/usr/bin/python
"""
Web extractor for JavaScript-rendered race results pages.

Supports extracting race results from dynamic JavaScript pages like navisport.com
and formats them for use with the existing parseri.py parser.
"""

import re
import time
from typing import Optional, List, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup


class RaceResultsExtractor:
    """Extractor for race results from JavaScript-rendered web pages."""
    
    def __init__(self, headless: bool = True, timeout: int = 30):
        """
        Initialize the extractor.
        
        Args:
            headless: Whether to run browser in headless mode
            timeout: Maximum time to wait for page elements to load
        """
        self.timeout = timeout
        self.driver = None
        self.headless = headless
        
    def _setup_driver(self):
        """Setup Chrome WebDriver with appropriate options."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(self.timeout)
        except Exception as e:
            raise WebDriverException(f"Failed to setup Chrome driver: {str(e)}")
    
    def _cleanup_driver(self):
        """Clean up WebDriver resources."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def extract_navisport_results(self, url: str) -> str:
        """
        Extract race results from a navisport.com URL.
        
        Args:
            url: The navisport.com results URL
            
        Returns:
            Formatted results string compatible with parseri.py parseResults()
            
        Raises:
            WebDriverException: If page loading fails
            TimeoutException: If elements don't load within timeout
        """
        if not self.driver:
            self._setup_driver()
        
        try:
            # Load the page
            self.driver.get(url)
            
            # Wait for results to load - look for results table or containers
            wait = WebDriverWait(self.driver, self.timeout)
            
            # Try multiple selectors that might contain the results
            results_selectors = [
                "table",
                ".results",
                ".result-list",
                "[class*='result']",
                "[class*='table']",
                "tbody tr",
                ".participant",
                ".competitor"
            ]
            
            results_element = None
            for selector in results_selectors:
                try:
                    results_element = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if not results_element:
                # If no specific results elements found, wait for page to fully load
                time.sleep(5)
            
            # Get page source after JavaScript execution
            page_source = self.driver.page_source
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract results data
            return self._parse_navisport_html(soup)
            
        except Exception as e:
            raise WebDriverException(f"Failed to extract results from {url}: {str(e)}")
    
    def _parse_navisport_html(self, soup: BeautifulSoup) -> str:
        """
        Parse race results from navisport HTML.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            Formatted results string
        """
        results = []
        
        # Look for results in tables
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:  # Need at least position, name, time
                    continue
                
                # Extract text from cells
                cell_texts = [cell.get_text(strip=True) for cell in cells]
                
                # Skip header rows
                if not cell_texts[0] or not cell_texts[0][0].isdigit():
                    continue
                
                # Try to parse as race result
                result_line = self._format_result_line(cell_texts)
                if result_line:
                    results.append(result_line)
        
        # If no table results found, try other patterns
        if not results:
            results = self._parse_alternative_patterns(soup)
        
        return '\n'.join(results)
    
    def _format_result_line(self, cells: List[str]) -> Optional[str]:
        """
        Format a table row as a result line compatible with parseri.py.
        
        Expected format: "position name team time"
        
        Args:
            cells: List of cell texts from a table row
            
        Returns:
            Formatted result line or None if parsing fails
        """
        if len(cells) < 3:
            return None
        
        try:
            # Try different cell arrangements
            # Common patterns:
            # [pos, name, team, time, ...]
            # [pos, name, time, diff, ...]
            # [pos, first_name, last_name, team, time, ...]
            
            pos = cells[0].strip()
            if not pos or not pos[0].isdigit():
                return None
            
            # Extract name (could be in one cell or split across multiple)
            name_parts = []
            team = ""
            time = ""
            
            # Look for time pattern (HH:MM:SS or MM:SS)
            time_pattern = re.compile(r'\d{1,2}:\d{2}(?::\d{2})?')
            time_idx = -1
            
            for i, cell in enumerate(cells[1:], 1):
                if time_pattern.search(cell):
                    time = cell.strip()
                    time_idx = i
                    break
            
            if time_idx > 1:
                # Cells between position and time are likely name/team
                name_team_cells = cells[1:time_idx]
                
                if len(name_team_cells) >= 2:
                    # Assume last cell before time is team, rest is name
                    name_parts = name_team_cells[:-1]
                    team = name_team_cells[-1].strip()
                else:
                    name_parts = name_team_cells
            
            if not name_parts:
                return None
            
            # Join name parts
            name = ' '.join(part.strip() for part in name_parts if part.strip())
            
            # Clean up time (remove extra whitespace, +/- prefixes)
            time = re.sub(r'^\s*[\+\-]\s*', '', time).strip()
            
            # Format as "position name team time"
            if team:
                return f"{pos} {name} {team} {time}"
            else:
                return f"{pos} {name} {time}"
                
        except Exception:
            return None
    
    def _parse_alternative_patterns(self, soup: BeautifulSoup) -> List[str]:
        """
        Parse results using alternative patterns when tables aren't found.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            List of formatted result lines
        """
        results = []
        
        # Look for divs or other containers with result-like content
        result_containers = soup.find_all(['div', 'li', 'p'], 
                                        class_=re.compile(r'result|participant|competitor', re.I))
        
        for container in result_containers:
            text = container.get_text(strip=True)
            if not text:
                continue
            
            # Try to match patterns like "1. Name Team 56:27"
            match = re.match(r'(\d+)\.?\s+(.+?)\s+([^\d]*?)\s+(\d{1,2}:\d{2}(?::\d{2})?)', text)
            if match:
                pos, name, team, time = match.groups()
                team = team.strip()
                if team:
                    results.append(f"{pos} {name.strip()} {team} {time}")
                else:
                    results.append(f"{pos} {name.strip()} {time}")
        
        return results
    
    def extract_results(self, url: str) -> str:
        """
        Main extraction method that detects URL type and uses appropriate parser.
        
        Args:
            url: URL to extract results from
            
        Returns:
            Formatted results string compatible with parseri.py
        """
        try:
            if 'navisport.com' in url:
                return self.extract_navisport_results(url)
            else:
                # Generic extraction for other sites
                return self.extract_navisport_results(url)  # Use same method for now
        finally:
            self._cleanup_driver()


def extract_race_results(url: str, headless: bool = True, timeout: int = 30) -> str:
    """
    Convenience function to extract race results from a URL.
    
    Args:
        url: URL to extract results from
        headless: Whether to run browser in headless mode
        timeout: Maximum time to wait for page elements
        
    Returns:
        Formatted results string compatible with parseri.py parseResults()
    """
    extractor = RaceResultsExtractor(headless=headless, timeout=timeout)
    return extractor.extract_results(url)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python extractor.py <URL>")
        sys.exit(1)
    
    url = sys.argv[1]
    try:
        results = extract_race_results(url)
        print(results)
    except Exception as e:
        print(f"Error extracting results: {e}", file=sys.stderr)
        sys.exit(1)