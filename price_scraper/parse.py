"""HTML parsing: listing pages -> product links, product pages -> clean records."""
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def parse_price(text: str) -> Optional[float]:
    """'£51.77' -> 51.77. Returns None if there is no number."""
    match = re.search(r"\d[\d,]*\.?\d*", text or "")
    return float(match.group().replace(",", "")) if match else None


def parse_stock(text: str) -> int:
    """'In stock (22 available)' -> 22. Out of stock -> 0."""
    match = re.search(r"\((\d+)\s+available\)", text or "")
    return int(match.group(1)) if match else 0


def parse_listing(html: str, page_url: str) -> tuple[list[str], Optional[str]]:
    """Return (product URLs on this page, URL of the next page or None)."""
    soup = BeautifulSoup(html, "lxml")
    links = [urljoin(page_url, a["href"]) for a in soup.select("article.product_pod h3 a[href]")]
    next_link = soup.select_one("li.next a[href]")
    return links, urljoin(page_url, next_link["href"]) if next_link else None


def parse_product(html: str, url: str) -> dict:
    """Extract one product page into a flat record."""
    soup = BeautifulSoup(html, "lxml")
    main = soup.select_one("div.product_main")

    info = {
        row.th.get_text(strip=True): row.td.get_text(strip=True)
        for row in soup.select("table.table-striped tr")
        if row.th and row.td
    }
    crumbs = [li.get_text(strip=True) for li in soup.select("ul.breadcrumb li")]
    rating_tag = main.select_one("p.star-rating") if main else None
    rating_word = next((c for c in (rating_tag.get("class", []) if rating_tag else []) if c in RATING_WORDS), None)
    desc_header = soup.select_one("#product_description")
    description = desc_header.find_next_sibling("p").get_text(strip=True) if desc_header else ""
    availability = info.get("Availability", "")
    image = soup.select_one("#product_gallery img[src]")

    return {
        "title": main.h1.get_text(strip=True) if main and main.h1 else "",
        "category": crumbs[2] if len(crumbs) >= 4 else "",
        "price": parse_price(info.get("Price (incl. tax)", "")),
        "price_excl_tax": parse_price(info.get("Price (excl. tax)", "")),
        "rating": RATING_WORDS.get(rating_word, 0),
        "stock": parse_stock(availability),
        "availability": availability,
        "reviews": int(info.get("Number of reviews", "0") or 0),
        "upc": info.get("UPC", ""),
        "url": url,
        "image_url": urljoin(url, image["src"]) if image else "",
        "description": description,
    }
