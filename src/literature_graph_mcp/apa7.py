import html
import re
from typing import Any


class UnsupportedCitationError(ValueError):
    pass


def format_csl_in_text(
    authors: list[dict[str, Any]], year: int
) -> tuple[str, str]:
    if not authors:
        raise UnsupportedCitationError("work has no author metadata")
    parenthetical_author, narrative_author = _format_in_text_authors(authors)
    return (
        f"({parenthetical_author}, {year})",
        f"{narrative_author} ({year})",
    )


def format_crossref_citation(
    message: dict[str, Any], fallback_container: str | None = None
) -> dict[str, str]:
    item_type = message.get("type")
    if item_type == "journal-article":
        return format_crossref_journal_article(message)
    if item_type == "proceedings-article":
        return _format_crossref_proceedings_article(message)
    if item_type == "posted-content":
        return _format_crossref_preprint(message, fallback_container)
    if item_type == "book":
        return _format_crossref_book(message)
    raise UnsupportedCitationError(
        f"unsupported Crossref type: {item_type or 'missing'}"
    )


def format_crossref_journal_article(message: dict[str, Any]) -> dict[str, str]:
    if message.get("type") != "journal-article":
        raise UnsupportedCitationError(
            f"unsupported Crossref type: {message.get('type', 'missing')}"
        )

    authors = message.get("author") or []
    if not authors:
        raise UnsupportedCitationError("journal article has no author metadata")
    year = _publication_year(message)
    title = _crossref_title(message)
    journal = _first_text(message.get("container-title"), "container title")
    doi = _required_text(message.get("DOI"), "DOI").lower()

    author_reference = _format_reference_authors(authors)
    parenthetical_author, narrative_author = _format_in_text_authors(authors)
    locator = _format_journal_locator(message, journal)
    reference = (
        f"{author_reference} ({year}). {_sentence(title)}. {locator} "
        f"https://doi.org/{doi}"
    )
    return {
        "in_text_parenthetical": f"({parenthetical_author}, {year})",
        "in_text_narrative": f"{narrative_author} ({year})",
        "reference": reference,
        "year": str(year),
    }


def _format_crossref_proceedings_article(
    message: dict[str, Any],
) -> dict[str, str]:
    authors, year, title, doi = _core_fields(message)
    container = _first_text(message.get("container-title"), "container title")
    pages = _optional_text(message.get("page"))
    locator = f"*{container}*"
    if pages:
        locator += f", {_page_range(pages)}"
    reference = (
        f"{_format_reference_authors(authors)} ({year}). {_sentence(title)}. "
        f"{locator}. https://doi.org/{doi}"
    )
    return _citation_result(authors, year, reference)


def _format_crossref_preprint(
    message: dict[str, Any], fallback_container: str | None
) -> dict[str, str]:
    authors, year, title, doi = _core_fields(message)
    archive = (
        _optional_text(fallback_container)
        or _optional_text(message.get("group-title"))
        or _optional_text(message.get("publisher"))
        or "Preprint archive"
    )
    reference = (
        f"{_format_reference_authors(authors)} ({year}). *{_sentence(title)}* "
        f"[Preprint]. {archive}. https://doi.org/{doi}"
    )
    return _citation_result(authors, year, reference)


def _format_crossref_book(message: dict[str, Any]) -> dict[str, str]:
    authors, year, title, doi = _core_fields(message)
    publisher = _required_text(message.get("publisher"), "publisher")
    reference = (
        f"{_format_reference_authors(authors)} ({year}). *{_sentence(title)}*. "
        f"{publisher}. https://doi.org/{doi}"
    )
    return _citation_result(authors, year, reference)


def _core_fields(
    message: dict[str, Any],
) -> tuple[list[dict[str, Any]], int, str, str]:
    authors = message.get("author") or []
    if not authors:
        raise UnsupportedCitationError("work has no author metadata")
    return (
        authors,
        _publication_year(message),
        _crossref_title(message),
        _required_text(message.get("DOI"), "DOI").lower(),
    )


