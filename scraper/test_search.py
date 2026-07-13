"""
Quick test: embeds a question the same way we embedded the chunks, then
searches Neon for the closest matching chunks using cosine similarity.

Usage:
    python test_search.py --query "What services does AdvaIoT offer?"
    python test_search.py --query "What printers do you sell?" --site stationery
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
DATABASE_URL = os.getenv("DATABASE_URL")

EMBEDDING_MODEL = "gemini-embedding-001"
OUTPUT_DIM = 768


def embed_query(text: str) -> list[float]:
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        # task_type matters here: queries and documents are embedded slightly
        # differently for best retrieval accuracy
        config=types.EmbedContentConfig(
            output_dimensionality=OUTPUT_DIM,
            task_type="RETRIEVAL_QUERY",
        ),
    )
    return result.embeddings[0].values


def search(query_vector: list[float], site: str | None, top_k: int = 5):
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        vector_str = str(query_vector)
        if site:
            cur.execute(
                """
                SELECT site, url, content, 1 - (embedding <=> %s::vector) AS similarity
                FROM chunks
                WHERE site = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (vector_str, site, vector_str, top_k),
            )
        else:
            cur.execute(
                """
                SELECT site, url, content, 1 - (embedding <=> %s::vector) AS similarity
                FROM chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (vector_str, vector_str, top_k),
            )
        rows = cur.fetchall()
    conn.close()
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True, help="Question to search for")
    parser.add_argument("--site", help="Optional: restrict search to one site")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    print(f"Query: {args.query}")
    if args.site:
        print(f"Restricted to site: {args.site}")
    print("Embedding query...")
    query_vector = embed_query(args.query)

    print("Searching...\n")
    results = search(query_vector, args.site, args.top_k)

    for i, (site, url, content, similarity) in enumerate(results, 1):
        print(f"--- Result {i} (similarity: {similarity:.3f}) ---")
        print(f"Site: {site} | URL: {url}")
        print(content[:250])
        print()


if __name__ == "__main__":
    main()
