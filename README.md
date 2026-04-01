# ESS-DIVE MCP Server

An MCP (Model Context Protocol) server for querying ESS-DIVE datasets and the ESS-DeepDive fusion database from chat-based AI clients such as Claude Code, Codex, VS Code with Copilot Chat, and Goose.

## What This Project Is

This project gives an AI client a set of tools for:

- searching public ESS-DIVE datasets
- fetching dataset metadata and sharing permissions
- converting between ESS-DIVE dataset IDs and DOIs
- parsing File Level Metadata (FLMD) CSV content
- searching ESS-DeepDive field and file metadata
- turning coordinates into map links

## If You Are New to MCP and Skills

You do not need deep background knowledge to try this project.

- An MCP server is a small local program that exposes tools to an AI chat client.
- Your chat client is the interface where you type natural-language questions.
- This repository is the MCP server. You run it locally, then connect to it from a client.
- Agent Skills are optional instruction bundles that help an agent use a toolset more reliably for a specific job. You do not need Skills to run basic ESS-DIVE queries.

The simplest mental model is:

1. Get an ESS-DIVE token.
2. Start or register this MCP server.
3. Open your AI client.
4. Ask questions in plain English.

## Getting Started

### 1. Install prerequisites

You will need:

- `git`
- Python 3.10 or newer
- [`uv`](https://docs.astral.sh/uv/) for running the project
- one MCP-capable client:
  - Claude Code
  - Codex
  - VS Code with GitHub Copilot Chat in Agent mode
  - Goose

### 2. Clone the repository and install dependencies

```bash
git clone https://github.com/ess-dive/essdive-mcp.git
cd essdive-mcp
uv sync
```

### 3. Get an ESS-DIVE authentication token

ESS-DIVE documents the token workflow in its Dataset API docs.

1. Go to `https://data.ess-dive.lbl.gov` or `https://data-sandbox.ess-dive.lbl.gov`
2. Sign in with ORCID
3. Open your profile
4. Go to `Settings` -> `Authentication Token`
5. Copy the token

Save it to a local file so you do not have to paste it into shell history:

```bash
printf '%s\n' 'YOUR_ESS_DIVE_TOKEN_HERE' > essdivetoken
```

Important:

- ESS-DIVE says the token expires after 24 hours.
- The environment variable name is `ESSDIVE_API_TOKEN`.
- You can authenticate with `--token`, `--token-file`, or `ESSDIVE_API_TOKEN`.

### 4. Sanity-check the server locally

Run:

```bash
uv run essdive-mcp --token-file ./essdivetoken
```

What should happen:

- the process starts
- it appears to sit there waiting
- that is normal

This server communicates over standard input/output, so it does not print an interactive menu. After confirming it starts cleanly, stop it with `Ctrl+C` and move on to one client setup below.

## Connect From One Client

Choose one of the following. These are alternatives, not sequential steps.

### VS Code with GitHub Copilot Chat

This is a good option for users who want a familiar GUI instead of a terminal-only workflow.

GitHub's Copilot MCP documentation says Visual Studio Code 1.99 or later is required.

Create a project-scoped MCP config at `.vscode/mcp.json`:

```json
{
  "servers": {
    "essdive-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "essdive-mcp",
        "--token-file",
        "${workspaceFolder}/essdivetoken"
      ]
    }
  }
}
```

Then:

1. Open this repository in VS Code.
2. Open `.vscode/mcp.json`.
3. Click `Start` above the server entry.
4. Open Copilot Chat.
5. Switch the chat mode to `Agent`.
6. Open the tools list and confirm `essdive-mcp` is available.

If you prefer not to keep the token in a file, you can use an environment variable instead:

```json
{
  "servers": {
    "essdive-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "essdive-mcp"],
      "env": {
        "ESSDIVE_API_TOKEN": "YOUR_ESS_DIVE_TOKEN_HERE"
      }
    }
  }
}
```

### Claude Code

Register the server:

```bash
claude mcp add --transport stdio essdive-mcp -- \
  uv run essdive-mcp --token-file ./essdivetoken
```

Then check it:

```bash
claude mcp get essdive-mcp
```

Inside Claude Code, use `/mcp` to confirm the server is connected.

Notes:

- `--transport`, `--scope`, and `--env` flags must come before the server name.
- Use `--scope project` if you want to share the server config with others in this repository.

### Codex

Register the server:

```bash
codex mcp add essdive-mcp -- \
  uv run essdive-mcp --token-file ./essdivetoken
```

Or add it manually to `~/.codex/config.toml`:

```toml
[mcp_servers.essdive-mcp]
command = "uv"
args = ["run", "essdive-mcp", "--token-file", "/absolute/path/to/essdivetoken"]
```

Then confirm it:

```bash
codex mcp get essdive-mcp
```

In the Codex TUI, use `/mcp` to inspect active MCP servers.

### Goose

In Goose, add a custom STDIO extension with:

- Name: `essdive-mcp`
- Command: `uv`
- Arguments: `run essdive-mcp --token-file /absolute/path/to/essdivetoken`
- Timeout: `300`

If you prefer environment variables, set:

- `ESSDIVE_API_TOKEN=YOUR_ESS_DIVE_TOKEN_HERE`

## First Queries to Try

Start with plain natural-language prompts. You do not need to call tool names directly.

### ESS-DIVE dataset search

Try prompts like:

- `Find public ESS-DIVE datasets about soil carbon and summarize the top five results.`
- `Search ESS-DIVE for datasets inside the bounding box [38.9187, -106.9532, 38.9263, -106.9451].`
- `Search ESS-DIVE for datasets within 100 meters of 38.8747, -76.5519 and summarize the results.`
- `Find ESS-DIVE datasets published in 2024 about wildfire recovery.`
- `Look for datasets with temporal coverage between 2020 and 2021 and show the dataset IDs.`

### Dataset details and permissions

- `Get the metadata for ESS-DIVE dataset ess-dive-165671432ae620e-20250908T210722395.`
- `Show the sharing permissions for ESS-DIVE dataset ess-dive-165671432ae620e-20250908T210722395.`

### Identifier conversion

- `Convert DOI 10.15485/2587853 to an ESS-DIVE dataset ID.`
- `Convert ESS-DIVE ID ess-dive-165671432ae620e-20250908T210722395 to a DOI.`

### ESS-DeepDive queries

- `Search ESS-DeepDive for temperature-related fields and summarize what datasets they come from.`
- `Find ESS-DeepDive fields with the word soil in the definition.`
- `Search ESS-DeepDive for temperature fields with at least 100 records.`

### Mapping helper

- `Turn the point 38.9219, -106.9490 into map links I can open in geojson.io and Google Maps.`
- `Create map links for the bounding box [38.9187, -106.9532, 38.9263, -106.9451].`

## Tool-Level Examples

If your client supports direct tool calling, these examples map closely to the available tools.

```text
search-datasets with query="wildfire recovery" and page_size=5
search-datasets with begin_date="2020" and end_date="2021" and format="detailed"
search-datasets with bbox=[38.9187, -106.9532, 38.9263, -106.9451]
search-datasets with lat=38.8747 and lon=-76.5519 and radius=100
get-dataset with id="ess-dive-165671432ae620e-20250908T210722395"
get-dataset-permissions with id="ess-dive-165671432ae620e-20250908T210722395"
doi-to-essdive-id with doi="10.15485/2587853"
essdive-id-to-doi with essdive_id="ess-dive-165671432ae620e-20250908T210722395"
search-ess-deepdive with field_name="temperature" and page_size=5
coords-to-map-links with points=[[38.9219, -106.9490]] and zoom=12
```

## Agent Skills

Skills are optional. They are useful when you want an agent to consistently recognize a recurring task pattern, such as:

- dataset discovery and metadata follow-up
- DOI and ESS-DIVE ID conversion
- ESS-DeepDive field and file exploration

Based on the Agent Skills conventions described in the March 12, 2026 AI4Curation presentation:

- a Skill is a reusable instruction document, usually written in Markdown
- a Skill is not the same thing as an MCP server
- Skills can reference MCP tools, but they do not replace them
- agents may use Skills explicitly or implicitly

This repository includes three Skills under [`.agents/skills/README.md`](/home/harry/essdive-mcp/.agents/skills/README.md):

- `essdive-datasets`
- `essdive-identifiers`
- `essdeepdive`

### Install Skills in Claude Code

Register the local marketplace:

```bash
/plugin marketplace add ./.claude-plugin/marketplace.json
```

Then install the Skill you want from that marketplace.

### Install Skills in Codex

Use the helper script:

```bash
./scripts/install_codex_skills.sh
```

This creates symlinks in `~/.codex/skills` (or `$CODEX_HOME/skills`).

Remove them later with:

```bash
./scripts/uninstall_codex_skills.sh
```

### Skill usage examples

You can ask for a Skill by name, or let the agent choose it when relevant.

Examples:

- `Use the essdive-datasets skill to find recent wildfire-related datasets and then fetch the metadata for the best match.`
- `Use the essdive-identifiers skill to normalize DOI https://doi.org/10.15485/2587853 and return the ESS-DIVE ID.`
- `Use the essdeepdive skill to search for temperature fields and tell me which data file each result comes from.`

## Available Tools

### ESS-DIVE dataset tools

- `search-datasets`
- `get-dataset`
- `get-dataset-permissions`
- `parse-flmd-file`

### Identifier tools

- `doi-to-essdive-id`
- `essdive-id-to-doi`

### ESS-DeepDive tools

- `search-ess-deepdive`
- `get-ess-deepdive-dataset`
- `get-ess-deepdive-file`

### Mapping tool

- `coords-to-map-links`

## Command-Line Options

- `--token`, `-t`: provide an ESS-DIVE API token directly
- `--token-file`: read the token from a file
- `--verbose`, `-v`: enable debug logging and include tracebacks in tool error responses

## Environment Variables

- `ESSDIVE_API_TOKEN`: ESS-DIVE API token
- `ESSDIVE_MCP_VERBOSE`: set to `1`, `true`, `yes`, or `on` for verbose diagnostics

## Testing

Run unit tests:

```bash
uv run pytest tests/ -m "not integration"
```

Run live integration tests:

```bash
export ESSDIVE_API_TOKEN="YOUR_ESS_DIVE_TOKEN_HERE"
uv run pytest tests/integration -m integration
```

## Troubleshooting

### The server starts and then seems to do nothing

That is expected. MCP stdio servers wait for a client to connect.

### My client does not show any ESS-DIVE tools

Check:

1. the server is registered correctly
2. the server is started
3. your client is in agent mode if required
4. your token is valid

### I get an authentication error

Refresh your ESS-DIVE token and try again. ESS-DIVE says tokens expire after 24 hours.

### I set an environment variable but the server still fails

The variable name must be exactly `ESSDIVE_API_TOKEN`.

### I am at LBNL and want to use CBORG-backed models

That is optional and not required for this project. See [CBORG_SETUP.md](/home/harry/essdive-mcp/CBORG_SETUP.md).

## License

BSD-3-Clause
