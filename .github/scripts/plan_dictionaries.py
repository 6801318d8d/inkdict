"""Plan the dictionaries to build: one job per source Wiktionary that has dictionaries missing for its newest dump.

Environment:
  LANGUAGES       the languages to build dictionaries for (space separated)
  BILINGUAL_WITH  "all": every pair among LANGUAGES; a list of languages: only the pairs where one of them is
                  either side; empty: no bilingual pair
  MONOLINGUAL_ONLY  Wiktionaries that cannot be the source of a bilingual dictionary (no `foreign_head_sections`)
  EXTRA_LOCALES   locales always built (e.g. "it:en en:it")
  LOCALES         manual runs: only these locales
  FORCE           "true": build even what is already released or recorded as empty/failed
Writes `builds=<JSON list of {source, snapshot, locales}>` to $GITHUB_OUTPUT.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "inkdict (https://github.com/6801318d8d/inkdict)"
DUMPS = "https://dumps.wikimedia.org/{src}wiktionary/"
STATUS_RELEASE = "build-status"


def request(url: str, method: str = "GET") -> str:
    req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode() if method == "GET" else ""


def latest_dump(src: str) -> str | None:
    """The newest dump whose file is complete (the one being written is skipped, as `--download` does)."""
    try:
        snapshots = sorted(set(re.findall(r'href="(\d{8})/"', request(DUMPS.format(src=src)))), reverse=True)
    except urllib.error.URLError as exc:
        print(f"::warning::{src}: cannot list the dumps ({exc})")
        return None
    for snapshot in snapshots:
        url = f"{DUMPS.format(src=src)}{snapshot}/{src}wiktionary-{snapshot}-pages-articles.xml.bz2"
        try:
            request(url, method="HEAD")
            return str(snapshot)
        except urllib.error.HTTPError:
            continue
    return None


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def wanted_locales() -> dict[str, list[str]]:
    """Source Wiktionary -> locales to build from it."""
    if manual := os.environ.get("LOCALES", "").split():
        locales = manual
    else:
        langs = os.environ["LANGUAGES"].split()
        with_ = os.environ.get("BILINGUAL_WITH", "").split()
        monolingual_only = os.environ.get("MONOLINGUAL_ONLY", "").split()
        locales = list(langs)  # monolingual
        for src in langs:
            for dst in langs:
                if src in monolingual_only:
                    break
                if dst != src and ("all" in with_ or src in with_ or dst in with_):
                    locales.append(f"{src}:{dst}")
        locales += [loc for loc in os.environ.get("EXTRA_LOCALES", "").split() if loc not in locales]
    by_source: dict[str, list[str]] = {}
    for locale in locales:
        by_source.setdefault(locale.split(":", 1)[0], []).append(locale)
    return by_source


def tag(locale: str, snapshot: str) -> str:
    src, _, dst = locale.partition(":")
    return f"dict-{dst or src}-{src}-{snapshot}"


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    force = os.environ.get("FORCE") == "true"
    released = set(
        gh("release", "list", "-R", repo, "--limit", "10000", "--json", "tagName", "-q", ".[].tagName").split()
    )

    # Pairs found empty or failing for a dump, recorded by the build jobs: not retried before the next dump
    status: dict[str, dict[str, dict[str, str]]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["gh", "release", "download", STATUS_RELEASE, "-R", repo, "-p", "status-*.json", "-D", tmp],
            check=False,
            capture_output=True,
        )
        for file in Path(tmp).glob("status-*.json"):
            status[file.stem.removeprefix("status-")] = json.loads(file.read_text(encoding="utf-8"))

    builds = []
    for src, locales in sorted(wanted_locales().items()):
        if not (snapshot := latest_dump(src)):
            print(f"::warning::{src}: no complete dump found")
            continue
        recorded = status.get(src, {}).get(snapshot, {})
        todo = [loc for loc in locales if force or (tag(loc, snapshot) not in released and loc not in recorded)]
        done = len(locales) - len(todo)
        print(f"{src} {snapshot}: {len(todo)} to build, {done} released or recorded")
        if todo:
            builds.append({"source": src, "snapshot": snapshot, "locales": " ".join(todo)})

    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
        fh.write(f"builds={json.dumps(builds)}\n")
    print(f"{len(builds)} source Wiktionaries to build, {sum(len(b['locales'].split()) for b in builds)} dictionaries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
