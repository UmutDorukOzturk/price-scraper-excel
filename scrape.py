"""Scrape the whole books.toscrape.com catalogue into a formatted Excel report.

Usage:
    python scrape.py                     # full run, compared with the latest snapshot
    python scrape.py --max-pages 2       # quick test on the first 2 listing pages
    python scrape.py --compare snapshots/books_2026-10-29_0900.csv
    python scrape.py --from-snapshot snapshots/books_2026-11-05_1432.csv   # rebuild the report, no scraping
"""
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from price_scraper.compare import compare
from price_scraper.excel_report import write_report
from price_scraper.fetch import get_html
from price_scraper.parse import parse_listing, parse_product

START_URL = "https://books.toscrape.com/catalogue/page-1.html"
SOURCE = "books.toscrape.com"
ROOT = Path(__file__).resolve().parent
SNAPSHOT_DIR = ROOT / "snapshots"
OUTPUT_DIR = ROOT / "output"
STAMP = "%Y-%m-%d_%H%M"


def step(n: int, text: str, result: str) -> None:
    print(f"[{n}/4] {(text + ' ').ljust(36, '.')} {result}", flush=True)


def collect_links(max_pages: Optional[int], delay: float) -> tuple[list[str], int]:
    url, links, pages = START_URL, [], 0
    while url and (max_pages is None or pages < max_pages):
        page_links, url = parse_listing(get_html(url, delay), url)
        links += page_links
        pages += 1
    return list(dict.fromkeys(links)), pages


def fetch_products(links: list[str], workers: int, delay: float) -> tuple[list[dict], list[tuple[str, str]]]:
    records, failed = [], []
    show_progress = sys.stdout.isatty()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(lambda u: parse_product(get_html(u, delay), u), url): url for url in links}
        for done, future in enumerate(as_completed(futures), start=1):
            try:
                records.append(future.result())
            except Exception as exc:  # keep going; failures are reported at the end
                failed.append((futures[future], str(exc)))
            if show_progress:
                print(f"\r      downloading product pages... {done:,}/{len(links):,}", end="", flush=True)
    if show_progress:
        print("\r" + " " * 60 + "\r", end="")
    return records, failed


def clean(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    df = df.dropna(subset=["price"]).drop_duplicates(subset="upc")
    return df.sort_values(["category", "title"]).reset_index(drop=True)


def stamp_of(path: Path) -> Optional[datetime]:
    try:
        return datetime.strptime(path.stem.split("books_", 1)[1][:15], STAMP)
    except (IndexError, ValueError):
        return None


def latest_snapshot(exclude: Path) -> Optional[Path]:
    candidates = [p for p in sorted(SNAPSHOT_DIR.glob("books_*.csv")) if p.resolve() != exclude.resolve()]
    return candidates[-1] if candidates else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-pages", type=int, help="only scrape the first N listing pages (for testing)")
    ap.add_argument("--workers", type=int, default=6, help="parallel downloads (default 6)")
    ap.add_argument("--delay", type=float, default=0.15, help="pause before each request, seconds")
    ap.add_argument("--compare", type=Path, help="snapshot CSV to compare with (default: the latest one)")
    ap.add_argument("--no-compare", action="store_true", help="skip the comparison")
    ap.add_argument("--from-snapshot", type=Path, help="build the report from a saved snapshot, no scraping")
    args = ap.parse_args()

    started = time.time()
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"Book price scraper · {SOURCE}\n")

    if args.from_snapshot:
        df = pd.read_csv(args.from_snapshot)
        scraped_at = stamp_of(args.from_snapshot) or datetime.now()
        snapshot = args.from_snapshot
        step(1, "Loading saved snapshot", f"{snapshot.name}")
        step(2, "Products in snapshot", f"{len(df):,}")
    else:
        scraped_at = datetime.now()
        links, pages = collect_links(args.max_pages, args.delay)
        step(1, "Collecting product links", f"{pages} pages · {len(links):,} products")
        records, failed = fetch_products(links, args.workers, args.delay)
        df = clean(records)
        step(2, "Downloading product details", f"{len(df):,} saved · {len(failed)} failed")
        if failed:
            failed_file = OUTPUT_DIR / f"failed_urls_{scraped_at:{STAMP}}.txt"
            failed_file.write_text("\n".join(f"{u}\t{e}" for u, e in failed), encoding="utf-8")
            print(f"      failed URLs listed in {failed_file.relative_to(ROOT)}")
        snapshot = SNAPSHOT_DIR / f"books_{scraped_at:{STAMP}}.csv"
        df.to_csv(snapshot, index=False, encoding="utf-8")

    changes, previous_label = None, None
    previous = None if args.no_compare else (args.compare or latest_snapshot(exclude=snapshot))
    if previous:
        changes = compare(pd.read_csv(previous), df)
        when = stamp_of(previous)
        previous_label = f"{when:%d %b %Y, %H:%M}" if when else previous.name
        counts = changes["change"].value_counts()
        moved = int(counts.get("Price up", 0) + counts.get("Price down", 0))
        step(3, "Comparing with previous snapshot",
             f"{moved} price changes · {counts.get('New product', 0)} new · {counts.get('Removed', 0)} removed")
    else:
        step(3, "Comparing with previous snapshot", "none found (first run)")

    out = OUTPUT_DIR / f"book_prices_{scraped_at:{STAMP}}.xlsx"
    write_report(df, str(out), scraped_at, SOURCE, changes, previous_label)
    step(4, "Writing Excel report", str(out.relative_to(ROOT)))

    took = time.time() - started
    print(f"\nDone in {int(took // 60)}m {int(took % 60):02d}s · {len(df):,} products · "
          f"{df['category'].nunique()} categories · average price £{df['price'].mean():.2f}")


if __name__ == "__main__":
    main()
