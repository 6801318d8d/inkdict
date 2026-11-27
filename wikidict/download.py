"""Retrieve Wiktionary data."""

from __future__ import annotations

import logging
import os
import re
from datetime import timedelta
from pathlib import Path
from time import monotonic

from requests.exceptions import HTTPError
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from . import constants, utils

log = logging.getLogger(__name__)


def fetch_snapshots(locale: str) -> list[str]:
    """Fetch available snapshots.
    Return a list of sorted dates.
    """
    if forced_snapshot := os.environ.get("FORCE_SNAPSHOT"):
        return [forced_snapshot]

    with constants.SESSION.get(constants.BASE_URL.format(locale=locale)) as req:
        req.raise_for_status()
        return sorted(re.findall(r'href="(\d+)/"', req.text))


def fetch_pages(date: str, locale: str, output: Path) -> None:
    """Download all pages, current versions only.
    Return the path of the XML file BZ2 compressed.
    """
    if output.is_file():
        return

    url = constants.DUMP_URL.format(locale=locale, snapshot=date)
    with constants.SESSION.get(url, stream=True) as req:
        req.raise_for_status()

        # Ensure the folder exists
        output.parent.mkdir(exist_ok=True, parents=True)

        # Get total file size from headers
        total_size = int(req.headers.get("content-length", 0))

        # Create a rich progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(complete_style="green", finished_style="bold green"),
            DownloadColumn(),
            TransferSpeedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task(f"[cyan][{locale.upper()}] Downloading dump", total=total_size)

            with output.open(mode="wb") as fh:
                for chunk in req.iter_content(chunk_size=1024**2):
                    size = fh.write(chunk)
                    progress.update(task, advance=size)

            # Final update to ensure we show 100%
            progress.update(
                task,
                completed=total_size,
                description=f"[magenta][{locale.upper()}] Downloaded dump [green]✓[/green]",
            )


def get_output_file_compressed(locale: str, snapshot: str) -> Path:
    return Path(os.getenv("CWD", "")) / "data" / locale / f"pages-{snapshot}.xml.bz2"


def main(locale: str) -> int:
    """Entry point."""

    start = monotonic()
    locale = utils.guess_lang_origin(locale)

    # Get the snapshot to handle
    snapshots = fetch_snapshots(locale)

    # Fetch the snapshot file (--parse reads it compressed)
    for snapshot in snapshots[::-1]:
        file_compressed = get_output_file_compressed(locale, snapshot)
        try:
            fetch_pages(snapshot, locale, file_compressed)
            break
        except HTTPError as exc:
            file_compressed.unlink(missing_ok=True)
            if exc.response.status_code != 404:
                raise
            log.warning("Wiktionary dump is ongoing ... ")
            log.info("Will use the previous one.")
    else:
        log.error("No Wiktionary dump found!")
        return 1

    log.info("Retrieval done in %s!", timedelta(seconds=monotonic() - start))
    return 0
