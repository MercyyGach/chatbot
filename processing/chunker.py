"""
Reads rows from `pages`, splits the text into overlapping chunks,
and stores them in `chunks` (embedding left NULL until the next step).

Usage:
    python chunker.py --site advaforecourt
    python chunker.py --all
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Rough word-based chunking. ~180 words is a safe size that stays well under
# the 2048-token embedding input limit even for dense text, and 30-word overlap
# keeps context from getting cut mid-idea between chunks.
CHUNK_SIZE_WORDS = 180
CHUNK_OVERLAP_WORDS = 30


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "advatech_kb"),
        user=os.getenv("DB_USER", "advatech"),
        password=os.getenv("DB_PASSWORD", "advatech_dev_password"),
    )


def chunk_text(text: str, size: int = CHUNK_SIZE_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    words = text.split()
    if len(words) <= size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = start + size
        chunks.append(" ".join(words[start:end]))
        start += size - overlap
    return chunks


def process_pages(conn, site: str | None):
    with conn.cursor() as cur:
        if site:
            cur.execute("SELECT id, site, url, raw_text FROM pages WHERE site = %s", (site,))
        else:
            cur.execute("SELECT id, site, url, raw_text FROM pages")
        pages = cur.fetchall()

    total_chunks = 0
    for page_id, page_site, url, raw_text in pages:
        # Clear any existing chunks for this page so re-running is idempotent
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE page_id = %s", (page_id,))

        pieces = chunk_text(raw_text)
        with conn.cursor() as cur:
            for idx, piece in enumerate(pieces):
                cur.execute(
                    """
                    INSERT INTO chunks (page_id, site, url, chunk_index, content)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (page_id, page_site, url, idx, piece),
                )
        conn.commit()
        total_chunks += len(pieces)
        print(f"  {url} -> {len(pieces)} chunks")

    print(f"\nDone. {len(pages)} pages processed, {total_chunks} chunks created.")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--site", help="Only chunk pages for this site")
    group.add_argument("--all", action="store_true", help="Chunk pages for every site")
    args = parser.parse_args()

    conn = get_db_connection()
    process_pages(conn, args.site if not args.all else None)
    conn.close()


if __name__ == "__main__":
    main()
