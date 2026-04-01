# ESS-DIVE MCP Server

An MCP (Model Context Protocol) server for querying ESS-DIVE datasets and the ESS-DeepDive fusion database from chat-based AI clients such as Claude Code, Codex, VS Code with Copilot Chat, and Goose.

Those are examples, not the full list. If your client can connect to local stdio MCP servers, you can usually configure `essdive-mcp` there as well.

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

The easiest way to check your setup is:

```bash
./scripts/check_prereqs.sh
```

If your shell reports `Permission denied`, run the same script with `bash`, for example:

```bash
bash scripts/check_prereqs.sh
```

What each prerequisite is for:

- Python 3.10 or newer
  Python runs the `essdive-mcp` server itself.
- [`uv`](https://docs.astral.sh/uv/)
  `uv` installs the project dependencies and runs the server.
- `git`
  `git` is only needed if you want to clone the repository from the command line. If you prefer, you can download the repository as a ZIP file from GitHub instead.
- one MCP-capable client if you want to use the MCP server directly:
  - Claude Code
  - Codex
  - VS Code with GitHub Copilot Chat in Agent mode
  - Goose

Other MCP-capable clients may also work. The clients listed here are just the ones this README documents explicitly.

How to check them manually:

- Check Python:

```bash
python3 --version
```

If that does not work, try:

```bash
python --version
```

You need Python `3.10` or newer. If you do not have it, install it from <https://www.python.org/downloads/>.

- Check `uv`:

```bash
uv --version
```

If you do not have `uv`, install it using the official Astral instructions:

macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

- Check `git`:

```bash
git --version
```

If you do not have `git`, you can still continue by downloading this repository as a ZIP file from GitHub and extracting it locally.

### 2. Download the repository

Option A: clone it with `git`:

```bash
git clone https://github.com/ess-dive/essdive-mcp.git
cd essdive-mcp
```

Option B: on the GitHub repository page, use `Code` -> `Download ZIP`, then extract the ZIP and open the extracted `essdive-mcp` folder in your terminal or editor.

### 3. Install the project locally

The easiest way is:

```bash
./scripts/setup_local.sh
```

This script:

- checks your required prerequisites
- runs `uv sync`
- tells you the next steps

If you prefer the manual command:

```bash
uv sync
```

### 4. Get an ESS-DIVE authentication token

ESS-DIVE documents the token workflow in its Dataset API docs.

1. Go to `https://data.ess-dive.lbl.gov` or `https://data-sandbox.ess-dive.lbl.gov`
2. Sign in with ORCID
3. Open your profile
4. Go to `Settings` -> `Authentication Token`
5. Copy the token

The easiest way to save it locally is:

```bash
./scripts/save_token.sh
```

Important:

- ESS-DIVE says the token expires after 24 hours.
- The environment variable name is `ESSDIVE_API_TOKEN`.
- You can authenticate with `--token`, `--token-file`, or `ESSDIVE_API_TOKEN`.

If you prefer the manual command, you can still save the token to `essdivetoken` yourself.

### 5. Sanity-check the server locally

The easiest way is:

```bash
./scripts/start_server.sh
```

This script:

- checks that `uv` is available
- checks that your token file exists
- starts the MCP server with that token file

If you prefer the manual command:

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

If your preferred client is not listed here, look for that client's MCP server settings and configure it to run:

```bash
uv run essdive-mcp --token-file ./essdivetoken
```

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

## Example Results

The exact results will change over time as ESS-DIVE and ESS-DeepDive are updated, but successful queries should look roughly like this.

### Dataset search example

Prompt:

```text
Search ESS-DIVE for datasets within 100 meters of 38.8747, -76.5519 and summarize the results.
```

Example result excerpt:

```text
Found 20 datasets. Showing 3 results:

1. COMPASS-FME Terrestrial Ecosystem Manipulation to Probe the Effects of Storm Treatments (TEMPEST) Experiment Level 1 Sensor Data v2-1
   ID: ess-dive-f002e3e8be8a266-20260401T000217538
   Published: 2025
   URL: https://data.ess-dive.lbl.gov/view/doi:10.15485/2588618

2. COMPASS-FME Synoptic Sites Level 1 Sensor Data v2-1
   ID: ess-dive-3aa5e31d62e9ee6-20260331T235820880
   Published: 2025
```

### Identifier conversion example

Prompt:

```text
Convert DOI 10.15485/2588618 to an ESS-DIVE dataset ID.
```

Example result:

```text
ess-dive-f002e3e8be8a266-20260401T000217538
```

The reverse conversion should return:

```text
doi:10.15485/2588618
```

### ESS-DeepDive field search example

Prompt:

```text
Search ESS-DeepDive for temperature-related fields.
```

Example result excerpt:

```json
{
  "field_name": "HG_Soil_Temperature_C",
  "unit": "C",
  "definition": "In situ soil temperature",
  "data_type": "numeric",
  "total_record_count": 36,
  "missing_values_count": 10,
  "values_summary": {
    "min": 19.1,
    "max": 26.9
  },
  "doi": "doi:10.15485/2587853",
  "version": "ess-dive-165671432ae620e-20250908T210722395",
  "data_file": "NExpt_ESSDIVE_Datafile.csv"
}
```

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

You can also use the Skills without installing this MCP server. In that case, they still provide task-specific instructions and prompt patterns, and some of them include fallback API examples. You just will not get the full MCP tool integration.

This repository includes three Skills described in [docs/SKILLS.md](docs/SKILLS.md):

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

That is optional and not required for this project. See [docs/CBORG_SETUP.md](docs/CBORG_SETUP.md).

## License

BSD-3-Clause
