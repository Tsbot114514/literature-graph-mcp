import argparse
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .paths import absolute_local_path, normalize_local_path, resolve_library_root
from .repository import LiteratureGraphRepository


def create_server(repository: LiteratureGraphRepository, library_root: Path) -> FastMCP:
    server = FastMCP(
        "literature-graph",
        instructions=(
            "Manage an extensible literature knowledge graph with typed Entity nodes. "
            "Do not delete graph data. Notes and selected excerpts are Session-level text."
        ),
    )

    @server.tool()
    def search_nodes(
        query: str,
        node_type: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Find Entity nodes by ID, title, name, or Note text."""
        return repository.search_nodes(query, node_type, limit)

    @server.tool()
    def get_node(node_id: str) -> dict:
        """Get any Entity node by its globally unique ID."""
        node = repository.get_node(node_id)
        if node is None:
            raise ValueError(f"Node not found: {node_id}")
        if "Paper" in node["labels"]:
            node["properties"] = _with_absolute_path(node["properties"], library_root)
        return node

    @server.tool()
    def get_node_neighborhood(node_id: str, limit: int = 50) -> dict:
        """Get any Entity node and its one-hop typed relationships."""
        result = repository.get_neighborhood(node_id, limit)
        if "Paper" in result["node"]["labels"]:
            result["node"]["properties"] = _with_absolute_path(
                result["node"]["properties"], library_root
            )
        return result

    @server.tool()
    def search_papers(query: str, limit: int = 20) -> list[dict]:
        """Find Paper nodes by title, DOI, or arXiv ID."""
        return repository.search_papers(query, limit)

    @server.tool()
    def get_paper(paper_id: str) -> dict:
        """Get one Paper and resolve its current static local path."""
        paper = repository.get_paper(paper_id)
        if paper is None:
            raise ValueError(f"Paper not found: {paper_id}")
        return _with_absolute_path(paper, library_root)

    @server.tool()
    def set_paper_apa7_citation(
        paper_id: str,
        in_text_parenthetical: str,
        in_text_narrative: str,
        reference: str,
        verified_at: str,
        sources: list[str],
    ) -> dict:
        """Store verified APA 7 citation information directly on one Paper."""
        paper = repository.set_paper_apa7_citation(
            paper_id,
            in_text_parenthetical,
            in_text_narrative,
            reference,
            verified_at,
            sources,
        )
        return _with_absolute_path(paper, library_root)

    @server.tool()
    def get_paper_neighborhood(paper_id: str, limit: int = 50) -> dict:
        """Get a Paper and all adjacent Entity nodes, including Authors."""
        result = repository.get_neighborhood(paper_id, limit)
        if "Paper" not in result["node"]["labels"]:
            raise ValueError(f"Paper not found: {paper_id}")
        result["node"]["properties"] = _with_absolute_path(
            result["node"]["properties"], library_root
        )
        return result

    @server.tool()
    def find_path(source_id: str, target_id: str, max_hops: int = 4) -> dict:
        """Find the shortest undirected Entity path within a bounded hop count."""
        result = repository.find_path(source_id, target_id, max_hops)
        return result or {"nodes": [], "relationships": []}

    @server.tool()
    def upsert_node(
        node_type: str,
        node_id: str,
        properties: dict[str, Any],
    ) -> dict:
        """Create or update any typed Entity node without changing protected text."""
        return repository.upsert_node(node_type, node_id, properties)

    @server.tool()
    def upsert_paper(
        paper_id: str,
        title: str,
        doi: str | None = None,
        arxiv_id: str | None = None,
        openalex_id: str | None = None,
        year: int | None = None,
        abstract: str | None = None,
        venue: str | None = None,
        source_url: str | None = None,
        publication_status: str | None = None,
        publication_date: str | None = None,
        publication_date_precision: str | None = None,
        first_public_draft_date: str | None = None,
        first_public_draft_source: str | None = None,
        latest_revision_date: str | None = None,
        latest_revision_version: str | None = None,
        research_period_start: str | None = None,
        research_period_end: str | None = None,
        research_period_status: str | None = None,
        research_period_note: str | None = None,
        timeline_verified_at: str | None = None,
        timeline_sources: list[str] | None = None,
    ) -> dict:
        """Create a Paper or update metadata, including its verified timeline."""
        return repository.upsert_paper(
            paper_id,
            title,
            {
                "doi": doi,
                "arxiv_id": arxiv_id,
                "openalex_id": openalex_id,
                "year": year,
                "abstract": abstract,
                "venue": venue,
                "source_url": source_url,
                "publication_status": publication_status,
                "publication_date": publication_date,
                "publication_date_precision": publication_date_precision,
                "first_public_draft_date": first_public_draft_date,
                "first_public_draft_source": first_public_draft_source,
                "latest_revision_date": latest_revision_date,
                "latest_revision_version": latest_revision_version,
                "research_period_start": research_period_start,
                "research_period_end": research_period_end,
                "research_period_status": research_period_status,
                "research_period_note": research_period_note,
                "timeline_verified_at": timeline_verified_at,
                "timeline_sources": timeline_sources,
            },
        )

    @server.tool()
    def set_paper_local_path(paper_id: str, local_path: str = "") -> dict:
        """Set or clear a Paper's static location inside the selected library."""
        normalized = normalize_local_path(library_root, local_path)
        paper = repository.set_local_path(paper_id, normalized)
        return _with_absolute_path(paper, library_root)

    @server.tool()
    def upsert_node_note(
        node_id: str,
        session_title: str,
        session_id: str,
        note: str,
    ) -> dict:
        """Add or replace this Session's free-text Note section on any Entity."""
        return repository.upsert_node_note(node_id, session_title, session_id, note)

    @server.tool()
    def save_paper_chunk(
        paper_id: str,
        session_title: str,
        session_id: str,
        chunk: str,
    ) -> dict:
        """Save selected original excerpts in this Session's Paper chunk section."""
        return repository.upsert_paper_chunk(paper_id, session_title, session_id, chunk)

    @server.tool()
    def upsert_relationship(
        source_id: str,
        target_id: str,
        relationship_type: str,
        session_title: str,
        session_id: str,
        note: str,
    ) -> dict:
        """Create a typed Entity relationship or update this Session's Note on it."""
        return repository.upsert_relationship(
            source_id,
            target_id,
            relationship_type,
            session_title,
            session_id,
            note,
        )

    return server


def main() -> None:
    args = _parse_args()
    library_root = resolve_library_root(args.library)
    repository = LiteratureGraphRepository(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password,
        database=args.neo4j_database,
    )
    try:
        repository.verify()
        repository.ensure_schema()
        create_server(repository, library_root).run(transport="stdio")
    finally:
        repository.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Paper-Centric Neo4j MCP server")
    parser.add_argument(
        "--library",
        default=os.getenv("LITERATURE_LIBRARY_PATH"),
        required=os.getenv("LITERATURE_LIBRARY_PATH") is None,
        help="Absolute path to the literature library",
    )
    parser.add_argument(
        "--neo4j-uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687")
    )
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument(
        "--neo4j-password",
        default=os.getenv("NEO4J_PASSWORD"),
        required=os.getenv("NEO4J_PASSWORD") is None,
    )
    parser.add_argument("--neo4j-database", default=os.getenv("NEO4J_DATABASE"))
    return parser.parse_args()


def _with_absolute_path(paper: dict[str, Any], library_root: Path) -> dict[str, Any]:
    result = dict(paper)
    result["absolute_local_path"] = absolute_local_path(
        library_root, result.get("local_path")
    )
    return result
