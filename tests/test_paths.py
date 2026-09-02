from pathlib import Path

import pytest

from literature_graph_mcp.paths import normalize_local_path, resolve_library_root


def test_normalizes_path_inside_library(tmp_path: Path) -> None:
    paper = tmp_path / "topic" / "paper.pdf"
    paper.parent.mkdir()
    paper.write_text("paper", encoding="utf-8")
    assert normalize_local_path(tmp_path, str(paper)) == "topic/paper.pdf"


def test_allows_empty_local_path(tmp_path: Path) -> None:
    assert normalize_local_path(tmp_path, "") == ""


def test_rejects_path_outside_library(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.pdf"
    outside.write_text("paper", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="inside the selected library"):
            normalize_local_path(tmp_path, str(outside))
    finally:
        outside.unlink()


def test_requires_existing_library(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="existing directory"):
        resolve_library_root(str(tmp_path / "missing"))
