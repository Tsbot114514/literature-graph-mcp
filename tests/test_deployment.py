from pathlib import Path


COMPOSE_FILE = Path(__file__).parents[1] / "docker-compose.yml"


def test_compose_uses_published_neo4j_community_tag() -> None:
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert "image: neo4j:5.26-community" in compose
    assert "image: neo4j:5.28-community" not in compose


def test_compose_does_not_expose_password_as_neo4j_setting() -> None:
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert 'LG_PASSWORD: "${NEO4J_PASSWORD}"' in compose
    assert '$${LG_PASSWORD}' in compose
    assert '\n      NEO4J_PASSWORD:' not in compose
