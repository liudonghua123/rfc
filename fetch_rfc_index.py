#!/usr/bin/env python3
"""Fetch RFC search API key and build index/facet data from Typesense."""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib import error, request

SEARCH_URL = "https://www.rfc-editor.org/search/"
TYPESENSE_URL = "https://typesense.ietf.org/multi_search"
OUTPUT_DIR = Path(".")
INDEX_FILE = OUTPUT_DIR / "index.json"
FACET_FILE = OUTPUT_DIR / "facet_counts.json"
PER_PAGE = 250


def fetch_text(url: str, headers: Dict[str, str] | None = None) -> str:
    req_headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if headers:
        req_headers.update(headers)
    req = request.Request(url, headers=req_headers, method="GET")
    with request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def extract_typesense_api_key(html: str) -> str:
    m = re.search(r'name="x-typesense-api-key"\s+value="([^"]+)"', html)
    if not m:
        raise ValueError("Could not find x-typesense-api-key in the search page HTML.")
    return m.group(1)


def post_multi_search(api_key: str, page: int, per_page: int = PER_PAGE) -> Dict[str, Any]:
    body = {
        "searches": [
            {
                "preset": "red",
                "collection": "docs",
                "q": "*",
                "facet_by": "area.full,authors.name,flags.hiddenDefault,group.full,publicationDate,status.name,stream.name",
                "max_facet_values": 200,
                "page": page,
                "per_page": per_page,
            }
        ]
    }
    data = json.dumps(body).encode("utf-8")
    req = request.Request(
        f"{TYPESENSE_URL}?x-typesense-api-key={api_key}",
        data=data,
        headers={
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "referrer": "https://www.rfc-editor.org/",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    try:
        html = fetch_text(SEARCH_URL)
        api_key = extract_typesense_api_key(html)
        print(f"Fetched x-typesense-api-key: {api_key}")
    except (error.URLError, ValueError) as exc:
        print(f"Failed to fetch x-typesense-api-key: {exc}", file=sys.stderr)
        sys.exit(1)

    first_page = post_multi_search(api_key, page=1, per_page=PER_PAGE)
    if not first_page.get("results"):
        raise ValueError("No results returned from Typesense API.")

    first_result = first_page["results"][0]
    total_found = int(first_result.get("found", 0))
    facet_counts = first_result.get("facet_counts", [])
    hits = [item.get("document", item) for item in first_result.get("hits", [])]

    all_hits = list(hits)
    page = 1
    while len(all_hits) < total_found:
        page += 1
        page_result = post_multi_search(api_key, page=page, per_page=PER_PAGE)
        current_result = page_result["results"][0]
        current_hits = [item.get("document", item) for item in current_result.get("hits", [])]
        all_hits.extend(current_hits)
        print(f"Fetched page {page}: {len(current_hits)} hits (total {len(all_hits)}/{total_found})")

    index_payload = {
        "total": total_found,
        "data": all_hits,
    }

    INDEX_FILE.write_text(json.dumps(index_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    FACET_FILE.write_text(json.dumps(facet_counts, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Saved {INDEX_FILE} with {len(all_hits)} hits")
    print(f"Saved {FACET_FILE} with {len(facet_counts)} facet groups")


if __name__ == "__main__":
    main()
