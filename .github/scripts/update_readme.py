"""Write the list of the published dictionaries into README.md, between its two markers: one collapsible group per
language of the words, with the monolingual dictionary first and then the bilingual ones by language of the
definitions, each linked to its release. Run by the Dictionaries workflow after its builds; by hand (needs gh and
mediawiki-langcodes): python .github/scripts/update_readme.py
"""

import os
import re
import subprocess
from pathlib import Path

from mediawiki_langcodes import code_to_name

REPO = os.environ.get("GITHUB_REPOSITORY", "6801318d8d/inkdict")
README = Path(__file__).resolve().parents[2] / "README.md"
START = "<!-- dictionaries:start (written by .github/scripts/update_readme.py) -->"
END = "<!-- dictionaries:end -->"
TAG = re.compile(r"^dict-([a-z]+)-([a-z]+)-(\d{8})$")


def name(code: str) -> str:
    return code_to_name(code, "en") or code


def section(tags: list[str]) -> str:
    """The text between the markers, for these release tags.

    >>> print(section(["dict-zh-pl-20261101", "build-status", "dict-zh-zh-20261020", "dict-zh-pl-20261020"]))
    <!-- dictionaries:start (written by .github/scripts/update_readme.py) -->
    2 dictionaries, grouped by the language of their words:
    <BLANKLINE>
    <details><summary>Chinese (2)</summary>
    <BLANKLINE>
    - [Monolingual](https://github.com/6801318d8d/inkdict/releases/tag/dict-zh-zh-20261020) (2026-10-20 dump)
    - [Chinese-Polish](https://github.com/6801318d8d/inkdict/releases/tag/dict-zh-pl-20261101) (2026-11-01 dump)
    <BLANKLINE>
    </details>
    <BLANKLINE>
    <!-- dictionaries:end -->
    """
    newest: dict[tuple[str, str], str] = {}  # the release of an older dump lives on until its replacement is published
    for tag in tags:
        if m := TAG.match(tag):
            words, defs, snapshot = m.groups()
            newest[(words, defs)] = max(newest.get((words, defs), ""), snapshot)
    groups: dict[str, list[tuple[bool, str, str, str]]] = {}
    for (words, defs), snapshot in newest.items():
        groups.setdefault(words, []).append((words != defs, name(defs), defs, snapshot))
    lines = [START, f"{len(newest)} dictionaries, grouped by the language of their words:", ""]
    for words in sorted(groups, key=name):
        lines += [f"<details><summary>{name(words)} ({len(groups[words])})</summary>", ""]
        for bilingual, defs_name, defs, snapshot in sorted(groups[words]):  # monolingual (False) first
            label = f"{name(words)}-{defs_name}" if bilingual else "Monolingual"
            url = f"https://github.com/{REPO}/releases/tag/dict-{words}-{defs}-{snapshot}"
            lines.append(f"- [{label}]({url}) ({snapshot[:4]}-{snapshot[4:6]}-{snapshot[6:]} dump)")
        lines += ["", "</details>", ""]
    lines.append(END)
    return "\n".join(lines)


def main() -> None:
    tags = subprocess.run(
        ["gh", "release", "list", "-R", REPO, "--limit", "10000", "--json", "tagName", "-q", ".[].tagName"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    text = README.read_text(encoding="utf-8")
    start, end = text.index(START), text.index(END) + len(END)
    new = text[:start] + section(tags) + text[end:]
    if new == text:
        print("README.md unchanged")
        return
    README.write_text(new, encoding="utf-8", newline="\n")
    print("README.md updated")


if __name__ == "__main__":
    main()
