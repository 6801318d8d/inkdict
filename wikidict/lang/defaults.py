"""Defaults values for locales without specific needs.
See `wikidict.langs.__init__` for details.
"""

from collections import defaultdict
from collections.abc import Callable

from mediawiki_langcodes import code_to_name

module_trans = "Module"
template_trans = "Template"
appendix_trans = "Appendix"
template_adapters: dict[str, Callable[[str], str]] = {}
template_overrides: dict[str, Callable[[tuple[str, ...]], str]] = {}

section_patterns = ("#",)
sublist_patterns = ("#",)
section_level = 2
section_sublevels = (3,)
head_sections = ("",)
etyl_section = ("",)

# Marker(s) used by that Wiktionary to introduce the section of *another* language.
# An empty tuple means that Wiktionary cannot be used as the source of a bilingual dictionary.
# Available placeholders (see `wikidict.lang.head_sections_for()`):
#   - `$code`  the language code (ex: "en");
#   - `$code3` the ISO 639-3 language code (ex: "eng");
#   - `$name`  the language name, written in that Wiktionary's own language (ex: "anglais").
# Use the braced form when the placeholder is glued to a letter: `{{${code}v}}`.
foreign_head_sections: tuple[str, ...] = ()

variant_templates: tuple[str, ...] = ()
reverse_variant_titles: tuple[str, ...] = ()
reverse_variant_templates: tuple[str, ...] = ()
variant_handlers: dict[str, Callable[[str, list[str], defaultdict[str, str], str], str]] = {}

definitions_to_ignore: tuple[str, ...] = ()
templates_ignored: tuple[str, ...] = ()


def foreign_names(code: str, locale: str) -> tuple[str, ...]:
    """All the names the `code` language may be given in the `locale` Wiktionary.
    Several candidates can be returned: unknown ones simply never match any section.

        >>> foreign_names("en", "fr")
        ('anglais',)
        >>> foreign_names("it", "de")
        ('Italienisch',)
        >>> foreign_names("zzz", "fr")
        ()

    """
    return (name,) if (name := code_to_name(code, locale)) else ()


def find_genders(code: str, locale: str) -> list[str]:
    return []


def find_pronunciations(code: str, locale: str) -> list[str]:
    return []


def adjust_wikicode(
    code: str,
    locale: str,
    *,
    templates_status: list[tuple[str, str]] | None = None,
    word: str = "",
) -> str:
    return code
