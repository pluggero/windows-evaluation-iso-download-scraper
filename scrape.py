#!/usr/bin/env python3
"""Scrape Windows Evaluation ISO download URLs from Microsoft's evaluation center."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

from tqdm import tqdm

BASE_URL = "https://www.microsoft.com/en-us/evalcenter"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

# Maps output name -> (page path, aria-label substring to disambiguate when a page has multiple ISOs)
TARGETS: dict[str, tuple[str, str | None]] = {
    "windows-11-enterprise": (
        "download-windows-11-enterprise",
        "Enterprise ISO 64-bit",
    ),
    "windows-11-enterprise-ltsc": (
        "download-windows-11-enterprise",
        "Enterprise ISO LTSC 64-bit",
    ),
    "windows-11-iot-enterprise-ltsc": (
        "download-windows-11-iot-enterprise-ltsc-eval",
        None,
    ),
    "windows-2022": ("download-windows-server-2022", None),
    "windows-2025": ("download-windows-server-2025", None),
}


class IsoLinkParser(HTMLParser):
    """Collect (aria_label, href) from <a> tags whose aria-label contains 'ISO' and the given locale."""

    def __init__(self, locale: str) -> None:
        super().__init__()
        self.locale = locale
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr = dict(attrs)
        label = attr.get("aria-label") or ""
        href = attr.get("href") or ""
        if "ISO" in label and self.locale in label and href:
            self.links.append((label, href))


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def resolve_url(fwlink: str) -> str:
    """Follow redirects and return the final URL; raises ValueError if it doesn't end in .iso."""
    req = urllib.request.Request(
        fwlink,
        method="HEAD",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        final = resp.url
    if not final.lower().endswith(".iso"):
        raise ValueError(f"Resolved URL does not end in .iso: {final}")
    return final


def download_and_hash(url: str, name: str) -> tuple[str, int]:
    """Stream-download url, return (sha256_hex, byte_count). Temp file is deleted after hashing."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    size = 0
    with tempfile.NamedTemporaryFile(delete=False, suffix=".iso") as tmp:
        tmp_path = tmp.name
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length") or 0) or None
                with tqdm(
                    total=total, unit="B", unit_scale=True, desc=name, leave=True
                ) as bar:
                    while chunk := resp.read(1 << 20):  # 1 MiB chunks
                        tmp.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                        bar.update(len(chunk))
        finally:
            tmp.close()
            os.unlink(tmp_path)
    return digest.hexdigest(), size


def scrape_target(name: str, page_path: str, hint: str | None, locale: str) -> dict:
    url = f"{BASE_URL}/{page_path}"
    print(f"[{name}] fetching {url}")
    html = fetch_html(url)

    parser = IsoLinkParser(locale)
    parser.feed(html)

    if not parser.links:
        raise RuntimeError(f"No ISO links found on {url}")

    if hint:
        matches = [
            (label, href)
            for label, href in parser.links
            if hint.lower() in label.lower()
        ]
    else:
        matches = parser.links

    if not matches:
        raise RuntimeError(
            f"No ISO link matching hint {hint!r} found among: {[l for l, _ in parser.links]}"
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Ambiguous: multiple ISO links match hint {hint!r}: {[l for l, _ in matches]}"
        )

    label, fwlink = matches[0]
    print(f"[{name}] resolving {fwlink!r}")
    final_url = resolve_url(fwlink)
    print(f"[{name}] downloading and hashing {final_url}")
    sha256, size = download_and_hash(final_url, name)

    return {
        "name": name,
        "locale": locale,
        "url": final_url,
        "fwlink": fwlink,
        "sha256": sha256,
        "size": size,
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Windows Evaluation ISO download URLs."
    )
    parser.add_argument(
        "targets",
        nargs="*",
        metavar="TARGET",
        help=f"Targets to scrape (default: all). Choices: {', '.join(TARGETS)}",
    )
    parser.add_argument(
        "--locale",
        default="en-US",
        metavar="LOCALE",
        help="Locale of the ISO to download (default: en-US)",
    )
    args = parser.parse_args()

    requested = set(args.targets) if args.targets else set(TARGETS)
    unknown = requested - set(TARGETS)
    if unknown:
        parser.error(
            f"Unknown targets: {', '.join(sorted(unknown))}. Valid: {', '.join(TARGETS)}"
        )

    os.makedirs("data", exist_ok=True)
    failed: list[str] = []

    for name, (page_path, hint) in TARGETS.items():
        if name not in requested:
            continue
        try:
            result = scrape_target(name, page_path, hint, args.locale)
            out_path = os.path.join("data", f"{name}.json")
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)
                f.write("\n")
            print(f"[{name}] wrote {out_path}")
        except Exception as exc:
            print(f"[{name}] ERROR: {exc}", file=sys.stderr)
            failed.append(name)

    if failed:
        print(f"\nFailed targets: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
