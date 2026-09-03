from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..paths import absolute_local_path
from ..repository import LiteratureGraphRepository

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _author_surname(name: str) -> str:
    if not name:
        return ""
    return name.split()[-1]


def _display_label(
    repository: LiteratureGraphRepository,
    properties: dict[str, Any],
    labels: list[str],
    cache: dict[str, str],
) -> str:
    node_id = properties.get("id")
    if not node_id:
        return properties.get("title") or properties.get("name") or ""

    if "Paper" not in labels:
        return properties.get("name") or properties.get("title") or node_id

    if node_id in cache:
        return cache[node_id]

    year = properties.get("year")
    author = ""
    try:
        neighborhood = repository.get_neighborhood(node_id, 50)
    except ValueError:
        neighborhood = {"relationships": []}
    for rel in neighborhood["relationships"]:
        if rel["type"] == "AUTHORED_BY":
            author = rel["node_properties"].get("name") or ""
            break

    surname = _author_surname(author)
    label = " ".join(str(value) for value in (surname, year) if value)
    if not label:
        label = properties.get("title") or node_id
    cache[node_id] = label
    return label


def _finalize(
    repository: LiteratureGraphRepository,
    properties: dict[str, Any],
    labels: list[str],
    library_root: Path,
    cache: dict[str, str],
) -> dict[str, Any]:
    result = dict(properties)
    if "Paper" in labels:
        result["absolute_local_path"] = absolute_local_path(
            library_root, result.get("local_path")
        )
    result["display_label"] = _display_label(
        repository, properties, labels, cache
    )
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
            results.append({"labels": ["Paper"], "properties": properties})
    return results


def create_app(repository: LiteratureGraphRepository, library_root: Path) -> FastAPI:
    app = FastAPI(title="Literature Graph UI")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/search")
    def search(query: str, limit: int = 20) -> dict[str, Any]:
        cache: dict[str, str] = {}
        nodes = repository.search_nodes(query, None, limit)
        papers = repository.search_papers(query, limit)
        items = _normalize_search_items(nodes, papers)
        return {
            "results": [
                {
                    "labels": item["labels"],
                    "properties": _finalize(
                        repository, item["properties"], item["labels"], library_root, cache
                    ),
                }
                for item in items
            ]
        }

    @app.get("/api/graph")
    def graph() -> dict[str, Any]:
        cache: dict[str, str] = {}
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}

        for paper in repository.list_papers():
            paper_id = paper["id"]
            nodes[paper_id] = {
                "labels": ["Entity", "Paper"],
                "properties": _finalize(
                    repository, paper, ["Entity", "Paper"], library_root, cache
                ),
            }
            try:
                neighborhood = repository.get_neighborhood(paper_id, 50)
            except ValueError:
                continue
            for rel in neighborhood["relationships"]:
                neighbor_id = rel["node_properties"]["id"]
                if neighbor_id not in nodes:
                    nodes[neighbor_id] = {
                        "labels": rel["node_labels"],
                        "properties": _finalize(
                            repository,
                            rel["node_properties"],
                            rel["node_labels"],
                            library_root,
                            cache,
                        ),
                    }
                source = paper_id if rel["direction"] == "outgoing" else neighbor_id
                target = neighbor_id if rel["direction"] == "outgoing" else paper_id
                key = f"{rel['type']}:{source}->{target}"
                edges[key] = {"type": rel["type"], "source": source, "target": target}

        return {"nodes": list(nodes.values()), "edges": list(edges.values())}

    @app.get("/api/papers")
    def papers() -> list[dict[str, Any]]:
        cache: dict[str, str] = {}
        return [
            _finalize(repository, properties, ["Entity", "Paper"], library_root, cache)
            for properties in repository.list_papers()
        ]

    @app.get("/api/node/{node_id}")
    def get_node(node_id: str) -> dict[str, Any]:
        node = repository.get_node(node_id)
        if node is None:
            return JSONResponse({"error": f"Node not found: {node_id}"}, status_code=404)
        cache: dict[str, str] = {}
        node["properties"] = _finalize(
            repository, node["properties"], node["labels"], library_root, cache
        )
        return node

    @app.get("/api/node/{node_id}/neighborhood")
    def get_neighborhood(node_id: str, limit: int = 50) -> dict[str, Any]:
        try:
            result = repository.get_neighborhood(node_id, limit)
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=404)
        cache: dict[str, str] = {}
        result["node"]["properties"] = _finalize(
            repository,
            result["node"]["properties"],
            result["node"]["labels"],
            library_root,
            cache,
        )
        for rel in result["relationships"]:
            rel["node_properties"] = _finalize(
                repository,
                rel["node_properties"],
                rel["node_labels"],
                library_root,
                cache,
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