def _citation_result(
    authors: list[dict[str, Any]], year: int, reference: str
) -> dict[str, str]:
    parenthetical_author, narrative_author = _format_in_text_authors(authors)
    return {
        "in_text_parenthetical": f"({parenthetical_author}, {year})",
        "in_text_narrative": f"{narrative_author} ({year})",
        "reference": reference,
        "year": str(year),
    }


def _publication_year(message: dict[str, Any]) -> int:
    candidates = [
        message.get("published-print"),
        message.get("posted"),
        message.get("published"),
        message.get("issued"),
        message.get("published-online"),
    ]
    for candidate in candidates:
        try:
            return int(candidate["date-parts"][0][0])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    raise UnsupportedCitationError("publication year is missing")


def _format_reference_authors(authors: list[dict[str, Any]]) -> str:
    formatted = [_format_reference_author(author) for author in authors]
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) <= 20:
        return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"
    return ", ".join(formatted[:19]) + f", ... {formatted[-1]}"


def _format_reference_author(author: dict[str, Any]) -> str:
    literal = _optional_text(author.get("name"))
    if literal:
        return literal
    family = _required_text(author.get("family"), "author family name")
    given = _optional_text(author.get("given"))
    return f"{family}, {_initials(given)}" if given else family


def _format_in_text_authors(authors: list[dict[str, Any]]) -> tuple[str, str]:
    names = [_author_label(author) for author in authors]
    if len(names) == 1:
        return names[0], names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}", f"{names[0]} and {names[1]}"
    return f"{names[0]} et al.", f"{names[0]} et al."


def _author_label(author: dict[str, Any]) -> str:
    return _required_text(
        author.get("family") or author.get("name"), "author citation name"
    )


def _initials(given: str) -> str:
    words = re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", given, flags=re.UNICODE)
    initials: list[str] = []
    for word in words:
        pieces = word.split("-")
        initials.append("-".join(f"{piece[0].upper()}." for piece in pieces))
    if not initials:
        raise UnsupportedCitationError("author given name has no usable initials")
    return " ".join(initials)


def _format_journal_locator(message: dict[str, Any], journal: str) -> str:
    volume = _optional_text(message.get("volume"))
    issue = _optional_text(message.get("issue"))
    pages = _optional_text(message.get("page"))
    article_number = _optional_text(message.get("article-number"))

    if volume:
        locator = f"*{journal}, {volume}*"
        if issue:
            locator += f"({issue})"
    else:
        locator = f"*{journal}*"
        if issue:
            locator += f", ({issue})"
    if pages:
        locator += f", {_page_range(pages)}."
    elif article_number:
        locator += f", Article {article_number}."
    else:
        locator += "."
    return locator


def _sentence(value: str) -> str:
    return value.rstrip().rstrip(".")


def _page_range(value: str) -> str:
    return re.sub(r"(?<=\d)-(?=\d)", "–", value)


def _first_text(value: Any, field: str) -> str:
    if not isinstance(value, list) or not value:
        raise UnsupportedCitationError(f"{field} is missing")
    return _required_text(value[0], field)


def _optional_first_text(value: Any) -> str | None:
    if not isinstance(value, list) or not value:
        return None
    return _optional_text(value[0])


def _crossref_title(message: dict[str, Any]) -> str:
    title = _first_text(message.get("title"), "title")
    subtitle = _optional_first_text(message.get("subtitle"))
    if subtitle and _sentence(subtitle).lower() not in title.lower():
        return f"{_sentence(title)}: {_sentence(subtitle)}"
    return title


def _required_text(value: Any, field: str) -> str:
    normalized = _optional_text(value)
    if not normalized:
        raise UnsupportedCitationError(f"{field} is missing")
    return normalized


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = html.unescape(re.sub(r"<[^>]+>", "", value)).strip()
    return normalized or None
