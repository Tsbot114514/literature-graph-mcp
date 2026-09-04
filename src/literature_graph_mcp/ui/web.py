from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..paths import absolute_local_path
from ..repository import LiteratureGraphRepository

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _display_label(
    properties: dict[str, Any],
    labels: list[str],
) -> str:
    node_id = properties.get("id")
    if not node_id:
        return properties.get("title") or properties.get("name") or ""

    if "Paper" not in labels:
        return properties.get("name") or properties.get("title") or node_id

    title = properties.get("title") or node_id
    year = properties.get("year")
    return f"{year} · {title}" if year else title


def _finalize(
    properties: dict[str, Any],
    labels: list[str],
    library_root: Path,
) -> dict[str, Any]:
    result = dict(properties)
    if "Paper" in labels:
        result["absolute_local_path"] = absolute_local_path(
            library_root, result.get("local_path")
        )
    result["display_label"] = _display_label(properties, labels)
    return result


def _summary(properties: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    result = {
        key: properties[key]
        for key in ("id", "title", "name", "year", "venue")
        if properties.get(key) is not None
    }
    result["display_label"] = _display_label(properties, labels)
    return result


def _normalize_search_items(nodes: list[dict], papers: list[dict]) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for item in nodes:
        node_id = item.get("properties", {}).get("id")
        if node_id and node_id not in seen:
            seen.add(node_id)
            results.append(item)
    for properties in papers:
        node_id = properties.get("id")
        if node_id and node_id not in seen:
            seen.add(node_id)
            results.append({"labels": ["Entity", "Paper"], "properties": properties})
    return results


def create_app(repository: LiteratureGraphRepository, library_root: Path) -> FastAPI:
    app = FastAPI(title="Literature Graph UI")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/search")
    def search(
        query: str,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, Any]:
        nodes = repository.search_nodes(query, None, limit)
        papers = repository.search_papers(query, limit)
        items = _normalize_search_items(nodes, papers)[:limit]
        return {
            "results": [
                {
                    "labels": item["labels"],
                    "properties": _summary(item["properties"], item["labels"]),
                }
                for item in items
            ]
        }

    @app.get("/api/graph")
    def graph(
        paper_limit: int = Query(default=50, ge=1, le=200),
        relationship_limit: int = Query(default=200, ge=1, le=1000),
    ) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}

        snapshot = repository.get_graph_snapshot(paper_limit, relationship_limit)
        for node in snapshot["nodes"]:
            node_id = node["properties"]["id"]
            nodes[node_id] = {
                "labels": node["labels"],
                "properties": _summary(node["properties"], node["labels"]),
            }
        for rel in snapshot["relationships"]:
            neighbor_id = rel["node_properties"]["id"]
            if neighbor_id not in nodes:
                nodes[neighbor_id] = {
                    "labels": rel["node_labels"],
                    "properties": _summary(
                        rel["node_properties"], rel["node_labels"]
                    ),
                }
            key = f"{rel['type']}:{rel['source_id']}->{rel['target_id']}"
            edges[key] = {
                "type": rel["type"],
                "source": rel["source_id"],
                "target": rel["target_id"],
            }

        return {"nodes": list(nodes.values()), "edges": list(edges.values())}

    @app.get("/api/node")
    def get_node(node_id: str) -> dict[str, Any]:
        node = repository.get_node(node_id)
        if node is None:
            return JSONResponse({"error": f"Node not found: {node_id}"}, status_code=404)
        node["properties"] = _finalize(
            node["properties"], node["labels"], library_root
        )
        return node

    @app.get("/api/neighborhood")
    def get_neighborhood(
        node_id: str,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        try:
            result = repository.get_neighborhood(node_id, limit)
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=404)
        result["node"]["properties"] = _summary(
            result["node"]["properties"], result["node"]["labels"]
        )
        for rel in result["relationships"]:
            rel["node_properties"] = _summary(
                rel["node_properties"], rel["node_labels"]
            )
        return result

    return app


def serve(
    repository: LiteratureGraphRepository,
    library_root: Path,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    app = create_app(repository, library_root)
    uvicorn.run(app, host=host, port=port)
