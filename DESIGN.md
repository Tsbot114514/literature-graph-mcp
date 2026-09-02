# Personal Literature Knowledge Graph Design

## 1. Purpose

Build a personal, Paper-Centric literature knowledge graph for an Agent. The graph stores global relationships, Session-level summaries, and selected source excerpts. It does not duplicate or pre-chunk every paper.

The Agent uses the graph to locate relevant papers and relationships, then opens the original paper when it needs more evidence.

## 2. Confirmed Principles

- Neo4j is the only structured database.
- Each MCP process is bound to one user-selected literature library when it starts.
- `Paper` is the core node type.
- Every domain node also has the `Entity` label and a globally unique `id`.
- The Agent may create new node types without changing MCP code.
- Original PDF files remain outside Neo4j and are opened on demand.
- Nodes and relationships can both contain a free-text `note` property.
- Paper nodes can contain a free-text `chunk` property.
- `chunk` contains only source excerpts that the Agent considers important or that the user explicitly wants to preserve.
- A Note is a Session-level summary, not a message log.
- Every Note section contains only the Session title and Session ID as its source information.
- The graph does not introduce `agent_id` or `message_id`.
- The Agent may create and update nodes and relationships autonomously.
- The Agent may create a new relationship type when existing types cannot express the relationship.
- The Agent may delete graph data only after explicit user authorization.
- Suspected duplicate papers are not merged automatically.
- Paper timelines are first-class metadata because fast-moving fields can make even
  recent evidence historically stale.

## 3. Storage Boundary

Neo4j stores:

- Paper metadata.
- Relationships between papers.
- Node Notes.
- Relationship Notes.
- Selected original excerpts in Paper `chunk` properties.
- Library-relative local paths or remote source URLs used to reopen papers.

Neo4j does not store:

- PDF binary data.
- Automatically generated full-text chunks for every paper.
- A separate vector index in the first version.
- Message-level conversation logs.

### Node admission

The knowledge graph is a curated long-term memory, not a copy of every search result or bibliography entry. Create a literature node only when it is expected to be reused for at least one of these purposes:

- It provides direct evidence for or against a research Claim.
- It introduces an architecture, method, dataset, or relationship that the Agent expects to revisit.
- It anchors a useful path between existing nodes.
- The user explicitly wants it retained in the library.

Being mentioned in a review, returned by a search, or used only as general background is not sufficient. Such references may remain in review documents without becoming graph nodes.

## 4. Literature Library Binding

The user selects one literature library root when starting the MCP server:

```text
literature-graph-mcp --library <absolute-library-path>
```

The server must:

- Resolve and validate the library root during startup.
- Bind the running MCP process to that library.
- Read local paper material only from inside that root.
- Reject paths that escape the selected library.
- Never scan the library automatically.
- Never watch or track file moves automatically in the first version.

Paper nodes store `local_path` relative to the selected library root:

```text
<library root>/2025/example-paper.pdf

local_path = "2025/example-paper.pdf"
```

If no local material is available, `local_path` remains empty. A Paper node may still contain metadata, relationships, Notes, Chunks, and a remote `source_url`.

When a local file or directory is moved, the Agent explicitly updates `local_path` through MCP. The first version treats it as a static location rather than a persistent file binding.

Using a relative path means the whole literature library can be moved without rewriting every Paper node. The user only needs to start the MCP server with the new library root.

## 5. Paper Node

All nodes use the common shape:

```text
(:Entity:<DynamicType> {id: "...", ...})
```

Examples include `Paper`, `Author`, `Institution`, `Topic`, and `Method`. The generic MCP tools accept a validated PascalCase `node_type`. `note`, `chunk`, and `local_path` remain protected properties maintained by their dedicated tools.

Minimum required properties:

```text
id
title
```

Optional properties:

```text
doi
arxiv_id
openalex_id
year
abstract
venue
local_path
source_url
publication_status
publication_date
publication_date_precision
first_public_draft_date
first_public_draft_source
latest_revision_date
latest_revision_version
research_period_start
research_period_end
research_period_status
research_period_note
timeline_verified_at
timeline_sources
citation_style
citation_in_text_parenthetical
citation_in_text_narrative
citation_reference
citation_verified_at
citation_sources
note
chunk
```

Timeline rules:

- `year` is only a coarse bibliographic field and must not substitute for the timeline.
- `first_public_draft_date` records the first verifiable public version, such as arXiv
  v1. It does not claim to identify an author's private first draft.
- `publication_date` records the archival publication date, not the conference event,
  DOI deposit, dataset snapshot, or preprint submission date.
- Partial publication dates use ISO-like `YYYY` or `YYYY-MM` strings and declare
  `publication_date_precision` as `year` or `month`; exact dates use `day`.
- `publication_status` distinguishes `preprint`, `accepted`, and `published` evidence.
- Research dates are recorded only when the paper explicitly reports when experiments,
  data collection, or the study were performed. They are never inferred from submission
  or publication dates.
- `research_period_status` is `reported` or `not_reported`; the latter remains explicit
  rather than silently treating missing dates as known.
- `timeline_verified_at` and `timeline_sources` preserve when and from which primary
  records the timeline was checked.

Example:

```cypher
(:Paper {
  id: "paper:uuid",
  title: "Example paper",
  doi: "10.xxxx/example",
  year: 2025,
  local_path: "2025/example.pdf",
  source_url: "https://example.org/paper",
  note: "...",
  chunk: "..."
})
```

## 6. Paper Identity and Deduplication

Paper matching order:

