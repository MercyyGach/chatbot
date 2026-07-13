"""
Reads data/pages_<site>.json files and splits each page's text into
overlapping chunks, saving to data/chunks_<site>.json. No DB needed yet.

Usage:
    python chunk_pages.py --site advatech-uganda
    python chunk_pages.py --all
"""

import argparse
import glob
import json
import os

CHUNK_SIZE_WORDS = 180
CHUNK_OVERLAP_WORDS = 30


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


def process_site(site: str):
    in_path = os.path.join("data", f"pages_{site}.json")
    if not os.path.exists(in_path):
        print(f"  [skip] {in_path} not found")
        return 0

    with open(in_path, encoding="utf-8") as f:
        data = json.load(f)

    all_chunks = []
    for page in data["pages"]:
        pieces = chunk_text(page["text"])
        for idx, piece in enumerate(pieces):
            all_chunks.append(
                {
                    "site": site,
                    "url": page["url"],
                    "title": page.get("title", ""),
                    "chunk_index": idx,
                    "content": piece,
                }
            )

    out_path = os.path.join("data", f"chunks_{site}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"  {site}: {len(data['pages'])} pages -> {len(all_chunks)} chunks -> {out_path}")
    return len(all_chunks)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--site", help="Chunk just this site (matches data/pages_<site>.json)")
    group.add_argument("--all", action="store_true", help="Chunk every pages_*.json file found in data/")
    args = parser.parse_args()

    total = 0
    if args.all:
        pattern = os.path.join("data", "pages_*.json")
        for path in sorted(glob.glob(pattern)):
            site = os.path.basename(path).replace("pages_", "").replace(".json", "")
            total += process_site(site)
    else:
        total = process_site(args.site)

    print(f"\nDone. {total} total chunks created.")


if __name__ == "__main__":
    main()
