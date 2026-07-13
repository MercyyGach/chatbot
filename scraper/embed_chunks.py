"""
Reads data/chunks_<site>.json, generates a Gemini embedding for each chunk,
and saves the result (chunk + embedding vector) to data/embedded_<site>.json.

Safe to re-run: if interrupted partway, it picks up where it left off
instead of re-embedding chunks it already processed (saves API calls).

Usage:
    python embed_chunks.py --site advatech-uganda
    python embed_chunks.py --all
"""

import argparse
import glob
import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from tqdm import tqdm

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

EMBEDDING_MODEL = "gemini-embedding-001"
OUTPUT_DIM = 768  # keeps storage + search fast; plenty of quality for this use case


def embed_one(text: str) -> list[float]:
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=OUTPUT_DIM),
    )
    return result.embeddings[0].values


def process_site(site: str, delay: float = 0.3):
    in_path = os.path.join("data", f"chunks_{site}.json")
    out_path = os.path.join("data", f"embedded_{site}.json")

    if not os.path.exists(in_path):
        print(f"  [skip] {in_path} not found")
        return 0

    with open(in_path, encoding="utf-8") as f:
        chunks = json.load(f)

    # Resume support: load whatever's already been embedded
    already_done = []
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            already_done = json.load(f)

    done_count = len(already_done)
    if done_count >= len(chunks):
        print(f"  {site}: already fully embedded ({done_count} chunks), skipping")
        return done_count

    results = already_done
    remaining = chunks[done_count:]

    pbar = tqdm(total=len(chunks), initial=done_count, desc=f"Embedding {site}")
    for chunk in remaining:
        try:
            vector = embed_one(chunk["content"])
        except Exception as e:
            print(f"\n  [error] chunk {chunk['chunk_index']} of {chunk['url']} -> {e}")
            print(f"  Saving progress so far ({len(results)} chunks) -- re-run to resume.")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False)
            raise SystemExit(1)

        chunk_with_embedding = {**chunk, "embedding": vector}
        results.append(chunk_with_embedding)
        pbar.update(1)

        # Save progress every 20 chunks so a crash doesn't lose much work
        if len(results) % 20 == 0:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False)

        time.sleep(delay)

    pbar.close()

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)

    print(f"  {site}: {len(results)} chunks embedded -> {out_path}")
    return len(results)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--site", help="Embed just this site (matches data/chunks_<site>.json)")
    group.add_argument("--all", action="store_true", help="Embed every chunks_*.json file found in data/")
    parser.add_argument("--delay", type=float, default=0.3, help="Seconds between API calls")
    args = parser.parse_args()

    total = 0
    if args.all:
        pattern = os.path.join("data", "chunks_*.json")
        for path in sorted(glob.glob(pattern)):
            site = os.path.basename(path).replace("chunks_", "").replace(".json", "")
            total += process_site(site, delay=args.delay)
    else:
        total = process_site(args.site, delay=args.delay)

    print(f"\nDone. {total} total chunks embedded.")


if __name__ == "__main__":
    main()
