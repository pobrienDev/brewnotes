"""Rebuild data/styles_bjcp_2021.json from the BJCP 2021 style pages.

Run once, by hand, when the guideline numbers need re-checking:

    cd backend && uv run python tools/bjcp_2021_vitals.py /tmp/bjcp-cache

Only facts are taken from the pages: category and style codes, names, the page URL and the
vital statistics (OG, FG, ABV, IBU, SRM). Summaries are BrewNotes' own words and are read from
the existing data file so they survive a rebuild; a new style gets an empty summary to fill in.
Pages are fetched sequentially with a pause and cached in the given directory. See the plan,
Appendix B, on what may be stored from the guidelines.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

INDEX_URL = "https://www.bjcp.org/beer-styles/beer-style-guidelines/"
STYLE_URL = re.compile(r"https://www\.bjcp\.org/style/2021/([^/]+)/([^/]+)/([^/]+)/$")
USER_AGENT = "BrewNotes (personal project; github.com/pobrienDev/brewnotes)"
PAUSE_S = 0.4
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "styles_bjcp_2021.json"

NUM = r"([0-9]+(?:\.[0-9]+)?)"
DASH = r"\s*[-–]\s*"  # noqa: RUF001  # the pages use both hyphens and en dashes
METRICS = ("og", "fg", "abv", "ibu", "srm")
# Styles whose statistics the pages present in prose or with labels, transcribed by hand.
OVERRIDES: dict[str, dict[str, list[list[Any]]]] = {
    "saison": {
        "og": [[1.048, 1.065, "standard"]],
        "fg": [[1.002, 1.008, "standard"]],
        "abv": [[3.5, 5.0, "table"], [5.0, 7.0, "standard"], [7.0, 9.5, "super"]],
        "ibu": [[20, 35]],
        "srm": [[5, 14, "pale"], [15, 22, "dark"]],
    },
    "fruit-lambic": {
        "og": [[1.040, 1.060]],
        "fg": [[1.000, 1.010]],
        "abv": [[5.0, 7.0]],
        "ibu": [[0, 10]],
        "srm": [[3, 7]],
    },
    "wheatwine": {
        "og": [[1.080, 1.120]],
        "fg": [[1.016, 1.030]],
        "abv": [[8.0, 12.0]],
        "ibu": [[30, 60]],
        "srm": [[6, 14]],
    },
    "specialty-ipa": {},
    "historical-beer-kellerbier": {},
}
# Codes whose styles the guidelines list as variants of one parent entry.
PARENTS = {"21B": ("specialty-ipa", "Specialty IPA"), "27A": ("historical-beer", "Historical Beer")}


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return str(response.read().decode("utf-8", "ignore"))


def text_of(page: str) -> str:
    stripped = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    return html.unescape(re.sub(r"\s+", " ", stripped))


def grab(metric: str, text: str) -> list[float] | None:
    match = re.search(rf"\b{metric}\s*{NUM}%?{DASH}{NUM}%?", text)
    return [float(match.group(1)), float(match.group(2))] if match else None


def parse_ranges(vitals: str) -> dict[str, list[list[Any]]]:
    varies = re.search(r"\b(vary|varies|variable|same as base)\b", vitals, re.I)
    if not vitals or (varies and not re.search(r"\bOG\s*[0-9]", vitals)):
        return {}
    ranges: dict[str, list[list[Any]]] = {}
    for metric in METRICS:
        found = grab(metric.upper(), vitals)
        if found:
            ranges[metric] = [found]
    return ranges


def collect(cache: Path) -> list[dict[str, Any]]:
    cache.mkdir(parents=True, exist_ok=True)
    index = fetch(INDEX_URL)
    links = sorted(set(re.findall(r'href="(https://www\.bjcp\.org/style/2021/[^"#]+)"', index)))
    records = []
    for url in links:
        match = STYLE_URL.match(url)
        if not match:
            continue
        category, code, slug = match.groups()
        path = cache / f"{code}_{slug}.html"
        if not path.exists():
            path.write_text(fetch(url))
            time.sleep(PAUSE_S)
        page = path.read_text()
        text = text_of(page)
        title = re.search(r"<h1[^>]*>(.*?)</h1>", page, flags=re.S)
        name = html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else slug
        name = re.sub(r"^\w+\.\s*", "", name)
        vitals = re.search(r"Vital Statistics(.*?)(Commercial Examples|Past Revision|$)", text)
        cat_name = re.search(
            r'href="https://www\.bjcp\.org/style/2021/'
            + re.escape(category)
            + r'/?"[^>]*>(.*?)</a>',
            page,
            flags=re.S,
        )
        records.append(
            {
                "category": category,
                "category_name": re.sub(
                    r"^\d+\.\s*",
                    "",
                    html.unescape(re.sub(r"<[^>]+>", "", cat_name.group(1))).strip()
                    if cat_name
                    else "",
                ),
                "code": code,
                "slug": slug,
                "name": name,
                "url": url,
                "ranges": OVERRIDES.get(slug, parse_ranges(vitals.group(1) if vitals else "")),
            }
        )
    return records


def existing_summaries() -> dict[str, str]:
    if not DATA_FILE.exists():
        return {}
    data = json.loads(DATA_FILE.read_text())
    summaries: dict[str, str] = {}
    for category in data["categories"]:
        for style in category["styles"]:
            summaries[style["slug"]] = style.get("summary", "")
            for variant in style.get("variants", []):
                summaries[variant["slug"]] = variant.get("summary", "")
    return summaries


def build(records: list[dict[str, Any]], summaries: dict[str, str]) -> dict[str, Any]:
    categories: dict[str, dict[str, Any]] = {}
    buckets: dict[str, dict[tuple[str, str], Any]] = {}
    for record in records:
        cat = record["category"]
        categories.setdefault(cat, {"code": cat, "name": record["category_name"], "styles": []})
        entry = {
            "slug": record["slug"],
            "name": record["name"],
            "summary": summaries.get(record["slug"], ""),
            "source_url": record["url"],
            "ranges": record["ranges"],
        }
        code = record["code"]
        if code in PARENTS and record["slug"] != PARENTS[code][0]:
            entry["name"] = entry["name"].split(": ", 1)[-1]
            buckets.setdefault(cat, {}).setdefault(("variant", code), []).append(entry)
        else:
            entry["code"] = code
            buckets.setdefault(cat, {})[("style", code)] = entry
    for cat, bucket in buckets.items():
        styles = [entry for (kind, _), entry in bucket.items() if kind == "style"]
        for code, (slug, name) in PARENTS.items():
            variants = bucket.get(("variant", code))
            if not variants:
                continue
            parent = bucket.get(("style", code))
            if parent is None:
                parent = {
                    "code": code,
                    "slug": slug,
                    "name": name,
                    "summary": summaries.get(slug, ""),
                    "source_url": f"https://www.bjcp.org/style/2021/{cat}/",
                    "ranges": {},
                }
                styles.append(parent)
            parent["variants"] = sorted(variants, key=lambda v: str(v["name"]))
        styles.sort(key=lambda s: str(s["code"]))
        categories[cat]["styles"] = styles
    ordered = sorted(categories, key=lambda c: int(c) if c.isdigit() else 1000)
    return {
        "guideline": "BJCP",
        "version": "2021",
        "source": INDEX_URL,
        "note": (
            "Numeric ranges, codes and names come from the BJCP 2021 Beer Style Guidelines; "
            "summaries are written for BrewNotes and are not guideline text."
        ),
        "categories": [categories[c] for c in ordered],
    }


def main() -> None:
    cache = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/bjcp-cache")  # noqa: S108
    records = collect(cache)
    data = build(records, existing_summaries())
    DATA_FILE.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    styles = sum(len(c["styles"]) for c in data["categories"])
    variants = sum(len(s.get("variants", [])) for c in data["categories"] for s in c["styles"])
    missing = [
        s["slug"]
        for c in data["categories"]
        for s in c["styles"] + [v for s in c["styles"] for v in s.get("variants", [])]
        if not s["summary"]
    ]
    print(f"wrote {DATA_FILE}: {styles} styles, {variants} variants")
    if missing:
        print("styles without a summary (write one):", ", ".join(missing))


if __name__ == "__main__":
    main()
