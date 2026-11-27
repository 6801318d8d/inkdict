"""Internationalization stuff."""

from collections import defaultdict
from collections.abc import Callable
from functools import cache
from importlib import import_module
from pathlib import Path
from string import Template
from typing import Any

from langcodes import Language

from . import defaults

_ALL_LOCALES = {
    locale.name: import_module(f"wikidict.lang.{locale.name}")
    for locale in sorted(Path(__file__).parent.glob("*"))
    if locale.is_dir() and bool(list(locale.glob("*.py", case_sensitive=True)))
}


def _populate(attr: str) -> dict[str, Any]:
    """
    Create a dict for all locales pointing to the appropriate attribute.
    Fallback to `defaults`.
    """
    return {
        locale.__name__.split(".")[-1]: getattr(locale, attr) if hasattr(locale, attr) else getattr(defaults, attr)
        for locale in _ALL_LOCALES.values()
    }


# Name of the "Module" special page in the current locale
module_trans: dict[str, str] = _populate("module_trans")

# Name of the "Template" special page in the current locale
template_trans: dict[str, str] = _populate("template_trans")

# Name of the "Appendix" special page in the current locale
appendix_trans: dict[str, str] = _populate("appendix_trans")

# Wiktionary modules/templates to alter in the database directly
template_adapters: dict[str, dict[str, Callable[[str], str]]] = _populate("template_adapters")

# Wiktionary modules/templates to override
template_overrides: dict[str, dict[str, Callable[[tuple[str, ...]], str]]] = _populate("template_overrides")

# Markers for sections that contain interesting text to analyse.
section_patterns: dict[str, tuple[str, ...]] = _populate("section_patterns")
sublist_patterns: dict[str, tuple[str, ...]] = _populate("sublist_patterns")
section_level: dict[str, int] = _populate("section_level")
section_sublevels: dict[str, tuple[int, ...]] = _populate("section_sublevels")
head_sections: dict[str, tuple[str, ...]] = _populate("head_sections")
foreign_head_sections: dict[str, tuple[str, ...]] = _populate("foreign_head_sections")
foreign_names: dict[str, Callable[[str, str], tuple[str, ...]]] = _populate("foreign_names")
etyl_section: dict[str, tuple[str]] = _populate("etyl_section")
sections: dict[str, tuple[str, ...]] = _populate("sections")

# Variants
reverse_variant_titles: dict[str, tuple[str, ...]] = _populate("reverse_variant_titles")

# Template names considered interesting to look variants into
variant_templates: dict[str, tuple[str, ...]] = _populate("variant_templates")
reverse_variant_templates: dict[str, tuple[str, ...]] = _populate("reverse_variant_templates")

# Functions to extract variants from templates
variant_handlers: dict[str, dict[str, Callable[[str, list[str], defaultdict[str, str], str], str]]] = _populate(
    "variant_handlers"
)

# Some definitions are not good to keep
definitions_to_ignore: dict[str, tuple[str, ...]] = _populate("definitions_to_ignore")

# Templates to ignore: the text will be deleted
templates_ignored: dict[str, tuple[str, ...]] = _populate("templates_ignored")

# Function to find gender(s)
find_genders: dict[str, Callable[[str, str], list[str]]] = _populate("find_genders")

# Function to find pronunciation(s)
find_pronunciations: dict[str, Callable[[str, str], list[str]]] = _populate("find_pronunciations")

# URL to fetch a random word (in the current locale preferrably)
random_word_url: dict[str, str] = _populate("random_word_url")

# Function to adapt the word wikicode before rendering.
# Note: This function must return only the wikicode for the current locale,
#       skipping other locales since they will create unnecessary work.
# TODO: typing, but I do not know yet how to set keyword-arguments
adjust_wikicode = _populate("adjust_wikicode")


class UnsupportedLocale(Exception):
    """Raised when a Wiktionary cannot be used to build the requested dictionary."""


@cache
def head_sections_for(lang_src: str, lang_dst: str) -> tuple[str, ...]:
    """Section marker(s) introducing `lang_dst` words in the `lang_src` Wiktionary.

    Monolingual dictionaries use the hand-crafted `head_sections` of the locale:

        >>> head_sections_for("it", "it")
        ('{{-it-}}',)

    Bilingual ones are derived from `foreign_head_sections`:

        >>> head_sections_for("it", "en")
        ('{{-en-}}',)
        >>> head_sections_for("fr", "it")
        ('{{langue|it}}',)
        >>> head_sections_for("en", "it")
        ('italian',)
        >>> head_sections_for("nl", "es")
        ('{{spa}}', '{{es}}')

    Several markers may be returned: unknown ones simply never match any section.
    """
    if lang_src == lang_dst:
        return head_sections[lang_src]

    if not (patterns := foreign_head_sections[lang_src]):
        msg = f"The {lang_src.upper()} Wiktionary cannot be used to build bilingual dictionaries."
        raise UnsupportedLocale(msg)

    placeholders = {
        "code": lang_dst,
        "code3": Language.get(lang_dst).to_alpha3() if len(lang_dst) < 3 else lang_dst,
        "name": "",
    }
    names = [name.lower() for name in foreign_names[lang_src](lang_dst, lang_src)]

    ret: list[str] = []
    for pattern in patterns:
        if "$name" in pattern:
            ret.extend(Template(pattern).substitute(placeholders | {"name": name}) for name in names)
        else:
            ret.append(Template(pattern).substitute(placeholders))

    if not ret:
        msg = f"Cannot guess how the {lang_src.upper()} Wiktionary introduces {lang_dst.upper()} words."
        raise UnsupportedLocale(msg)

    # Remove duplicates, keep the order
    return tuple(dict.fromkeys(ret))


@cache
def sections_for(lang_src: str, lang_dst: str) -> tuple[str, ...]:
    """Same as `sections`, with head sections pointing at `lang_dst` instead of `lang_src`.

    >>> sections_for("it", "it")[:2]
    ('{{-it-}}', '{{etim}}')
    >>> sections_for("it", "en")[:2]
    ('{{-en-}}', '{{etim}}')

    """
    if lang_src == lang_dst:
        return sections[lang_src]

    own_head_sections = set(head_sections[lang_src])
    return (
        *head_sections_for(lang_src, lang_dst),
        *(section for section in sections[lang_src] if section not in own_head_sections),
    )
