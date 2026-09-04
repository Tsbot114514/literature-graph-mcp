import re
from collections.abc import Mapping
from typing import Any

from neo4j import Driver, GraphDatabase, ManagedTransaction

from .text_sections import upsert_session_section


_RELATIONSHIP_TYPE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_NODE_TYPE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
_RESERVED_NODE_PROPERTIES = {"id", "note", "chunk", "local_path"}


def validate_relationship_type(value: str) -> str:
    normalized = value.strip().upper()
    if not _RELATIONSHIP_TYPE.fullmatch(normalized):
        raise ValueError("relationship_type must use uppercase snake case")
    return normalized


def validate_node_type(value: str) -> str:
    normalized = value.strip()
    if normalized == "Entity" or not _NODE_TYPE.fullmatch(normalized):
        raise ValueError("node_type must use a PascalCase label other than Entity")
    return normalized


class LiteratureGraphRepository:
    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str | None = None,
    ) -> None:
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database

    def close(self) -> None:
        self._driver.close()

    def verify(self) -> None:
        self._driver.verify_connectivity()

    def ensure_schema(self) -> None:
        migrations = [
            "MATCH (p:Paper) SET p:Entity",
        ]
        constraints = [
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
            "FOR (n:Entity) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT paper_id_unique IF NOT EXISTS "
            "FOR (p:Paper) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT paper_doi_unique IF NOT EXISTS "
            "FOR (p:Paper) REQUIRE p.doi IS UNIQUE",
            "CREATE CONSTRAINT paper_arxiv_id_unique IF NOT EXISTS "
            "FOR (p:Paper) REQUIRE p.arxiv_id IS UNIQUE",
        ]
        with self._driver.session(database=self._database) as session:
            for query in migrations + constraints:
                session.run(query).consume()

    def upsert_node(
        self,
        node_type: str,
        node_id: str,
        properties: Mapping[str, Any],
    ) -> dict:
        label = validate_node_type(node_type)
        identifier = _required(node_id, "node_id")
        values = _clean_node_properties(properties)
        with self._driver.session(database=self._database) as session:
            return session.execute_write(
                self._upsert_node_tx,
                label,
                identifier,
                values,
            )

    @staticmethod
    def _upsert_node_tx(
        tx: ManagedTransaction,
        node_type: str,
        node_id: str,
        properties: dict[str, Any],
    ) -> dict:
        existing = tx.run(
            "MATCH (n:Entity {id: $node_id}) RETURN labels(n) AS labels",
            node_id=node_id,
        ).single()
        if existing is not None:
            domain_labels = set(existing["labels"]) - {"Entity"}
            if domain_labels and node_type not in domain_labels:
                raise ValueError(
                    f"node_id already belongs to node type: {sorted(domain_labels)[0]}"
                )
        record = tx.run(
            f"MERGE (n:Entity {{id: $node_id}}) SET n:`{node_type}`, n += $properties "
            "RETURN labels(n) AS labels, properties(n) AS properties",
            node_id=node_id,
            properties=properties,
        ).single(strict=True)
        return {"labels": record["labels"], "properties": record["properties"]}

    def upsert_paper(self, paper_id: str, title: str, properties: Mapping[str, Any]) -> dict:
        identifier = _required(paper_id, "paper_id")
        normalized_title = _required(title, "title")
        values = {key: value for key, value in properties.items() if value is not None}
        values["doi"] = _optional_identifier(values.get("doi"))
        values["arxiv_id"] = _optional_identifier(values.get("arxiv_id"))
        values = {key: value for key, value in values.items() if value is not None}
        values["title"] = normalized_title
        with self._driver.session(database=self._database) as session:
            return session.execute_write(
                self._upsert_paper_tx,
                paper_id=identifier,
                properties=values,
            )

    @staticmethod
    def _upsert_paper_tx(
        tx: ManagedTransaction,
        paper_id: str,
        properties: dict[str, Any],
    ) -> dict:
        matches = list(
            tx.run(
                "MATCH (p:Paper) "
                "WHERE p.id = $paper_id "
                "OR ($doi IS NOT NULL AND p.doi = $doi) "
                "OR ($arxiv_id IS NOT NULL AND p.arxiv_id = $arxiv_id) "
                "RETURN p.id AS id",
                paper_id=paper_id,
                doi=properties.get("doi"),
                arxiv_id=properties.get("arxiv_id"),
            )
        )
        matched_ids = {record["id"] for record in matches}
        if len(matched_ids) > 1:
            raise ValueError("paper identifiers match different existing Paper nodes")
        canonical_id = next(iter(matched_ids), paper_id)
        record = tx.run(
            "MERGE (p:Entity:Paper {id: $paper_id}) "
            "SET p += $properties "
            "RETURN properties(p) AS paper",
            paper_id=canonical_id,
            properties=properties,
        ).single(strict=True)
        return record["paper"]

    def set_local_path(self, paper_id: str, local_path: str) -> dict:
        with self._driver.session(database=self._database) as session:
            record = session.run(
                "MATCH (p:Paper {id: $paper_id}) "
                "SET p.local_path = $local_path "
                "RETURN properties(p) AS paper",
                paper_id=_required(paper_id, "paper_id"),
                local_path=local_path,
            ).single()
        if record is None:
            raise ValueError(f"Paper not found: {paper_id}")
        return record["paper"]

    def get_paper(self, paper_id: str) -> dict | None:
        with self._driver.session(database=self._database) as session:
            record = session.run(
                "MATCH (p:Paper {id: $paper_id}) RETURN properties(p) AS paper",
                paper_id=_required(paper_id, "paper_id"),
            ).single()
        return None if record is None else record["paper"]

    def set_paper_apa7_citation(
        self,
        paper_id: str,
        in_text_parenthetical: str,
        in_text_narrative: str,
        reference: str,
        verified_at: str,
        sources: list[str],
    ) -> dict:
        citation_sources = [
            _required(source, "citation source") for source in sources
        ]
        if not citation_sources:
            raise ValueError("citation sources must not be empty")
        properties = {
            "citation_style": "APA 7",
            "citation_in_text_parenthetical": _required(
                in_text_parenthetical, "in_text_parenthetical"
            ),
            "citation_in_text_narrative": _required(
                in_text_narrative, "in_text_narrative"
            ),
            "citation_reference": _required(reference, "reference"),
            "citation_verified_at": _required(verified_at, "verified_at"),
            "citation_sources": citation_sources,
        }
        with self._driver.session(database=self._database) as session:
            record = session.run(
                "MATCH (p:Paper {id: $paper_id}) "
                "SET p += $properties "
                "RETURN properties(p) AS paper",
                paper_id=_required(paper_id, "paper_id"),
                properties=properties,
            ).single()
        if record is None:
            raise ValueError(f"Paper not found: {paper_id}")
        return record["paper"]

    def get_node(self, node_id: str) -> dict | None:
        with self._driver.session(database=self._database) as session:
            record = session.run(
                "MATCH (n:Entity {id: $node_id}) "
                "RETURN labels(n) AS labels, properties(n) AS properties",
                node_id=_required(node_id, "node_id"),
            ).single()
        if record is None:
            return None
        return {"labels": record["labels"], "properties": record["properties"]}

    def search_nodes(
        self,
        query: str,
        node_type: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        normalized = _required(query, "query").lower()
        label = validate_node_type(node_type) if node_type else None
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (n:Entity) "
                "WHERE ($node_type IS NULL OR $node_type IN labels(n)) "
                "AND (toLower(n.id) CONTAINS $search_query "
                "OR toLower(coalesce(n.title, '')) CONTAINS $search_query "
                "OR toLower(coalesce(n.name, '')) CONTAINS $search_query "
                "OR toLower(coalesce(n.note, '')) CONTAINS $search_query) "
                "RETURN labels(n) AS labels, properties(n) AS properties "
                "ORDER BY coalesce(n.title, n.name, n.id) LIMIT $limit",
                node_type=label,
                search_query=normalized,
                limit=_bounded_limit(limit),
            )
            return [
                {"labels": record["labels"], "properties": record["properties"]}
                for record in result
            ]

    def search_papers(self, query: str, limit: int = 20) -> list[dict]:
        normalized = _required(query, "query").lower()
        bounded_limit = _bounded_limit(limit)
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (p:Paper) "
                "WHERE toLower(p.title) CONTAINS $search_query "
                "OR toLower(coalesce(p.doi, '')) CONTAINS $search_query "
                "OR toLower(coalesce(p.arxiv_id, '')) CONTAINS $search_query "
                "RETURN properties(p) AS paper "
                "ORDER BY p.year DESC, p.title "
                "LIMIT $limit",
                search_query=normalized,
                limit=bounded_limit,
            )
            return [record["paper"] for record in result]

    def list_papers(self) -> list[dict]:
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (p:Paper) RETURN properties(p) AS paper "
                "ORDER BY p.title"
            )
            return [record["paper"] for record in result]

    def get_graph_snapshot(
        self,
        paper_limit: int = 50,
        relationship_limit: int = 200,
    ) -> dict:
        bounded_papers = _bounded_limit(paper_limit, maximum=200)
        bounded_relationships = _bounded_limit(relationship_limit, maximum=1000)
        with self._driver.session(database=self._database) as session:
            node_result = session.run(
                "MATCH (p:Paper) "
                "RETURN labels(p) AS labels, "
                "{id: p.id, title: p.title, year: p.year, venue: p.venue} AS properties "
                "ORDER BY coalesce(p.publication_date, toString(p.year), '') DESC, "
                "p.title LIMIT $limit",
                limit=bounded_papers,
            )
            nodes = [record.data() for record in node_result]
            paper_ids = [node["properties"]["id"] for node in nodes]
            if not paper_ids:
                return {"nodes": [], "relationships": []}

            relationship_result = session.run(
                "MATCH (p:Paper)-[r]-(other:Entity) "
                "WHERE p.id IN $paper_ids "
                "WITH p, r, other "
                "ORDER BY p.id, type(r), coalesce(other.title, other.name, other.id) "
                "LIMIT $limit "
                "RETURN type(r) AS type, "
                "CASE WHEN startNode(r) = p THEN p.id ELSE other.id END AS source_id, "
                "CASE WHEN startNode(r) = p THEN other.id ELSE p.id END AS target_id, "
                "labels(other) AS node_labels, "
                "{id: other.id, title: other.title, name: other.name, "
                "year: other.year, venue: other.venue} AS node_properties",
                paper_ids=paper_ids,
                limit=bounded_relationships,
            )
            relationships = [record.data() for record in relationship_result]
        return {"nodes": nodes, "relationships": relationships}

    def get_neighborhood(self, node_id: str, limit: int = 50) -> dict:
        identifier = _required(node_id, "node_id")
        with self._driver.session(database=self._database) as session:
            node_record = session.run(
                "MATCH (n:Entity {id: $node_id}) "
                "RETURN labels(n) AS labels, properties(n) AS properties",
                node_id=identifier,
            ).single()
            if node_record is None:
                raise ValueError(f"Node not found: {node_id}")
            result = session.run(
                "MATCH (n:Entity {id: $node_id})-[r]-(other:Entity) "
                "RETURN type(r) AS type, properties(r) AS properties, "
                "CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END AS direction, "
                "labels(other) AS node_labels, properties(other) AS node_properties "
                "ORDER BY type, coalesce(other.title, other.name, other.id) LIMIT $limit",
                node_id=identifier,
                limit=_bounded_limit(limit, maximum=200),
            )
            relationships = [record.data() for record in result]
        return {
            "node": {
                "labels": node_record["labels"],
                "properties": node_record["properties"],
            },
            "relationships": relationships,
        }

    def find_path(self, source_id: str, target_id: str, max_hops: int = 4) -> dict | None:
        if not 1 <= max_hops <= 6:
            raise ValueError("max_hops must be between 1 and 6")
        query = (
            "MATCH (source:Entity {id: $source_id}), (target:Entity {id: $target_id}) "
            f"MATCH path = shortestPath((source)-[*..{max_hops}]-(target)) "
            "RETURN [n IN nodes(path) | {labels: labels(n), properties: properties(n)}] AS nodes, "
            "[r IN relationships(path) | {"
            "type: type(r), properties: properties(r), "
            "source_id: startNode(r).id, target_id: endNode(r).id"
            "}] AS relationships"
        )
        with self._driver.session(database=self._database) as session:
            record = session.run(
                query,
                source_id=_required(source_id, "source_id"),
                target_id=_required(target_id, "target_id"),
            ).single()
        return None if record is None else record.data()

    def upsert_node_note(
        self,
        node_id: str,
        session_title: str,
        session_id: str,
        text: str,
    ) -> dict:
        with self._driver.session(database=self._database) as session:
            return session.execute_write(
                self._upsert_node_note_tx,
                _required(node_id, "node_id"),
                session_title,
                session_id,
                text,
            )

    @staticmethod
    def _upsert_node_note_tx(
        tx: ManagedTransaction,
        node_id: str,
        session_title: str,
        session_id: str,
        text: str,
    ) -> dict:
        record = tx.run(
            "MATCH (n:Entity {id: $node_id}) RETURN n.note AS current",
            node_id=node_id,
        ).single()
        if record is None:
            raise ValueError(f"Node not found: {node_id}")
        updated = upsert_session_section(record["current"], session_title, session_id, text)
        result = tx.run(
            "MATCH (n:Entity {id: $node_id}) SET n.note = $updated "
            "RETURN labels(n) AS labels, properties(n) AS properties",
            node_id=node_id,
            updated=updated,
        ).single(strict=True)
        return {"labels": result["labels"], "properties": result["properties"]}

    def upsert_paper_chunk(
        self,
        paper_id: str,
        session_title: str,
        session_id: str,
        text: str,
    ) -> dict:
        with self._driver.session(database=self._database) as session:
            return session.execute_write(
                self._upsert_paper_text_tx,
                _required(paper_id, "paper_id"),
                "chunk",
                session_title,
                session_id,
                text,
            )

    @staticmethod
    def _upsert_paper_text_tx(
        tx: ManagedTransaction,
        paper_id: str,
        property_name: str,
        session_title: str,
        session_id: str,
        text: str,
    ) -> dict:
        record = tx.run(
            f"MATCH (p:Paper {{id: $paper_id}}) RETURN p.{property_name} AS current",
            paper_id=paper_id,
        ).single()
        if record is None:
            raise ValueError(f"Paper not found: {paper_id}")
        updated = upsert_session_section(record["current"], session_title, session_id, text)
        result = tx.run(
            f"MATCH (p:Paper {{id: $paper_id}}) "
            f"SET p.{property_name} = $updated RETURN properties(p) AS paper",
            paper_id=paper_id,
            updated=updated,
        ).single(strict=True)
        return result["paper"]

    def upsert_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        session_title: str,
        session_id: str,
        note: str,
    ) -> dict:
        relation = validate_relationship_type(relationship_type)
        with self._driver.session(database=self._database) as session:
            return session.execute_write(
                self._upsert_relationship_tx,
                _required(source_id, "source_id"),
                _required(target_id, "target_id"),
                relation,
                session_title,
                session_id,
                note,
            )

    @staticmethod
    def _upsert_relationship_tx(
        tx: ManagedTransaction,
        source_id: str,
        target_id: str,
        relationship_type: str,
        session_title: str,
        session_id: str,
        note: str,
    ) -> dict:
        query = (
            "MATCH (source:Entity {id: $source_id}) "
            "MATCH (target:Entity {id: $target_id}) "
            f"MERGE (source)-[r:`{relationship_type}`]->(target) "
            "RETURN r.note AS current"
        )
        record = tx.run(query, source_id=source_id, target_id=target_id).single()
        if record is None:
            raise ValueError("source or target node not found")
        updated = upsert_session_section(record["current"], session_title, session_id, note)
        result = tx.run(
            "MATCH (source:Entity {id: $source_id}) "
            "MATCH (target:Entity {id: $target_id}) "
            f"MATCH (source)-[r:`{relationship_type}`]->(target) "
            "SET r.note = $note "
            "RETURN {type: type(r), properties: properties(r), "
            "source_id: source.id, target_id: target.id} AS relationship",
            source_id=source_id,
            target_id=target_id,
            note=updated,
        ).single(strict=True)
        return result["relationship"]


def _required(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _bounded_limit(value: int, maximum: int = 100) -> int:
    if value < 1:
        raise ValueError("limit must be positive")
    return min(value, maximum)


def _optional_identifier(value: Any) -> str | None:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    return normalized or None


def _clean_node_properties(properties: Mapping[str, Any]) -> dict[str, Any]:
    reserved = _RESERVED_NODE_PROPERTIES.intersection(properties)
    if reserved:
        raise ValueError(
            f"reserved properties require dedicated tools: {', '.join(sorted(reserved))}"
        )
    return {key: value for key, value in properties.items() if value is not None}
