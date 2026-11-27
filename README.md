# inkdict

Dictionaries for e-readers (Kobo, Kindle, KOReader, PocketBook, Boox...) built from [Wiktionary](https://www.wiktionary.org):

- **monolingual**: the words of a language explained in the same language (Italian words, in Italian);
- **bilingual**: the words of one language explained in another (English words, in Italian).

inkdict is a fork of [reader.dict's monolingual dictionaries](https://github.com/reader-dict/monolingual), by Mickaël Schoentgen and [its contributors](https://github.com/reader-dict/monolingual#contributors-), under the MIT license. It adds:

- bilingual dictionaries;
- a graphical interface, with launchers for Windows and for GNU/Linux and macOS;
- support for Windows (the code of the upstream project cannot be imported there).

Ready-made monolingual dictionaries, built by the upstream project, can be downloaded from [reader.dict](https://www.reader-dict.com).

## How it works

Each Wiktionary is written in one language but describes the words of many languages, each in its own section of the page. For example the page [house](https://it.wiktionary.org/wiki/house) of the Italian Wiktionary has an English section, with Italian definitions.

- A **monolingual** dictionary keeps, from a Wiktionary, the sections of its own language: from the Italian Wiktionary, the Italian words.
- A **bilingual** dictionary keeps the sections of another language: from the Italian Wiktionary, the English words, explained in Italian.

A dictionary is named by a *locale*: `it` for the monolingual Italian dictionary, `it:en` for the bilingual one (the Wiktionary, then the language of the words).

The work goes in four steps:

1. **download** the latest dump of the Wiktionary (all its pages, as one compressed XML file);
2. **parse** it into a database, shared by every dictionary built from that Wiktionary;
3. **render** the words of the chosen language: their definitions, pronunciations, etymologies and variants;
4. **convert** them into the dictionary formats of the e-readers.

Size and time grow with the Wiktionary. As an example, measured on a laptop with 12 cores: the Italian Wiktionary is a 72 MB download and a 370 MB database; rendering its 540,000 pages for the monolingual dictionary took 2 minutes, and its 26,000 English words (`it:en`) a few seconds. The English and French Wiktionaries are much larger: count several GB of disk space and hours of work.

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs Python 3.13 and the other requirements by itself:
  - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - GNU/Linux and macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [git](https://git-scm.com/downloads), to install one of the requirements.
- For Kindle dictionaries only: [kindling](https://github.com/ciscoriordan/kindling/releases), saved as `~/.local/bin/kindling` (GNU/Linux, macOS) or `%USERPROFILE%\.local\bin\kindling.exe` (Windows):
  - Windows: download `kindling-cli-windows.exe` and rename it `kindling.exe`;
  - GNU/Linux: download `kindling-cli-linux`, rename it `kindling`, and run `chmod a+x ~/.local/bin/kindling`;
  - macOS: the same with `kindling-cli-mac-apple-silicon` or `kindling-cli-mac-intel`.

Then download this project: `git clone https://github.com/6801318d8d/inkdict.git`, or *Code → Download ZIP* on GitHub.

## Graphical interface

- Windows: double-click `start_gui.bat`.
- GNU/Linux and macOS: run `./start_gui.sh` in a terminal.

The first start takes a minute or two, while uv installs Python and the requirements; the next ones are quick.

In the window:

1. **Wiktionary**: the language of the definitions.
2. **Language of the words**: the same language for a monolingual dictionary, another one for a bilingual dictionary. Any language code can be typed (`la`, `grc`, `ja`...), as long as that Wiktionary has words in it.
3. **Working folder**: the dumps and the dictionaries go in its `data/` subfolder, the logs in its `logs/` subfolder.
4. **Steps** and **Formats**: all the steps are needed the first time; afterwards, another dictionary from the same dump needs only *Render* and *Convert*. *Only with etymologies* skips the variant of each dictionary without etymologies.
5. **Start**. The output of each step is shown in the window; **Stop** interrupts it, and **Open the output folder** shows the dictionaries.

## Command line

Install the requirements once, in the project folder, and activate the environment:

```bash
uv venv --python 3.13
uv pip install -r requirements.txt

# GNU/Linux and macOS
. .venv/bin/activate
# Windows
.venv\Scripts\activate
```

Then run `python -m wikidict LOCALE` for all the steps, or one step at a time:

```bash
# Monolingual: Italian words, in Italian
python -m wikidict it --download
python -m wikidict it --parse
python -m wikidict it --render
python -m wikidict it --convert

# Bilingual: English words, in Italian (the dump and the database are those of `it`)
python -m wikidict it:en --render
python -m wikidict it:en --convert
```

Useful options:

- `--convert --format=stardict,dicthtml` makes only some formats (`dictfile`, `dicthtml`, `dictorg`, `jsonvolume`, `mobi`, `stardict`, `stardict-nosyn`, or `all`), and `--with-etym-only` skips the variants without etymologies;
- `--render --workers=4` limits the number of processes;
- `--get-word=WORD` shows how one word is rendered, straight from Wiktionary (after `--download`): `python -m wikidict it:en --get-word=cat`.

The data go to the `data/` folder of the current folder, or of the folder named by the `CWD` environment variable. [DEBUG.md](DEBUG.md) lists the variables that help to debug a dictionary.

## Output files

The dictionaries are in `data/<words>/<wiktionary>/output/`: `data/it/it/output/` for `it`, `data/en/it/output/` for `it:en`. Their names give the language of the words first, then the language of the definitions, as e-readers expect: `it:en` gives `dict-en-it.zip`, offered for books in English. Each comes in two variants, with and without (`-noetym`) etymologies.

| File | Format | Devices and apps |
|------|--------|------------------|
| `dicthtml-en-it.zip` | Kobo | Kobo: copy it, as it is, into the `.kobo/custom-dict/` folder of the e-reader |
| `dict-en-it.zip` | StarDict | KOReader: unzip it into `koreader/data/dict/`; also GoldenDict, Boox... |
| `dict-en-it-nosyn.zip` | StarDict without the `.syn` file | Readers that ignore that file (Boox) |
| `dict-en-it.mobi.zip` | Mobipocket | Kindle: unzip it, and copy the `.mobi` file into `documents/dictionaries/` |
| `dict-en-it.df.bz2` | DictFile | PocketBook, Vivlio (through their converters) |
| `dictorg-en-it.zip` | DICT.org | dictd and its clients |
| `jsonvolume/` | JSON | Other uses |

More instructions for each device are on [reader.dict](https://www.reader-dict.com).

## Supported Wiktionaries

Monolingual dictionaries can be built from 30 Wiktionaries: `bg`, `ca`, `cs`, `da`, `de`, `el`, `en`, `eo`, `es`, `eu`, `fi`, `fr`, `it`, `ja`, `jbo`, `ko`, `la`, `lt`, `mg`, `nl`, `no`, `pl`, `pt`, `ro`, `ru`, `sv`, `th`, `tr`, `uk`, `zh`.

Bilingual dictionaries can be built from all of them except the Lojban one (`jbo`). Each Wiktionary marks the section of a language in its own way: `foreign_head_sections`, in `wikidict/lang/<code>/__init__.py`, describes it with placeholders for the language of the words: `$code` (`en`), `$code3` (`eng`) and `$name` (the name of the language in the Wiktionary's own language: `anglais` in the French one). For example `("{{langue|$code}}",)` for the French Wiktionary, `("$name",)` for the English one.

So far only `it:en` has been built and checked end to end; the other pairs follow the same rules but have not been checked yet. If a pair gives few or no words, please open an issue.

## Development

Run the tests:

```bash
uv pip install -r requirements-tests.txt

# The tests of a language (and the bilingual ones, for `it`) need the dump of its Wiktionary
python -m wikidict it --download
python -m wikidict it --parse
python -m pytest tests/test_it.py tests/test_bilingual.py

# Doctests
python -m pytest --doctest-modules wikidict
```

Run the linters and the type checker before a pull request: `./check.sh`.

The changes from the upstream project are described in the commits of this fork; the upstream updates can be merged with `git pull https://github.com/reader-dict/monolingual.git main`.

## License

MIT: see [LICENSE](LICENSE). The dictionaries contain text from Wiktionary, available under the [Creative Commons Attribution-ShareAlike license](https://creativecommons.org/licenses/by-sa/4.0/).
