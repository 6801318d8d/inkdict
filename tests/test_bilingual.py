"""Bilingual dictionaries: words of one language explained in another Wiktionary (`it:en`: English words, in Italian).

Like the other language tests, it needs the dump of the source Wiktionary in `data/it/` (`python -m wikidict it --download`
then `--parse`).
"""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest

from wikidict import context, lang
from wikidict.render import parse_word


@pytest.fixture(scope="module", autouse=True)
def setup_lua_ctx() -> None:
    with patch.dict("os.environ", {"CWD": str(Path(context.__file__).parent.parent)}):
        assert context.reset("it")


def test_english_word_in_italian(page: Callable[[str, str], str]) -> None:
    code = page("house", "it")

    details = parse_word("house", code, "it:en", force=True)
    assert details
    assert details.pronunciations == ["/haʊs/"]
    assert details.definitions == {
        "Sostantivo": ["<small>(<i>architettura</i>)</small> casa"],
        "Verbo": ["alloggiare"],
    }
    assert not context.get_then_clear_errors()

    # The page has no Italian section: nothing for the monolingual dictionary
    assert parse_word("house", code, "it", force=True) is None


def test_unsupported_wiktionary() -> None:
    with pytest.raises(lang.UnsupportedLocale):
        lang.head_sections_for("jbo", "en")
