import pytest

from literature_graph_mcp.text_sections import (
    format_session_section,
    upsert_session_section,
)


def test_formats_session_section() -> None:
    assert format_session_section("Research", "ses_123", "A useful note.") == (
        "## Research\nsession_id: ses_123\n\nA useful note."
    )


def test_appends_a_different_session() -> None:
    first = format_session_section("First", "ses_1", "First note")
    result = upsert_session_section(first, "Second", "ses_2", "Second note")
    assert result == (
        "## First\nsession_id: ses_1\n\nFirst note\n\n"
        "## Second\nsession_id: ses_2\n\nSecond note"
    )


def test_replaces_the_same_session() -> None:
    document = (
        "## Old title\nsession_id: ses_1\n\nOld note\n\n"
        "## Other\nsession_id: ses_2\n\nKeep me"
    )
    result = upsert_session_section(document, "New title", "ses_1", "New note")
    assert result == (
        "## New title\nsession_id: ses_1\n\nNew note\n\n"
        "## Other\nsession_id: ses_2\n\nKeep me"
    )


def test_preserves_markdown_headings_inside_session_text() -> None:
    document = format_session_section(
        "Research", "ses_1", "Opening\n\n## Analysis\n\nOriginal analysis"
    )
    result = upsert_session_section(document, "Other", "ses_2", "Other note")
    assert "## Analysis\n\nOriginal analysis" in result
    assert result.endswith("## Other\nsession_id: ses_2\n\nOther note")


@pytest.mark.parametrize("field", ["", "two\nlines"])
def test_rejects_invalid_session_metadata(field: str) -> None:
    with pytest.raises(ValueError):
        format_session_section(field, "ses_1", "note")
