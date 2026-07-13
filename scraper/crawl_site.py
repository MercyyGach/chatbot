"""
Auto-crawls a site starting from its homepage, following internal links,
and saves all page content to a local JSON file. No database needed yet.

Usage:
    python crawl_site.py --site advatech-uganda --start https://advatech-uganda.vercel.app/

Output:
    data/pages_advatech-uganda.json
"""

import argparse
import json
import os
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AdvatechKBBot/1.0; +https://advatech.co.ke)"
}

TAGS_TO_REMOVE = ["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]

# Skip links to files/anchors/external stuff, not real pages
SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".css", ".js", ".ico")


def is_same_site(base_domain: str, url: str) -> bool:
    return urlparse(url).netloc == base_domain


def clean_url(url: str) -> str:
    """Strip fragments (#section) and trailing slashes for consistent dedup."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def extract_page(html: str) -> tuple[str, str, list[str]]:
    """Returns (title, cleaned_text, list_of_links_found)."""
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    links = [a["href"] for a in soup.find_all("a", href=True)]

    for tag_name in TAGS_TO_REMOVE:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    main_content = soup.find("main") or soup.find("article") or soup
    text = main_content.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    return title, "\n".join(lines), links


def crawl(start_url: str, max_pages: int = 60, delay: float = 1.0) -> list[dict]:
    base_domain = urlparse(start_url).netloc
    to_visit = [clean_url(start_url)]
    visited = set()
    results = []

    pbar = tqdm(total=max_pages, desc="Crawling")
    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [skip] {url} -> {e}")
            continue

        title, text, links = extract_page(resp.text)

        if len(text) >= 50:
            results.append({"url": url, "title": title, "text": text})
            pbar.update(1)
        else:
            print(f"  [skip] {url} -> too little text (JS-rendered page?)")

        for link in links:
            full_url = urljoin(url, link)
            full_url = clean_url(full_url)
            if (
                is_same_site(base_domain, full_url)
                and full_url not in visited
                and full_url not in to_visit
                and not full_url.lower().endswith(SKIP_EXTENSIONS)
                and "#" not in link[:1]  # skip pure anchor links
            ):
                to_visit.append(full_url)

        time.sleep(delay)

    pbar.close()
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True, help="Short site identifier, e.g. advatech-uganda")
    parser.add_argument("--start", required=True, help="Homepage URL to start crawling from")
    parser.add_argument("--max-pages", type=int, default=60, help="Safety limit on pages to crawl")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests")
    args = parser.parse_args()

    pages = crawl(args.start, max_pages=args.max_pages, delay=args.delay)

    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", f"pages_{args.site}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"site": args.site, "pages": pages}, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Saved {len(pages)} pages to {out_path}")


if __name__ == "__main__":
    main()
