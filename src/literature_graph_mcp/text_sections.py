import re


_SECTION_START = re.compile(r"(?m)^## [^\r\n]+\r?\nsession_id: [^\r\n]+\r?$")


def format_session_section(session_title: str, session_id: str, text: str) -> str:
    title = _single_line(session_title, "session_title")
    identifier = _single_line(session_id, "session_id")
    body = text.strip()
    if not body:
        raise ValueError("text must not be empty")
    return f"## {title}\nsession_id: {identifier}\n\n{body}"


def upsert_session_section(
    document: str | None,
    session_title: str,
    session_id: str,
    text: str,
) -> str:
    replacement = format_session_section(session_title, session_id, text)
    existing = (document or "").strip()
    if not existing:
        return replacement

    sections = _split_sections(existing)
    target = f"session_id: {_single_line(session_id, 'session_id')}"
    updated = False
    for index, section in enumerate(sections):
        if target in section.splitlines():
            sections[index] = replacement
            updated = True
            break

    if not updated:
        sections.append(replacement)
    return "\n\n".join(section.strip() for section in sections if section.strip())


def _split_sections(document: str) -> list[str]:
    starts = [match.start() for match in _SECTION_START.finditer(document)]
    if not starts:
        return [document]

    sections: list[str] = []
    if starts[0] > 0 and document[: starts[0]].strip():
        sections.append(document[: starts[0]])
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(document)
        sections.append(document[start:end])
    return sections


def _single_line(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized or "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{name} must be a non-empty single line")
    return normalized
