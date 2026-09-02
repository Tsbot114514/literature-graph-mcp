[CmdletBinding()]
param(
    [string]$LibraryPath = (Join-Path $HOME "literature-library\papers"),
    [string]$Neo4jPassword = "",
    [switch]$SkipOpenCodeConfig
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "Required command not found: $Name"
    }
    return $command
}

function Set-ObjectProperty {
    param(
        [object]$Object,
        [string]$Name,
        [object]$Value
    )

    $Object.PSObject.Properties.Remove($Name)
    $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$docker = Require-Command "docker"
$uv = Require-Command "uv"

& $docker.Source compose version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose is unavailable. Start or install Docker Desktop."
}

$libraryRoot = [System.IO.Path]::GetFullPath($LibraryPath)
$libraryParent = Split-Path -Parent $libraryRoot
if (-not (Test-Path -LiteralPath $libraryParent)) {
    New-Item -ItemType Directory -Path $libraryParent -Force | Out-Null
}
if (-not (Test-Path -LiteralPath $libraryRoot)) {
    New-Item -ItemType Directory -Path $libraryRoot -Force | Out-Null
}

if (-not $Neo4jPassword) {
    $Neo4jPassword = "lgmcp-" + [Guid]::NewGuid().ToString("N")
}

$envPath = Join-Path $projectRoot ".env"
$envLines = @(
    "NEO4J_PASSWORD=$Neo4jPassword"
    "NEO4J_HTTP_PORT=7474"
    "NEO4J_BOLT_PORT=7687"
)
[System.IO.File]::WriteAllLines(
    $envPath,
    $envLines,
    (New-Object System.Text.UTF8Encoding($false))
)

$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = $Neo4jPassword
$env:LITERATURE_LIBRARY_PATH = $libraryRoot

[Environment]::SetEnvironmentVariable("NEO4J_URI", $env:NEO4J_URI, "User")
[Environment]::SetEnvironmentVariable("NEO4J_USER", $env:NEO4J_USER, "User")
[Environment]::SetEnvironmentVariable("NEO4J_PASSWORD", $Neo4jPassword, "User")
[Environment]::SetEnvironmentVariable("LITERATURE_LIBRARY_PATH", $libraryRoot, "User")

& $docker.Source compose --project-directory $projectRoot --env-file $envPath up -d
if ($LASTEXITCODE -ne 0) {
    throw "Neo4j failed to start."
}

& $uv.Source --directory $projectRoot sync --frozen
if ($LASTEXITCODE -ne 0) {
    throw "Python dependency installation failed."
}

$healthy = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    Start-Sleep -Seconds 2
    $status = & $docker.Source inspect --format "{{.State.Health.Status}}" literature-graph-neo4j 2>$null
    if ($status -eq "healthy") {
        $healthy = $true
        break
    }
}
if (-not $healthy) {
    throw "Neo4j did not become healthy within 120 seconds."
}

$mcpConfig = [pscustomobject][ordered]@{
    type = "local"
    command = @(
        $uv.Source
        "--directory"
        $projectRoot
        "run"
        "literature-graph-mcp"
        "--library"
        $libraryRoot
    )
    enabled = $true
}

$generatedPath = Join-Path $projectRoot "opencode.mcp.generated.json"
[pscustomobject][ordered]@{
    mcp = [pscustomobject][ordered]@{
        "literature-graph" = $mcpConfig
    }
} | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $generatedPath -Encoding UTF8

$configured = $false
if (-not $SkipOpenCodeConfig) {
    $configDirectory = Join-Path $HOME ".config\opencode"
    $configPath = Join-Path $configDirectory "opencode.jsonc"
    if (-not (Test-Path -LiteralPath $configDirectory)) {
        New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null
    }

    try {
        if (Test-Path -LiteralPath $configPath) {
            $rawConfig = Get-Content -LiteralPath $configPath -Raw
            $config = $rawConfig | ConvertFrom-Json
            $backupPath = "$configPath.backup-$(Get-Date -Format 'yyyyMMddHHmmss')"
            Copy-Item -LiteralPath $configPath -Destination $backupPath
        } else {
            $config = [pscustomobject][ordered]@{
                '$schema' = "https://opencode.ai/config.json"
            }
        }

        if ($null -eq $config.mcp) {
            Set-ObjectProperty -Object $config -Name "mcp" -Value ([pscustomobject]@{})
        }
        Set-ObjectProperty -Object $config.mcp -Name "literature-graph" -Value $mcpConfig
        $config | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $configPath -Encoding UTF8
        $configured = $true
    } catch {
        "OpenCode config was not changed: $($_.Exception.Message)"
        "Use the generated snippet: $generatedPath"
    }
}

"Literature Graph MCP is installed."
"Library: $libraryRoot"
"Neo4j: bolt://localhost:7687"
"Generated MCP config: $generatedPath"
if ($configured) {
    "OpenCode configuration updated. Restart OpenCode before using the MCP."
} elseif ($SkipOpenCodeConfig) {
    "OpenCode configuration skipped by request."
}
