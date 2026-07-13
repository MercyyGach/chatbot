"""
Same as crawl_site.py, but uses a real (headless) browser via Playwright so
JavaScript-rendered content actually loads before we grab the text.
Use this ONLY for sites where crawl_site.py returned 0 pages.

First-time setup (one-off, run once):
    pip install playwright
    playwright install chromium

Usage:
    python crawl_site_js.py --site stationery --start https://stationery-six.vercel.app/
"""

import argparse
import json
import os
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from tqdm import tqdm

TAGS_TO_REMOVE = ["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]
SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".css", ".js", ".ico")


def is_same_site(base_domain: str, url: str) -> bool:
    return urlparse(url).netloc == base_domain


def clean_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def extract_page(html: str) -> tuple[str, str, list[str]]:
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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        pbar = tqdm(total=max_pages, desc="Crawling (JS)")
        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                page.goto(url, timeout=20000, wait_until="networkidle")
                # small extra wait for any late client-side rendering
                page.wait_for_timeout(500)
                html = page.content()
            except Exception as e:
                print(f"  [skip] {url} -> {e}")
                continue

            title, text, links = extract_page(html)

            if len(text) >= 50:
                results.append({"url": url, "title": title, "text": text})
                pbar.update(1)
            else:
                print(f"  [skip] {url} -> still too little text")

            for link in links:
                full_url = urljoin(url, link)
                full_url = clean_url(full_url)
                if (
                    is_same_site(base_domain, full_url)
                    and full_url not in visited
                    and full_url not in to_visit
                    and not full_url.lower().endswith(SKIP_EXTENSIONS)
                ):
                    to_visit.append(full_url)

            time.sleep(delay)

        pbar.close()
        browser.close()

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--max-pages", type=int, default=60)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    pages = crawl(args.start, max_pages=args.max_pages, delay=args.delay)

    os.makedirs("data", exist_ok=True)
    out_path = os.path.join("data", f"pages_{args.site}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"site": args.site, "pages": pages}, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Saved {len(pages)} pages to {out_path}")


if __name__ == "__main__":
    main()
