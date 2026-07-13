"""
Scrapes a list of URLs for one Advatech site and stores the cleaned text in Postgres.

Usage:
    python scrape_site.py --site advaforecourt --urls urls_advaforecourt.txt

Where urls_advaforecourt.txt is a plain text file, one URL per line.
"""

import argparse
import os
import time

import psycopg2
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AdvatechKBBot/1.0; +https://advatech.co.ke)"
}

# Tags that are almost never useful content -- strip these before extracting text
TAGS_TO_REMOVE = ["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "advatech_kb"),
        user=os.getenv("DB_USER", "advatech"),
        password=os.getenv("DB_PASSWORD", "advatech_dev_password"),
    )


def clean_page(html: str) -> tuple[str, str]:
    """Returns (title, cleaned_text) from raw HTML."""
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    for tag_name in TAGS_TO_REMOVE:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Prefer <main> or <article> if present -- usually the real content area
    main_content = soup.find("main") or soup.find("article") or soup

    text = main_content.get_text(separator="\n", strip=True)

    # Collapse excessive blank lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return title, "\n".join(lines)


def scrape_url(url: str) -> tuple[str, str] | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [skip] {url} -> {e}")
        return None

    title, text = clean_page(resp.text)
    if len(text) < 50:
        print(f"  [skip] {url} -> too little text extracted (JS-rendered page?)")
        return None
    return title, text


def save_page(conn, site: str, url: str, title: str, text: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pages (site, url, title, raw_text)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE
                SET title = EXCLUDED.title,
                    raw_text = EXCLUDED.raw_text,
                    scraped_at = NOW();
            """,
            (site, url, title, text),
        )
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True, help="Short site identifier, e.g. advaforecourt")
    parser.add_argument("--urls", required=True, help="Path to a text file with one URL per line")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds to wait between requests")
    args = parser.parse_args()

    with open(args.urls) as f:
        urls = [line.strip() for line in f if line.strip()]

    conn = get_db_connection()
    saved = 0

    for url in tqdm(urls, desc=f"Scraping {args.site}"):
        result = scrape_url(url)
        if result:
            title, text = result
            save_page(conn, args.site, url, title, text)
            saved += 1
        time.sleep(args.delay)

    conn.close()
    print(f"\nDone. Saved/updated {saved}/{len(urls)} pages for site '{args.site}'.")


if __name__ == "__main__":
    main()
