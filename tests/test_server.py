import asyncio
from pathlib import Path

from literature_graph_mcp.server import create_server


def test_registers_minimal_tool_surface() -> None:
    server = create_server(object(), Path.cwd())  # type: ignore[arg-type]
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == {
        "search_nodes",
        "get_node",
        "get_node_neighborhood",
        "search_papers",
        "get_paper",
        "set_paper_apa7_citation",
        "get_paper_neighborhood",
        "find_path",
        "upsert_node",
        "upsert_paper",
        "set_paper_local_path",
        "upsert_node_note",
        "save_paper_chunk",
        "upsert_relationship",
    }


def test_upsert_paper_exposes_timeline_metadata() -> None:
    server = create_server(object(), Path.cwd())  # type: ignore[arg-type]
    tools = asyncio.run(server.list_tools())
    upsert_paper = next(tool for tool in tools if tool.name == "upsert_paper")
    properties = upsert_paper.inputSchema["properties"]

    assert {
        "publication_status",
        "publication_date",
        "publication_date_precision",
        "first_public_draft_date",
        "first_public_draft_source",
        "latest_revision_date",
        "latest_revision_version",
        "research_period_start",
        "research_period_end",
        "research_period_status",
        "research_period_note",
        "timeline_verified_at",
        "timeline_sources",
    } <= properties.keys()


def test_set_paper_apa7_citation_requires_verified_fields() -> None:
    server = create_server(object(), Path.cwd())  # type: ignore[arg-type]
    tools = asyncio.run(server.list_tools())
    citation_tool = next(
        tool for tool in tools if tool.name == "set_paper_apa7_citation"
    )

    assert citation_tool.inputSchema["required"] == [
        "paper_id",
        "in_text_parenthetical",
        "in_text_narrative",
        "reference",
        "verified_at",
        "sources",
    ]
