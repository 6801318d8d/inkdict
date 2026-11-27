"""Rewrite two generated parts of README.md, each between its two markers:
- the table of contents: a link to every section (## headings) and subsection (###);
- the list of the published dictionaries: one collapsible group per language of the words, with the monolingual
  dictionary first and then the bilingual ones by language of the definitions, each linked to its release and
  shown with the flag of its language (assets/flags).
Run by the Dictionaries workflow after its builds; by hand (needs gh and mediawiki-langcodes):
python .github/scripts/update_readme.py
"""

import os
import re
import subprocess
from pathlib import Path

from mediawiki_langcodes import code_to_name

REPO = os.environ.get("GITHUB_REPOSITORY", "6801318d8d/inkdict")
README = Path(__file__).resolve().parents[2] / "README.md"
FLAGS = README.parent / "assets" / "flags"
TOC = ("<!-- toc:start (written by .github/scripts/update_readme.py) -->", "<!-- toc:end -->")
LIST = ("<!-- dictionaries:start (written by .github/scripts/update_readme.py) -->", "<!-- dictionaries:end -->")
TAG = re.compile(r"^dict-([a-z]+)-([a-z]+)-(\d{8})$")
HEADING = re.compile(r"^(#{2,3}) +(.+?) *#* *$")


def name(code: str) -> str:
    return code_to_name(code, "en") or code


def flag(code: str) -> str:
    # images, not flag emoji: Chrome and Edge on Windows show those as two letters
    if (FLAGS / f"{code}.svg").is_file():
        return f'<img src="assets/flags/{code}.svg" width="20" alt="">'
    return "🌐"


def toc(text: str) -> str:
    """The table of contents of the README's sections, with GitHub's anchors.

    >>> print(toc("# Title\\n## Use it\\n```sh\\n## not a heading\\n```\\n### The GUI\\n## Use it"))
    <!-- toc:start (written by .github/scripts/update_readme.py) -->
    **Contents**
    <BLANKLINE>
    - [Use it](#use-it)
      - [The GUI](#the-gui)
    - [Use it](#use-it-1)
    <!-- toc:end -->
    """
    lines, seen, fence = [TOC[0], "**Contents**", ""], {}, False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence and (m := HEADING.match(line)):
            level, title = len(m[1]), m[2]
            anchor = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
            seen[anchor] = seen.get(anchor, -1) + 1
            suffix = f"-{seen[anchor]}" if seen[anchor] else ""
            lines.append(f"{'  ' * (level - 2)}- [{title}](#{anchor}{suffix})")
    return "\n".join([*lines, TOC[1]])


def dictionaries(tags: list[str]) -> str:
    """The list of the dictionaries of these release tags.

    >>> print(dictionaries(["dict-zh-pl-20261101", "build-status", "dict-zh-zh-20261020", "dict-zh-pl-20261020"]))
    <!-- dictionaries:start (written by .github/scripts/update_readme.py) -->
    2 dictionaries, grouped by the language of their words:
    <BLANKLINE>
    <details><summary><img src="assets/flags/zh.svg" width="20" alt=""> Chinese (2)</summary>
    <BLANKLINE>
    - <img src="assets/flags/zh.svg" width="20" alt=""> [Monolingual](https://github.com/6801318d8d/inkdict/releases/tag/dict-zh-zh-20261020) (2026-10-20 dump)
    - <img src="assets/flags/pl.svg" width="20" alt=""> [Chinese-Polish](https://github.com/6801318d8d/inkdict/releases/tag/dict-zh-pl-20261101) (2026-11-01 dump)
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
    lines = [LIST[0], f"{len(newest)} dictionaries, grouped by the language of their words:", ""]
    for words in sorted(groups, key=name):
        lines += [f"<details><summary>{flag(words)} {name(words)} ({len(groups[words])})</summary>", ""]
        for bilingual, defs_name, defs, snapshot in sorted(groups[words]):  # monolingual (False) first
            label = f"{name(words)}-{defs_name}" if bilingual else "Monolingual"
            url = f"https://github.com/{REPO}/releases/tag/dict-{words}-{defs}-{snapshot}"
            lines.append(f"- {flag(defs)} [{label}]({url}) ({snapshot[:4]}-{snapshot[4:6]}-{snapshot[6:]} dump)")
        lines += ["", "</details>", ""]
    lines.append(LIST[1])
    return "\n".join(lines)


def replace(text: str, markers: tuple[str, str], block: str) -> str:
    start, end = text.index(markers[0]), text.index(markers[1]) + len(markers[1])
    return text[:start] + block + text[end:]


def main() -> None:
    tags = subprocess.run(
        ["gh", "release", "list", "-R", REPO, "--limit", "10000", "--json", "tagName", "-q", ".[].tagName"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    text = README.read_text(encoding="utf-8")
    new = replace(text, LIST, dictionaries(tags))
    new = replace(new, TOC, toc(new))
    if new == text:
        print("README.md unchanged")
        return
    README.write_text(new, encoding="utf-8", newline="\n")
    print("README.md updated")


if __name__ == "__main__":
    main()
