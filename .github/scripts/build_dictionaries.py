"""Build and publish the dictionaries of one source Wiktionary, whose dump is already downloaded and parsed.

Environment:
  SOURCE, SNAPSHOT   the Wiktionary and its dump (YYYYMMDD)
  LOCALES            the locales to build, in this order (space separated)
  JOB_START          epoch seconds when the job started
  BUDGET_MINUTES     no new dictionary is started after that many minutes of job: the rest waits for the next run
  CWD                the working folder that holds data/
  FORMATS            the --format value of --convert
  MIN_WORDS          dictionaries with fewer entries are not published
Each dictionary becomes the release `dict-<words>-<definitions>-<snapshot>`, and its releases of older dumps are
deleted. Pairs with no word, too few, or that fail, are recorded in `status-<source>.json` of the release
`build-status`, so that they are not retried before the next dump.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from mediawiki_langcodes import code_to_name

STATUS_RELEASE = "build-status"
REPO = os.environ["GITHUB_REPOSITORY"]
SOURCE = os.environ["SOURCE"]
SNAPSHOT = os.environ["SNAPSHOT"]
DATA = Path(os.environ["CWD"]) / "data"


def run(*args: str) -> tuple[int, str]:
    """Run a command, showing its output as it comes, and return its exit code and output."""
    print(f"$ {' '.join(args)}", flush=True)
    lines = []
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace") as proc:
        assert proc.stdout
        for line in proc.stdout:
            print(line, end="", flush=True)
            lines.append(line)
    return proc.returncode, "".join(lines)


def gh(*args: str, check: bool = True) -> str:
    return subprocess.run(["gh", *args], check=check, capture_output=True, text=True).stdout


def name(code: str) -> str:
    return code_to_name(code, "en") or code


def notes(src: str, dst: str) -> str:
    date = f"{SNAPSHOT[:4]}-{SNAPSHOT[4:6]}-{SNAPSHOT[6:]}"
    what = f"{name(dst)} words explained in {name(src)}"
    locale = src if src == dst else f"{src}:{dst}"
    return f"""{what}, from the {name(src)} Wiktionary dump of {date} (locale `{locale}`).

| File | For |
|------|-----|
| `dicthtml-{dst}-{src}.zip` | Kobo: copy it, as it is, into `.kobo/custom-dict/` |
| `dict-{dst}-{src}.zip` | KOReader: unzip it into `koreader/data/dict/`; GoldenDict, Boox... |
| `dict-{dst}-{src}-nosyn.zip` | StarDict readers that ignore the `.syn` file (Boox) |
| `dict-{dst}-{src}.mobi.zip` | Kindle: unzip it, and copy the `.mobi` file into `documents/dictionaries/` |
| `dict-{dst}-{src}.df.bz2` | DictFile (PocketBook, Vivlio) |
| `dictorg-{dst}-{src}.zip` | DICT.org (dictd) |

