"""
Creates the pgvector extension + chunks table in your Neon database (if not
already there), then loads every data/embedded_<site>.json file into it.

Usage:
    python load_to_neon.py
"""

import glob
import json
import os

import psycopg2
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

CREATE_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id          SERIAL PRIMARY KEY,
    site        TEXT NOT NULL,
    url         TEXT NOT NULL,
    title       TEXT,
    chunk_index INTEGER NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(768),
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chunks_site_idx ON chunks (site);
"""

# Created after data is loaded -- ivfflat indexes need existing rows to build well
CREATE_VECTOR_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);
"""


def get_connection():
    if not DATABASE_URL:
        raise SystemExit(
            "DATABASE_URL not found in .env -- add your Neon connection string first."
        )
    return psycopg2.connect(DATABASE_URL)


def setup_tables(conn):
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()
    print("Tables ready.")


def load_site(conn, path: str):
    site = os.path.basename(path).replace("embedded_", "").replace(".json", "")
    with open(path, encoding="utf-8") as f:
        chunks = json.load(f)

    with conn.cursor() as cur:
        # Clear existing rows for this site so re-running is safe (no duplicates)
        cur.execute("DELETE FROM chunks WHERE site = %s", (site,))

        for chunk in tqdm(chunks, desc=f"Loading {site}"):
            cur.execute(
                """
                INSERT INTO chunks (site, url, title, chunk_index, content, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    chunk["site"],
                    chunk["url"],
                    chunk.get("title", ""),
                    chunk["chunk_index"],
                    chunk["content"],
                    chunk["embedding"],
                ),
            )
    conn.commit()
    return len(chunks)


def main():
    conn = get_connection()
    setup_tables(conn)

    total = 0
    for path in sorted(glob.glob(os.path.join("data", "embedded_*.json"))):
        total += load_site(conn, path)

    print("Building similarity search index (this can take a moment)...")
    with conn.cursor() as cur:
        cur.execute(CREATE_VECTOR_INDEX_SQL)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT site, COUNT(*) FROM chunks GROUP BY site ORDER BY site;")
        rows = cur.fetchall()

    conn.close()

    print(f"\nDone. {total} chunks loaded.\n")
    print("Chunks per site in the database:")
    for site, count in rows:
        print(f"  {site}: {count}")


if __name__ == "__main__":
    main()
