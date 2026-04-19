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

# --- CONFIGURATION: TARGETING THE "GOOD" STUFF ---
# Skip URLs containing these substrings
IRRELEVANT_KEYWORDS = [
    '/about/', '/press/', '/news/', '/careers/', '/leadership/', 
    '/organization/', '/contact/', '/events/', '/privacy_policy/',
    'social-media', 'biographies', 'contracting'
]

# Only process URLs containing these (Optional: uncomment to be ultra-strict)
# RELEVANT_KEYWORDS = ['/states/', '/renting/', '/hcv/', '/program/', '/eligibility/']

# HTML Elements that HUD usually uses for the "Meat" of the page
MAIN_CONTENT_SELECTORS = [
    'main', 'article', '#main-content', '.region-content', '.content-node'
]

def is_relevant_url(url):
    """Filters out 'About Us' and administrative pages."""
    path = url.lower()
    for keyword in IRRELEVANT_KEYWORDS:
        if keyword in path:
            return False
    return True

def get_markdown_from_url(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        if not is_relevant_url(url):
            return None, []

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            return None, []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. REMOVE NOISE (Sidebars, Nav, Social Media)
        noise_selectors = [
            'header', 'footer', 'nav', 'aside', '.sidebar', 
            '.breadcrumb', '.social-share', '.navigation', '#skip-link'
        ]
        for selector in noise_selectors:
            for element in soup.select(selector):
                element.decompose()

        # 2. TARGET THE CONTENT
        # We try to find the main body. If we can't, we fallback to the whole body.
        main_content = None
        for selector in MAIN_CONTENT_SELECTORS:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        target = main_content if main_content else soup.find('body')
        
        # Update links to absolute URLs for the crawler
        links = []
        for a in target.find_all('a', href=True):
            full_url = urljoin(url, a['href'])
            a['href'] = full_url
            links.append(full_url)

        # 3. CONVERT TO MARKDOWN
        markdown_content = md(str(target), heading_style="ATX").strip()
        
        # Filter out pages that are too short (likely empty or splash pages)
        if len(markdown_content) < 300:
            return None, links
            
        return markdown_content, links
        
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None, []

# ... [get_markdown_from_pdf remains the same] ...
def get_markdown_from_pdf(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)
        text_content = [page.extract_text() for page in reader.pages if page.extract_text()]
        return "\n\n".join(text_content)
    except Exception as e:
        print(f"Error fetching PDF {url}: {e}")
        return None

def fetch_data(start_url, max_depth=1):
    start_url = urldefrag(start_url)[0].rstrip('/')
    visited = {} 
    queue = deque([(start_url, 0)]) 

    ignore_extensions = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip", ".css", ".js"}

    while queue:
        link, depth = queue.popleft()
        if link in visited or depth > max_depth:
            continue

        parsed = urlparse(link)
        if parsed.netloc != urlparse(start_url).netloc:
            continue 

        file_extension = os.path.splitext(parsed.path)[1].lower()
        if file_extension in ignore_extensions:
            continue

        if file_extension == ".pdf":
            print(f"Scraping PDF: {link}")
            content = get_markdown_from_pdf(link)
            found_links = []
        else:
            print(f"Scraping: {link} (Depth {depth})")
            content, found_links = get_markdown_from_url(link)
        
        if content:
            visited[link] = content
            if depth < max_depth:
                for new_link in found_links:
                    normalized = urldefrag(new_link)[0].rstrip('/')
                    if normalized not in visited:
                        queue.append((normalized, depth + 1))
    return visited

def save_data_to_disk(data, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for url, content in data.items():
        # Keep the URL at the very top for the RAG metadata extractor
        filename = re.sub(r'[^a-zA-Z0-9]', '_', urlparse(url).path.strip('/')) or "index"
        filepath = os.path.join(output_dir, f"{filename[:200]}.md")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{url}\n---\n\n{content}")

def scrape(start_url, max_depth=1, output_dir=None):
    if output_dir is None:
        output_dir = urlparse(start_url).netloc
    scraped_data = fetch_data(start_url, max_depth=max_depth)
    save_data_to_disk(scraped_data, output_dir)
    return scraped_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("-d", "--depth", type=int, default=1)
    parser.add_argument("-o", "--output", default=None)
    args = parser.parse_args()
    scrape(args.url, max_depth=args.depth, output_dir=args.output)