The `-noetym` files are the same dictionaries without etymologies. Each file has its SHA-256 checksum next to it.
The definitions come from Wiktionary, under the Creative Commons Attribution-ShareAlike license.
"""


def publish(src: str, dst: str) -> None:
    tag = f"dict-{dst}-{src}-{SNAPSHOT}"
    date = f"{SNAPSHOT[:4]}-{SNAPSHOT[4:6]}-{SNAPSHOT[6:]}"
    title = (
        f"{name(dst)} dictionary ({date} dump)" if src == dst else f"{name(dst)}-{name(src)} dictionary ({date} dump)"
    )
    files = sorted(str(f) for f in (DATA / dst / src / "output").iterdir() if f.is_file())
    gh("release", "delete", tag, "-R", REPO, "--yes", "--cleanup-tag", check=False)
    notes_file = Path("notes.md")
    notes_file.write_text(notes(src, dst), encoding="utf-8")
    gh(
        "release",
        "create",
        tag,
        "-R",
        REPO,
        "--target",
        os.environ["GITHUB_SHA"],
        "--latest=false",
        "--title",
        title,
        "--notes-file",
        str(notes_file),
        *files,
    )
    # Older dumps of the same dictionary
    prefix = f"dict-{dst}-{src}-"
    for old in gh("release", "list", "-R", REPO, "--limit", "10000", "--json", "tagName", "-q", ".[].tagName").split():
        if old.startswith(prefix) and old != tag and old[len(prefix) :].isdigit() and len(old) == len(tag):
            gh("release", "delete", old, "-R", REPO, "--yes", "--cleanup-tag", check=False)


def save_status(recorded: dict[str, str]) -> None:
    """Merge this run's empty/failed pairs into status-<source>.json (only this job writes it) and upload it."""
    file = Path(f"status-{SOURCE}.json")
    gh("release", "download", STATUS_RELEASE, "-R", REPO, "-p", file.name, "--clobber", check=False)
    status = json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {}
    status = {SNAPSHOT: status.get(SNAPSHOT, {}) | recorded}  # the pairs of older dumps are retried with this one
    file.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
    if not gh("release", "view", STATUS_RELEASE, "-R", REPO, "--json", "tagName", check=False):
        gh(
            "release",
            "create",
            STATUS_RELEASE,
            "-R",
            REPO,
            "--latest=false",
            "--title",
            "Build status",
            "--notes",
            "Used by the Dictionaries workflow: the pairs found empty or failing for each dump.",
            check=False,
        )
    gh("release", "upload", STATUS_RELEASE, "-R", REPO, str(file), "--clobber")


def count_words(src: str, dst: str) -> int:
    """Entries rendered for the dictionary (the JSON written by --render)."""
    files = sorted((DATA / dst / src).glob("data-*.json"))
    return len(json.loads(files[-1].read_text(encoding="utf-8"))) if files else 0


def main() -> int:
    budget = int(os.environ.get("BUDGET_MINUTES", "240")) * 60
    min_words = int(os.environ.get("MIN_WORDS", "1000"))
    job_start = int(os.environ["JOB_START"])
    results: dict[str, str] = {}
    recorded: dict[str, str] = {}

    for locale in os.environ["LOCALES"].split():
        if time.time() - job_start > budget:
            results[locale] = "postponed to the next run"
            continue
        src, _, dst = locale.partition(":")
        dst = dst or src
        log = Path("logs") / dst / f"{src}.log"
        size = log.stat().st_size if log.is_file() else 0
        started = time.monotonic()
        code, output = run(sys.executable, "-m", "wikidict", locale, "--render")
        if code:
            if log.is_file():
                with log.open(encoding="utf-8", errors="replace") as fh:
                    fh.seek(size)
                    output += fh.read()
            results[locale] = recorded[locale] = "empty" if "No word found" in output else "failed (render)"
        elif (words := count_words(src, dst)) < min_words:
            results[locale] = recorded[locale] = f"too small ({words} words)"
        elif run(sys.executable, "-m", "wikidict", locale, "--convert", f"--format={os.environ['FORMATS']}")[0]:
            results[locale] = recorded[locale] = "failed (convert)"
        else:
            try:
                publish(src, dst)
                results[locale] = f"published in {(time.monotonic() - started) / 60:.0f} min"
            except subprocess.CalledProcessError as exc:
                results[locale] = f"failed (release: {exc.stderr.strip()[:200]})"
        shutil.rmtree(DATA / dst / src, ignore_errors=True)  # the disk of the runner is limited
        print(f"{locale}: {results[locale]}", flush=True)

    if recorded:
        save_status(recorded)

    with open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a", encoding="utf-8") as fh:
        fh.write(f"### {SOURCE} Wiktionary, dump {SNAPSHOT}\n\n| Locale | Result |\n|---|---|\n")
        fh.writelines(f"| `{loc}` | {res} |\n" for loc, res in results.items())
    return 0


if __name__ == "__main__":
    sys.exit(main())
