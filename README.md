# Literature Graph MCP

A Paper-centric Model Context Protocol server that lets agents classify literature, save discussion outcomes as structured research memory, and retrieve evidence while writing.

## What It Does

- Organizes Papers under one or more Topics.
- Stores Claims, Concepts, Authors, Institutions, and other typed entities.
- Records evidence roles such as `SUPPORTS`, `QUALIFIES`, and `CONTRADICTS`.
- Saves Session-level reading Notes without overwriting other Sessions.
- Saves selected source excerpts in Paper Chunks.
- Resolves PDFs and other local material inside a bound literature library.
- Stores verified publication timelines and APA 7 citation output.
- Gives agents bounded search, neighborhood, and path operations.

Neo4j is the only structured database. Original files stay in the filesystem and are opened on demand.

## One-Command Setup on Windows

Requirements:

- Docker Desktop
- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- OpenCode, if you want automatic OpenCode MCP registration

```powershell
git clone https://github.com/Tsbot114514/literature-graph-mcp.git
cd literature-graph-mcp
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer:

1. Creates a literature library at `~/literature-library/papers`.
2. Generates a local Neo4j password.
3. Starts Neo4j with Docker Compose.
4. Installs locked Python dependencies with `uv`.
5. Saves Neo4j settings as Windows user environment variables.
6. Backs up and updates `~/.config/opencode/opencode.jsonc` when it contains parseable JSON.
7. Writes `opencode.mcp.generated.json` as a fallback configuration snippet.

Use a custom library location:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -LibraryPath "D:\Papers"
```

Keep an existing OpenCode configuration unchanged:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -SkipOpenCodeConfig
```

Restart OpenCode after installation so it inherits the new environment variables and MCP configuration.

## Manual Setup

Create `.env` from `.env.example`, set a strong password, and run:

```powershell
docker compose --env-file .env up -d
uv sync --frozen
```

Set the runtime environment:

```powershell
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "your-password"
```

Run the stdio MCP server:

```powershell
uv run literature-graph-mcp --library "D:\Papers"
```

## MCP Client Configuration

Use the absolute paths produced by `install.ps1` when the client does not inherit `uv` from `PATH`.

```json
{
  "mcp": {
    "literature-graph": {
      "type": "local",
      "command": [
        "C:\\path\\to\\uv.exe",
        "--directory",
        "C:\\path\\to\\literature-graph-mcp",
        "run",
        "literature-graph-mcp",
        "--library",
        "C:\\path\\to\\papers"
      ],
      "enabled": true
    }
  }
}
```

The MCP process requires `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` in its environment.

## Visualization UI

A read-only browser viewer for the knowledge graph. It shares the same Neo4j database and `LiteratureGraphRepository` as the MCP server, so nodes and relationships created by agents appear here immediately.

Start it against the same library and database:

```powershell
uv run literature-graph-mcp --ui --port 8000 --library "D:\Papers"
```

Then open <http://127.0.0.1:8000>. The server listens on `127.0.0.1` by default; pass `--host` to change it.

- Search papers, authors, topics, concepts, claims, and methods.
- Browse the graph (drag to pan, scroll to zoom). Paper labels show the first author and year.
- Click a node to open its detail panel (abstract, DOI, source URL, notes, chunks).
- Click **Expand neighbors** to grow the graph from any node.

The UI is read-only for now; editing and user-authorized deletion are planned for a later stage.

## Tool Surface

Read tools:

```text
search_nodes
get_node
get_node_neighborhood
search_papers
get_paper
get_paper_neighborhood
find_path
```

Controlled write tools:

```text
upsert_node
upsert_paper
set_paper_local_path
set_paper_apa7_citation
upsert_node_note
save_paper_chunk
upsert_relationship
```

Deletion and merge tools are intentionally not exposed. Agents may create and update knowledge, but destructive operations require a separate user-authorized workflow.

## Storage Boundary

The repository and Neo4j do not contain your PDF library. Paper nodes store only library-relative paths. The server rejects paths outside the library selected at startup.

Do not commit:

- `.env` or database credentials
- Neo4j data directories
- PDFs or copyrighted source material
- personal Session exports
- project-specific research drafts

## Development

```powershell
uv sync --frozen
uv run pytest
uv build
```

See [DESIGN.md](DESIGN.md) for data boundaries, identity rules, Session Notes, selected Chunks, timelines, and write permissions.

## License

MIT