1. Same DOI means the same Paper.
2. Otherwise, the same arXiv ID means the same Paper.
3. Otherwise, normalized title and year can identify a possible duplicate.
4. Possible duplicates remain separate until the user authorizes a merge.

The database uses an internal `id` even when a DOI or arXiv ID is available.

## 7. Note Format

`note` is a free-text Markdown document. Each Session owns one section on a node or relationship.

```markdown
## <session_title>
session_id: <session_id>

<Session-level summary or annotation>
```

Example:

```markdown
## Literature Knowledge Graph Design
session_id: ses_example

Paper A limits the conditions under which the conclusion of Paper B applies.
The relationship is therefore QUALIFIES rather than CONTRADICTS.
```

Rules:

- A Note section summarizes the conclusion formed by a Session.
- It does not claim to originate from a particular message.
- It does not contain invented Agent or message identifiers.
- When the same Session updates a Note, its existing section is replaced.
- Sections belonging to other Sessions remain unchanged.

## 8. Chunk Format

`chunk` is also a free-text Markdown document on a Paper node. It stores only selected original excerpts.

```markdown
## <session_title>
session_id: <session_id>

### <optional source location>

> <original excerpt>
```

Example:

```markdown
## Literature Knowledge Graph Design
session_id: ses_example

### Results, page 8

> No significant effect was observed below 10 degrees Celsius.
```

Rules:

- The excerpt must come from the original paper or material attached to that Paper.
- The Agent may save an excerpt it considers important.
- The Agent must save an excerpt when the user explicitly requests it.
- Multiple excerpts may appear in the same Session section.
- Saving selected excerpts does not create a full-text chunking pipeline.

## 9. Relationships

Neo4j relationships connect any Entity nodes directly:

```text
(Entity)-[RELATIONSHIP]->(Entity)
```

Common examples:

```text
CITES
RELATED_TO
SUPPORTS
CONTRADICTS
QUALIFIES
EXTENDS
REPLICATES
USES_METHOD_FROM
AUTHORED_BY
AFFILIATED_WITH
```

Every relationship may contain a `note` property:

```cypher
(paperA)-[:QUALIFIES {
  note: """
## Literature Knowledge Graph Design
session_id: ses_example

Paper A shows that the result of Paper B applies only under a narrower condition.
  """
}]->(paperB)
```

## 10. New Relationship Types

Neo4j does not require relationship types to be declared in advance. The Agent may create a new type when necessary.

Relationship names use uppercase snake case:

```regex
^[A-Z][A-Z0-9_]*$
```

The relationship Note explains why the new relationship is appropriate. No separate `RelationType` or `RelationAssertion` node is required.

## 11. Relationship Uniqueness

One relationship is maintained for each tuple:

```text
(source_paper_id, relationship_type, target_paper_id)
```

If the same relationship already exists:

- Do not create a parallel relationship.
- Add or update the current Session section in the existing relationship's `note`.

Different relationship types may coexist between the same Paper nodes.

## 12. Agent Write Rules

The Agent may autonomously:

- Create a Paper node.
- Update Paper metadata.
- Add or update a Paper Note.
- Save an important original excerpt in `chunk`.
- Create a relationship between Paper nodes.
- Create a new relationship type.
- Add or update a relationship Note.

The Agent may not autonomously:

- Delete a node.
- Delete a relationship.
- Delete a Note section.
- Delete a Chunk section.
- Merge possible duplicate Paper nodes.

Deletion or merging is allowed only after explicit user authorization for that operation.

## 13. MCP Tool Surface

Read tools:

```text
search_nodes
get_node
get_node_neighborhood
search_papers
get_paper
set_paper_apa7_citation
get_paper_neighborhood
find_path
```

Write tools:

```text
upsert_node
upsert_paper
set_paper_local_path
upsert_node_note
save_paper_chunk
upsert_relationship
```

`set_paper_apa7_citation` is a dedicated Paper update rather than a separate graph
node. Citation information is derived bibliographic output, so it remains attached
to the Paper it describes. The stored value must already be verified against the
listed metadata sources. Missing graph metadata never means that the work has no
author.

Restricted tools:

```text
delete_paper
delete_relationship
delete_note_section
delete_chunk_section
merge_papers
```

Restricted tools are not exposed in the first version. They may be added later only with explicit user authorization. The regular Agent does not receive unrestricted `write-cypher` access.

## 14. Default Graph Retrieval

When the Agent opens an Entity node, the default graph response contains:

- The node labels and properties.
- The node `note` when present.
- The Paper `chunk` when the node is a Paper.
- Incoming and outgoing one-hop relationships.
- The `note` on each returned relationship.
- The ID, title, and year of each adjacent Paper.

Two-hop or larger expansion is performed only when the Agent explicitly requests it.

## 15. Reading Original Papers

When more evidence is needed:

1. Resolve `local_path` inside the library root and use it when the local material exists.
2. Otherwise use `source_url`.
3. If neither source is available, report that the original paper cannot currently be opened.

The graph guides the Agent to a Paper. The paper-reading tool supplies the original text only when needed.

## 16. First-Version Architecture

```text
Neo4j Community
  - Extensible Entity nodes
  - Typed Entity relationships
  - Node Notes
  - Relationship Notes
  - Selected source excerpts

Literature Graph MCP
  - User-selected literature library root
  - Library-relative local paper paths
  - Bounded graph reads
  - Controlled node and relationship writes
  - Session-section Note updates
  - User-authorized deletion only

Paper Reader
  - Local PDF access
  - Remote source access
  - On-demand reading
```

The first version does not require Zotero, SQLite, Graphiti, Microsoft GraphRAG, a separate vector database, or a full-text ingestion pipeline.
