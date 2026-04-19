#!/usr/bin/env python3
import os
import io
import requests
import re
import argparse
from markdownify import markdownify as md
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from pypdf import PdfReader
from collections import deque

def get_markdown_from_url(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Determine if we should parse as HTML or skip (e.g., PDF)
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            return None, []

        # Convert to Markdown
        markdown_content = md(response.text, heading_style="ATX")
        
        # Parse HTML first so we can grab links and make them absolute
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []

        """        # 1. List the specific classes or IDs you want to kill
        junk_selectors = {
            'id': ['header-wrapper', 'top-nav'],
            'class': ['site-footer-v2', 'ads-container', 'social-links']
        }

        # 2. Loop through and decompose
        for attr, values in junk_selectors.items():
            for value in values:
                for element in soup.find_all('div', {attr: value}):
                    element.decompose()"""
        
        for element in soup(['header', 'footer']):
            element.decompose()
        
        # Update all links to absolute URLs
        for a in soup.find_all('a', href=True):
            full_url = urljoin(url, a['href'])
            a['href'] = full_url  # Modify the HTML directly
            links.append(full_url) # Save for the crawler stack
            

        # Convert the modified HTML string into Markdown
        markdown_content = md(str(soup), heading_style="ATX")
            
        return markdown_content, links
        
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None, []

def get_markdown_from_pdf(url):
    """Fetches a PDF from a URL and extracts its text."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Read the PDF directly from the bytes response
        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)
        
        text_content = []
        for i, page in enumerate(reader.pages):
            extracted = page.extract_text()
            if extracted:
                text_content.append(extracted)
                
        # Combine pages and treat as basic markdown text
        return "\n\n".join(text_content)
        
    except Exception as e:
        print(f"Error fetching PDF {url}: {e}")
        return None


def fetch_data(start_url, max_depth=1):
    start_url = urldefrag(start_url)[0].rstrip('/')

    visited = {} # maps from link to md content
    queue = deque([(start_url, 0)]) # (url, current_depth)

    ignore_extensions = {
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", # Images
        ".zip", ".tar", ".gz", ".rar", ".7z",                     # Archives
        ".mp3", ".mp4", ".wav", ".avi", ".mov",                   # Media
        ".css", ".js", ".json", ".xml",                           # Web assets
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"         # Office docs
    }

    while queue:
        link, depth = queue.popleft()
        
        if link in visited or depth > max_depth:
            continue

        parsed = urlparse(link)
        domain = parsed.netloc
        file_extension = os.path.splitext(parsed.path)[1].lower()

        if domain != urlparse(start_url).netloc:
            continue # Skip external links

        if file_extension in ignore_extensions:
            print(f"Skipping file: {link}")
            visited[link] = f"FILE_REFERENCE: {link}"
            continue

        if file_extension == ".pdf":
            print(f"Scraping PDF: {link} at depth {depth}")
            content = get_markdown_from_pdf(link)
            found_links = []
        else:
            print(f"Scraping: {link} at depth {depth}")
            content, found_links = get_markdown_from_url(link)
        
        if content:
            visited[link] = content
            # Add new links to stack if we haven't reached max_depth
            if depth < max_depth:
                for new_link in found_links:
                    # Strip fragments (#) and trailing slashes (/)
                    normalized_link = urldefrag(new_link)[0].rstrip('/')
                    
                    if normalized_link not in visited:
                        queue.append((normalized_link, depth + 1))
    
    return visited

def url_to_filename(url):
    """Converts a URL path into a safe filename."""
    parsed = urlparse(url)
    # Combine path and query string, remove leading/trailing slashes
    path = (parsed.path + parsed.query).strip('/')
    
    if not path:
        return "index.md"
        
    # Replace non-alphanumeric characters (like / or ?) with underscores
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', path)
    return f"{safe_name}.md"

def save_data_to_disk(data, output_dir):
    """Saves the scraped markdown data to the specified folder."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    saved_count = 0
    for url, content in data.items():
        if not content or content.startswith("FILE_REFERENCE"):
            continue
            
        filename = url_to_filename(url)
        filepath = os.path.join(output_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"{url}\n---\n\n")
                f.write(content)
            saved_count += 1
        except Exception as e:
            print(f"Error saving {url} to {filepath}: {e}")
            
    print(f"\nSuccessfully saved {saved_count} pages to the '{output_dir}' folder.")

def scrape(start_url, max_depth=1, output_dir=None):
    """
    Main scraping function. Can be imported and used as a library.
    """
    if output_dir is None:
        # Default to the domain name if no output directory is provided
        output_dir = urlparse(start_url).netloc
        
    print(f"Starting scrape of {start_url} (Max Depth: {max_depth})...")
    scraped_data = fetch_data(start_url, max_depth=max_depth)
    
    print("\nSaving files to disk...")
    save_data_to_disk(scraped_data, output_dir)
    return scraped_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape a website and save pages as Markdown files.")
    parser.add_argument("url", help="The starting URL to scrape")
    parser.add_argument("-d", "--depth", type=int, default=1, help="Maximum depth to crawl (default: 1)")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output directory (default: website domain)")
    
    args = parser.parse_args()
    
    scrape(args.url, max_depth=args.depth, output_dir=args.output)
