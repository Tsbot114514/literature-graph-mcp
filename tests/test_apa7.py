import pytest

from literature_graph_mcp.apa7 import (
    UnsupportedCitationError,
    format_csl_in_text,
    format_crossref_citation,
    format_crossref_journal_article,
)


def test_formats_csl_in_text_authors() -> None:
    parenthetical, narrative = format_csl_in_text(
        [
            {"given": "Wujiang", "family": "Xu"},
            {"given": "Zujie", "family": "Liang"},
            {"given": "Kai", "family": "Mei"},
        ],
        2025,
    )

    assert parenthetical == "(Xu et al., 2025)"
    assert narrative == "Xu et al. (2025)"


def test_formats_two_author_journal_article() -> None:
    citation = format_crossref_journal_article(
        {
            "type": "journal-article",
            "author": [
                {"given": "Roger E.", "family": "Beaty"},
                {"given": "Dan R.", "family": "Johnson"},
            ],
            "published-print": {"date-parts": [[2021, 4]]},
            "title": ["Automating creativity assessment with SemDis"],
            "container-title": ["Behavior Research Methods"],
            "volume": "53",
            "issue": "2",
            "page": "757-780",
            "DOI": "10.3758/S13428-020-01453-W",
        }
    )

    assert citation["in_text_parenthetical"] == "(Beaty & Johnson, 2021)"
    assert citation["in_text_narrative"] == "Beaty and Johnson (2021)"
    assert citation["reference"] == (
        "Beaty, R. E., & Johnson, D. R. (2021). Automating creativity assessment "
        "with SemDis. *Behavior Research Methods, 53*(2), 757–780. "
        "https://doi.org/10.3758/s13428-020-01453-w"
    )


def test_appends_crossref_subtitle_to_journal_title() -> None:
    citation = format_crossref_journal_article(
        {
            "type": "journal-article",
            "author": [{"given": "S.", "family": "Ohlsson"}],
            "published-print": {"date-parts": [[1984]]},
            "title": ["Restructuring revisited"],
            "subtitle": [
                "II. An information processing theory of restructuring and insight"
            ],
            "container-title": ["Scandinavian Journal of Psychology"],
            "volume": "25",
            "issue": "2",
            "page": "117-129",
            "DOI": "10.1111/j.1467-9450.1984.tb01005.x",
        }
    )

    assert "Restructuring revisited: II. An information processing theory" in citation[
        "reference"
    ]

def test_formats_article_number_and_many_authors() -> None:
    citation = format_crossref_journal_article(
        {
            "type": "journal-article",
            "author": [
                {"given": "John D.", "family": "Patterson"},
                {"given": "Jimmy", "family": "Pronchick"},
                {"given": "Ruchi", "family": "Panchanadikar"},
            ],
            "published": {"date-parts": [[2025]]},
            "title": ["CAP"],
            "container-title": ["Behavior Research Methods"],
            "volume": "57",
            "issue": "9",
            "article-number": "264",
            "DOI": "10.3758/s13428-025-02761-9",
        }
    )

    assert citation["in_text_parenthetical"] == "(Patterson et al., 2025)"
    assert "*Behavior Research Methods, 57*(9), Article 264." in citation["reference"]


def test_rejects_unsupported_crossref_type() -> None:
    with pytest.raises(UnsupportedCitationError, match="unsupported Crossref type"):
        format_crossref_citation({"type": "book-chapter"})


def test_formats_proceedings_article() -> None:
    citation = format_crossref_citation(
        {
            "type": "proceedings-article",
            "author": [
                {"given": "Wenxuan", "family": "Zhou"},
                {"given": "Sheng", "family": "Zhang"},
                {"given": "Hoifung", "family": "Poon"},
            ],
            "published-print": {"date-parts": [[2023]]},
            "title": ["Context-faithful prompting"],
            "container-title": ["Findings of EMNLP 2023"],
            "page": "14544-14556",
            "DOI": "10.18653/v1/example",
        }
    )

    assert citation["in_text_parenthetical"] == "(Zhou et al., 2023)"
    assert "*Findings of EMNLP 2023*, 14544–14556." in citation["reference"]


def test_formats_preprint_with_graph_archive_name() -> None:
    citation = format_crossref_citation(
        {
            "type": "posted-content",
            "author": [{"given": "Pier Luc", "family": "de Chantal"}],
            "posted": {"date-parts": [[2025, 5, 8]]},
            "title": ["AI feedback and creativity"],
            "DOI": "10.31219/osf.io/example",
        },
        "PsyArXiv",
    )

    assert citation["in_text_parenthetical"] == "(de Chantal, 2025)"
    assert "[Preprint]. PsyArXiv." in citation["reference"]


def test_formats_book_with_group_author_and_subtitle() -> None:
    citation = format_crossref_citation(
        {
            "type": "book",
            "author": [{"name": "OECD"}],
            "published-print": {"date-parts": [[2024]]},
            "title": ["PISA 2022 results (Volume III)"],
            "subtitle": ["Creative minds, creative schools"],
            "publisher": "OECD Publishing",
            "DOI": "10.1787/example",
        }
    )

    assert citation["in_text_parenthetical"] == "(OECD, 2024)"
    assert "*PISA 2022 results (Volume III): Creative minds, creative schools*." in citation[
        "reference"
    ]
