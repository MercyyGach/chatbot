"""
Full RAG test: embeds a question, retrieves the closest chunks from Neon,
then asks Gemini to answer using ONLY that retrieved context.

Usage:
    python ask.py --query "What printers do you sell?" --site stationery
    python ask.py --query "What does AdvaIoT do?" --site advaiot
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
CHAT_MODEL = "gemini-2.5-flash"
OUTPUT_DIM = 768

SYSTEM_PROMPT = """You are a friendly, knowledgeable assistant chatting with visitors on
an Advatech Group website. You represent the company directly -- talk like a
helpful team member, not like a research tool describing a document.

Answer using ONLY the information given to you below. Never invent details,
prices, or destinations that aren't there.

Style rules:
- Speak naturally and warmly, in first person plural ("we offer...", "our team...").
- Never say phrases like "based on the provided context" or "the context mentions" --
  just answer as if you simply know this because you work here.
- If the information given doesn't cover what's being asked, say so plainly and
  warmly, then suggest reaching out to the team directly for anything more specific --
  don't just state that something isn't mentioned.
- Keep answers concise. Use specific names, prices, or details when you have them.
"""


def embed_query(text: str) -> list[float]:
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=OUTPUT_DIM,
            task_type="RETRIEVAL_QUERY",
        ),
    )
    return result.embeddings[0].values


def retrieve_chunks(query_vector: list[float], site: str | None, top_k: int = 5):
    conn = psycopg2.connect(DATABASE_URL)
    vector_str = str(query_vector)
    with conn.cursor() as cur:
        if site:
            cur.execute(
                """
                SELECT site, url, content
                FROM chunks
                WHERE site = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (site, vector_str, top_k),
            )
        else:
            cur.execute(
                """
                SELECT site, url, content
                FROM chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (vector_str, top_k),
            )
        rows = cur.fetchall()
    conn.close()
    return rows


def build_context(chunks) -> str:
    parts = []
    for i, (site, url, content) in enumerate(chunks, 1):
        parts.append(f"[Source {i} - {url}]\n{content}")
    return "\n\n".join(parts)


def generate_answer(question: str, context: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=prompt,
    )
    return response.text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--site", help="Optional: restrict retrieval to one site")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--show-sources", action="store_true", help="Print the retrieved chunks too")
    args = parser.parse_args()

    query_vector = embed_query(args.query)
    chunks = retrieve_chunks(query_vector, args.site, args.top_k)

    if not chunks:
        print("No matching content found.")
        return

    if args.show_sources:
        print("--- Retrieved context ---")
        for site, url, content in chunks:
            print(f"[{site}] {url}\n{content[:150]}\n")
        print("--- End context ---\n")

    context = build_context(chunks)
    answer = generate_answer(args.query, context)

    print(f"Q: {args.query}\n")
    print(f"A: {answer}")


if __name__ == "__main__":
    main()