"""
Removes repeated boilerplate lines (like sidebar filters, nav text) from a
site's scraped pages -- automatically detected as lines that appear on an
unusually high fraction of that site's pages, rather than being unique
content.

This OVERWRITES data/pages_<site>.json (keeping a backup as
data/pages_<site>_raw_backup.json first) so the rest of the pipeline
(chunking, embedding, loading) can just be re-run normally afterward.

Usage:
    python clean_boilerplate.py --site stationery
    python clean_boilerplate.py --site stationery --threshold 0.3 --dry-run
"""

import argparse
import json
import os
import shutil
from collections import Counter


def load_pages(site: str) -> dict:
    path = os.path.join("data", f"pages_{site}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_boilerplate_lines(pages: list[dict], threshold: float) -> set[str]:
    """Lines appearing on more than `threshold` fraction of pages are boilerplate."""
    line_page_counts = Counter()
    for page in pages:
        lines = set(line.strip() for line in page["text"].splitlines() if line.strip())
        for line in lines:
            line_page_counts[line] += 1

    n_pages = len(pages)
    boilerplate = {
        line for line, count in line_page_counts.items()
        if count / n_pages >= threshold
    }
    return boilerplate


def clean_pages(pages: list[dict], boilerplate: set[str]) -> list[dict]:
    cleaned = []
    for page in pages:
        lines = [line for line in page["text"].splitlines() if line.strip() not in boilerplate]
        cleaned_text = "\n".join(line for line in lines if line.strip())
        cleaned.append({**page, "text": cleaned_text})
    return cleaned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.4,
        help="Fraction of pages a line must appear on to count as boilerplate (default 0.4 = 40%%)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Just show what would be removed, don't write anything",
    )
    args = parser.parse_args()

    data = load_pages(args.site)
    pages = data["pages"]

    boilerplate = find_boilerplate_lines(pages, args.threshold)

    print(f"Found {len(boilerplate)} boilerplate lines (appearing on >= {args.threshold*100:.0f}% of {len(pages)} pages):\n")
    for line in sorted(boilerplate, key=len, reverse=True)[:30]:
        print(f"  - {line[:100]}")

    if args.dry_run:
        print("\n[dry run] Nothing was written. Remove --dry-run to apply the cleanup.")
        return

    cleaned_pages = clean_pages(pages, boilerplate)

    # Backup the original before overwriting
    original_path = os.path.join("data", f"pages_{args.site}.json")
    backup_path = os.path.join("data", f"pages_{args.site}_raw_backup.json")
    if not os.path.exists(backup_path):
        shutil.copy(original_path, backup_path)
        print(f"\nBacked up original to {backup_path}")

    with open(original_path, "w", encoding="utf-8") as f:
        json.dump({"site": args.site, "pages": cleaned_pages}, f, indent=2, ensure_ascii=False)

    avg_before = sum(len(p["text"]) for p in pages) / len(pages)
    avg_after = sum(len(p["text"]) for p in cleaned_pages) / len(cleaned_pages)
    print(f"\nDone. Average page length: {avg_before:.0f} chars -> {avg_after:.0f} chars")
    print(f"Cleaned pages saved to {original_path}")
    print("\nNext: delete the old chunks/embeddings for this site and rebuild them:")
    print(f"  del data\\chunks_{args.site}.json")
    print(f"  del data\\embedded_{args.site}.json")
    print(f"  python chunk_pages.py --site {args.site}")
    print(f"  python embed_chunks.py --site {args.site}")
    print(f"  python load_to_neon.py")


if __name__ == "__main__":
    main()
