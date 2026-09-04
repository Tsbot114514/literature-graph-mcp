from argparse import Namespace
from pathlib import Path

from fastapi.testclient import TestClient

from literature_graph_mcp import server
from literature_graph_mcp.ui.web import create_app


DOI_ID = "doi:10.1000/example"


class FakeRepository:
    def __init__(self) -> None:
        self.snapshot_calls: list[tuple[int, int]] = []

    def search_nodes(self, query: str, node_type: str | None, limit: int) -> list[dict]:
        return [
            {
                "labels": ["Entity", "Paper"],
                "properties": {
                    "id": DOI_ID,
                    "title": "Example Paper",
                    "year": 2026,
                    "note": "private note",
                },
            }
        ]

    def search_papers(self, query: str, limit: int) -> list[dict]:
        return []

    def get_node(self, node_id: str) -> dict | None:
        if node_id != DOI_ID:
            return None
        return {
            "labels": ["Entity", "Paper"],
            "properties": {
                "id": DOI_ID,
                "title": "Example Paper",
                "year": 2026,
                "note": "private note",
                "chunk": "source excerpt",
                "local_path": "example.pdf",
            },
        }

    def get_neighborhood(self, node_id: str, limit: int) -> dict:
        if node_id != DOI_ID:
            raise ValueError(f"Node not found: {node_id}")
        return {
            "node": {
                "labels": ["Entity", "Paper"],
                "properties": {
                    "id": DOI_ID,
                    "title": "Example Paper",
                    "note": "private note",
                },
            },
            "relationships": [
                {
                    "type": "ABOUT",
                    "properties": {},
                    "direction": "outgoing",
                    "node_labels": ["Entity", "Topic"],
                    "node_properties": {
                        "id": "topic:test",
                        "name": "Test Topic",
                        "note": "private topic note",
                    },
                }
            ],
        }

    def get_graph_snapshot(self, paper_limit: int, relationship_limit: int) -> dict:
        self.snapshot_calls.append((paper_limit, relationship_limit))
        return {
            "nodes": [
                {
                    "labels": ["Entity", "Paper"],
                    "properties": {
                        "id": DOI_ID,
                        "title": "Example Paper",
                        "year": 2026,
                        "note": "private note",
                    },
                }
            ],
            "relationships": [
                {
                    "type": "ABOUT",
                    "source_id": DOI_ID,
                    "target_id": "topic:test",
                    "node_labels": ["Entity", "Topic"],
                    "node_properties": {
                        "id": "topic:test",
                        "name": "Test Topic",
                        "note": "private topic note",
                    },
                }
            ],
        }


def _client(tmp_path: Path) -> tuple[TestClient, FakeRepository]:
    (tmp_path / "example.pdf").write_text("paper", encoding="utf-8")
    repository = FakeRepository()
    return TestClient(create_app(repository, tmp_path)), repository  # type: ignore[arg-type]


def test_graph_is_bounded_and_uses_lightweight_properties(tmp_path: Path) -> None:
    client, repository = _client(tmp_path)

    response = client.get("/api/graph")

    assert response.status_code == 200
    assert repository.snapshot_calls == [(50, 200)]
    assert len(response.json()["nodes"]) == 2
    assert all("note" not in node["properties"] for node in response.json()["nodes"])


def test_graph_rejects_limits_above_the_contract(tmp_path: Path) -> None:
    client, repository = _client(tmp_path)

    response = client.get("/api/graph?paper_limit=201")

    assert response.status_code == 422
    assert repository.snapshot_calls == []


def test_doi_node_id_with_slash_opens_detail(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    response = client.get("/api/node", params={"node_id": DOI_ID})

    assert response.status_code == 200
    assert response.json()["properties"]["id"] == DOI_ID
    assert response.json()["properties"]["note"] == "private note"
    assert response.json()["properties"]["absolute_local_path"].endswith(
        "example.pdf"
    )


def test_neighborhood_supports_doi_and_returns_summaries(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    response = client.get("/api/neighborhood", params={"node_id": DOI_ID})

    assert response.status_code == 200
    result = response.json()
    assert result["node"]["properties"]["id"] == DOI_ID
    assert "note" not in result["node"]["properties"]
    assert "note" not in result["relationships"][0]["node_properties"]


def test_search_returns_lightweight_results(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    response = client.get("/api/search", params={"query": "example"})

    assert response.status_code == 200
    properties = response.json()["results"][0]["properties"]
    assert properties["id"] == DOI_ID
    assert "note" not in properties


def test_static_index_is_available(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "Literature Graph UI" in response.text
    assert 'selector: "node.labeled, node:selected, node.hovered"' in response.text
    assert 'selector: "edge:selected"' in response.text


def test_ui_mode_does_not_run_schema_writes(monkeypatch, tmp_path: Path) -> None:
    class FakeLifecycleRepository:
        def __init__(self) -> None:
            self.verified = False
            self.schema_ensured = False
            self.closed = False

        def verify(self) -> None:
            self.verified = True

        def ensure_schema(self) -> None:
            self.schema_ensured = True

        def close(self) -> None:
            self.closed = True

    repository = FakeLifecycleRepository()
    args = Namespace(
        library=str(tmp_path),
        neo4j_uri="bolt://unused",
        neo4j_user="neo4j",
        neo4j_password="unused",
        neo4j_database=None,
        ui=True,
        host="127.0.0.1",
        port=8000,
    )
    served: list[tuple[str, int]] = []

    monkeypatch.setattr(server, "_parse_args", lambda: args)
    monkeypatch.setattr(server, "LiteratureGraphRepository", lambda **kwargs: repository)
    monkeypatch.setattr(
        "literature_graph_mcp.ui.web.serve",
        lambda repo, library, host, port: served.append((host, port)),
    )

    server.main()

    assert repository.verified
    assert not repository.schema_ensured
    assert repository.closed
    assert served == [("127.0.0.1", 8000)]
