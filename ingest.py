"""
Ingestion script for the Cornell off-campus housing RAG pipeline.

Cornell URLs are fetched via requests + BeautifulSoup.
ApartmentRatings and Reddit content must be manually saved as .txt files
in documents/txt/ before running this script.

Output: cleaned plain-text files in documents/clean/
"""

import re
import sys
import requests
from bs4 import BeautifulSoup
from pathlib import Path


CORNELL_SOURCES = {
    # Source 2 (housing-search-process parent) returns 404 — removed.
    "cornell_ithaca_neighborhoods.txt": "https://scl.cornell.edu/residential-life/housing/campus-living/housing-search-process/ithaca-neighborhoods",
    "cornell_signing_lease.txt": "https://scl.cornell.edu/residential-life/housing/campus-living/housing-search-process/signing-lease",
    "cornell_rental_listings.txt": "https://scl.cornell.edu/residential-life/housing/campus-living/housing-search-process/rental-listings-resources",
    "cornell_grad_tips.txt": "https://www.gradschool.cornell.edu/announcements/grad-tips-renting/",
    "cornell_off_campus_living.txt": "https://scl.cornell.edu/residential-life/housing/campus-living",
    "cornell_safe_living.txt": "https://scl.cornell.edu/residential-life/housing/campus-living/housing-search-process/safe-living-environments",
    "cornell_off_campus_news.txt": "https://scl.cornell.edu/news-events/news/supporting-journey-campus-living-cornells-comprehensive-housing-resources",
}

# These files must be saved manually into documents/txt/ before running.
MANUAL_TXT_FILES = [
    "cayuga_apartments.txt",
    "ithaca_reviews.txt",
    "reddit_cornellhousing.txt",
    "reddit_ithaca.txt",
]

DOCS_DIR = Path("documents")
TXT_DIR = DOCS_DIR / "txt"
CLEAN_DIR = DOCS_DIR / "clean"

# CSS/id patterns for boilerplate elements that should be stripped
_BOILERPLATE_PATTERN = re.compile(
    r"nav|menu|sidebar|cookie|banner|breadcrumb|social|share|ad|promo|"
    r"footer|header|skip|overlay|modal|popup",
    re.I,
)


def _find_main_content(soup: BeautifulSoup):
    """Return the tightest element that holds the page's substantive content."""
    return (
        soup.find("article")
        or soup.find("main")
        or soup.find(id=re.compile(r"^(main[-_]?(content|article)|content[-_]?main)$", re.I))
        or soup.find("div", id=re.compile(r"^(content|main)$", re.I))
        or soup.find("body")
        or soup
    )


def _strip_boilerplate(container) -> None:
    """Remove navigation, chrome, and junk from within a content container."""
    for tag in container(["script", "style", "noscript", "iframe", "form", "button",
                           "nav", "header", "footer", "aside"]):
        tag.decompose()
    # Collect first, then decompose — avoids attrs=None on already-decomposed children
    # that are still referenced later in the find_all result list.
    to_remove = []
    for tag in container.find_all(True):
        classes = " ".join(tag.get("class", None) or [])
        tag_id = tag.get("id", None) or ""
        if _BOILERPLATE_PATTERN.search(classes) or _BOILERPLATE_PATTERN.search(tag_id):
            to_remove.append(tag)
    for tag in to_remove:
        tag.decompose()


def clean_text(raw: str) -> str:
    raw = (raw
           .replace("&amp;", "&").replace("&nbsp;", " ").replace("\xa0", " ")
           .replace("&lt;", "<").replace("&gt;", ">")
           .replace("&quot;", '"').replace("&#39;", "'").replace("&apos;", "'"))
    raw = re.sub(r"\r\n|\r", "\n", raw)
    raw = "\n".join(line.strip() for line in raw.splitlines())
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    return raw.strip()


def fetch_cornell(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; cornell-housing-research/1.0)"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    container = _find_main_content(soup)
    _strip_boilerplate(container)
    text = container.get_text(separator="\n")
    return clean_text(text)


def load_manual(filename: str) -> str:
    return clean_text((TXT_DIR / filename).read_text(encoding="utf-8"))


def main() -> int:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    TXT_DIR.mkdir(parents=True, exist_ok=True)

    missing_manual = []

    print("=== Fetching Cornell URLs ===")
    for filename, url in CORNELL_SOURCES.items():
        print(f"  {url} ...", end=" ", flush=True)
        try:
            text = fetch_cornell(url)
            (CLEAN_DIR / filename).write_text(text, encoding="utf-8")
            print(f"OK  ({len(text):,} chars)")
        except Exception as exc:
            print(f"FAILED — {exc}")

    print("\n=== Loading manual .txt files ===")
    for filename in MANUAL_TXT_FILES:
        path = TXT_DIR / filename
        if not path.exists():
            print(f"  MISSING  {filename}")
            missing_manual.append(filename)
            continue
        try:
            text = load_manual(filename)
            (CLEAN_DIR / filename).write_text(text, encoding="utf-8")
            print(f"  {filename}  ({len(text):,} chars)")
        except Exception as exc:
            print(f"  ERROR  {filename} — {exc}")

    # Spot-check: print the first 600 chars of one fetched doc so you can
    # verify cleaning worked before moving to chunking.
    sample_path = CLEAN_DIR / "cornell_ithaca_neighborhoods.txt"
    if sample_path.exists():
        print("\n--- Spot-check: cornell_ithaca_neighborhoods.txt (first 600 chars) ---")
        print(sample_path.read_text(encoding="utf-8")[:600])
        print("---")

    if missing_manual:
        print("\n[ACTION NEEDED] The following files must be saved manually before chunking:")
        for f in missing_manual:
            print(f"  documents/txt/{f}")
        print("See README.md for instructions on where to copy the content from.")

    print(f"\nCleaned files are in {CLEAN_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
