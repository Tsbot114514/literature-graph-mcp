import pytest

from literature_graph_mcp.repository import validate_node_type, validate_relationship_type


def test_normalizes_relationship_type() -> None:
    assert validate_relationship_type("qualifies") == "QUALIFIES"


@pytest.mark.parametrize(
    "value",
    ["", "related to", "TYPE-WITH-DASH", "`MATCH (n)`"],
)
def test_rejects_unsafe_relationship_type(value: str) -> None:
    with pytest.raises(ValueError):
        validate_relationship_type(value)


@pytest.mark.parametrize("value", ["Paper", "Author", "Institution", "ResearchTopic"])
def test_accepts_dynamic_node_types(value: str) -> None:
    assert validate_node_type(value) == value


@pytest.mark.parametrize("value", ["", "Entity", "lowercase", "Invalid Type", "`Paper`"])
def test_rejects_unsafe_node_types(value: str) -> None:
    with pytest.raises(ValueError):
        validate_node_type(value)
