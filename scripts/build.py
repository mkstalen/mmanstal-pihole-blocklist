#!/usr/bin/env python3
"""Download the blocklists in sources.txt, merge and de-duplicate them,
apply allowlist.txt and extra-blocks.txt, and write blocklist.txt
as a plain one-domain-per-line list that Pi-hole can use directly.

Exits non-zero (and leaves blocklist.txt untouched) if any source fails
to download or the merged list shrinks suspiciously, so a bad run never
replaces a good list.
"""
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "blocklist.txt"
MIN_SHRINK_RATIO = 0.5  # refuse to publish if the list drops below half its previous size

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]$"
)
IGNORED = {
    "localhost", "localhost.localdomain", "local", "broadcasthost",
    "ip6-localhost", "ip6-loopback", "ip6-localnet", "ip6-mcastprefix",
    "ip6-allnodes", "ip6-allrouters", "ip6-allhosts", "0.0.0.0",
}
HOSTS_IPS = {"0.0.0.0", "127.0.0.1", "::", "::1", "::0"}


def read_list(path):
    if not path.exists():
        return []
    return [l.strip() for l in path.read_text().splitlines()
            if l.strip() and not l.strip().startswith("#")]


def parse_line(line):
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith("!") or line.startswith("["):
        return None
    if line.startswith("||"):  # Adblock style: ||domain^
        if "$" in line or "/" in line or "*" in line:
            return None
        domain = line[2:].rstrip("^").rstrip("|")
    else:
        parts = line.split()
        if len(parts) >= 2 and parts[0] in HOSTS_IPS:
            domain = parts[1]
        elif len(parts) == 1:
            domain = parts[0]
        else:
            return None
    domain = domain.lower().rstrip(".")
    if domain in IGNORED or not DOMAIN_RE.match(domain):
        return None
    return domain


def fetch(url, attempts=3):
    req = urllib.request.Request(url, headers={"User-Agent": "pihole-blocklist-merger/1.0"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            if attempt == attempts:
                raise
            time.sleep(10 * attempt)


def main():
    sources = read_list(ROOT / "sources.txt")
    domains = set()
    failures = []
    stats = []
    for url in sources:
        try:
            text = fetch(url)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{url}: {exc}")
            continue
        found = {d for d in map(parse_line, text.splitlines()) if d}
        stats.append((url, len(found)))
        domains |= found
        print(f"{len(found):>9,}  {url}")

    if failures:
        print("\nFailed to download:", *failures, sep="\n  ", file=sys.stderr)
        print("Keeping the previous blocklist.txt unchanged.", file=sys.stderr)
        sys.exit(1)

    extra = {d for d in map(parse_line, read_list(ROOT / "extra-blocks.txt")) if d}
    allow = {l.lower().rstrip(".") for l in read_list(ROOT / "allowlist.txt")}
    domains = (domains | extra) - allow

    if OUTPUT.exists():
        previous = sum(1 for l in OUTPUT.read_text().splitlines() if l and not l.startswith("#"))
        if previous and len(domains) < previous * MIN_SHRINK_RATIO:
            print(f"Merged list shrank from {previous:,} to {len(domains):,} domains; "
                  "refusing to publish.", file=sys.stderr)
            sys.exit(1)

    body = "\n".join(sorted(domains)) + "\n"
    if OUTPUT.exists():
        old_body = "\n".join(l for l in OUTPUT.read_text().splitlines() if not l.startswith("#")) + "\n"
        if old_body == body:
            print(f"\nNo changes ({len(domains):,} domains).")
            return

    header = [
        "# Merged Pi-hole blocklist",
        f"# Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"# Domains: {len(domains):,}",
        "# Sources:",
        *[f"#   {url} ({count:,})" for url, count in stats],
        "",
    ]
    OUTPUT.write_text("\n".join(header) + body)
    print(f"\nWrote {len(domains):,} unique domains to {OUTPUT.name}")


if __name__ == "__main__":
    main()
