# ESS-DIVE MCP Server

An MCP (Model Context Protocol) server for querying ESS-DIVE datasets and the ESS-DeepDive fusion database from chat-based AI clients such as Claude Code, Codex, VS Code with Copilot Chat, and Goose.

## Table of Contents

- [Quick Start](#quick-start)
- [What This Project Is](#what-this-project-is)
- [If You Are New to MCP and Skills](#if-you-are-new-to-mcp-and-skills)
- [Getting Started](#getting-started)
- [Install and Connect to a Client](#install-and-connect-to-a-client)
- [First Queries to Try](#first-queries-to-try)
- [Example Results](#example-results)
- [Tool-Level Examples](#tool-level-examples)
- [Agent Skills](#agent-skills)
- [Available Tools](#available-tools)
- [Command-Line Options](#command-line-options)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Quick Start

If you want the fastest path into ESS-DIVE MCP with a desktop app, use Goose Desktop and follow the instructions below. For this quick-start path, you do not need to clone this repository or run `uv sync`. You do still need to paste a command into Goose's extension settings.

If you want a more detailed Goose walkthrough with screenshots, see [docs/GOOSE_SETUP.md](docs/GOOSE_SETUP.md).

### What you need first

These are the minimum prerequisites:

- Python `3.10` or newer
  Check with `python --version` or `python3 --version`.
  (If you have it, you will get a response like `Python 3.13.4`.)
  If you do not have it, install it from <https://www.python.org/downloads/>.
- `uv`
  Check with `uv --version`.
  (If you have it, you will get a response like `uv 0.7.11`.)
  Install it from <https://docs.astral.sh/uv/getting-started/installation/>.
  The best installation option for `uv` will depend on your system, but note that you may need to refresh your terminal after installing.
- Goose Desktop
  Install it from <https://goose-docs.ai/docs/getting-started/installation/>.
  The best installation option will depend on your system. Once installation is complete, run Goose Desktop to complete the next step.
- Access to an LLM API that Goose Desktop can use.
  Examples include OpenAI, Anthropic, or LBNL's CBORG. If you plan to use CBORG, see [docs/CBORG_SETUP.md](docs/CBORG_SETUP.md). Goose will prompt you to provide LLM API details when you first run it. For more details and visual examples, see [docs/GOOSE_SETUP.md](docs/GOOSE_SETUP.md).
- An ESS-DIVE API token if you need authenticated access to private data.
  Public dataset search and retrieval no longer require a token. If you do need one, sign in at <https://data.ess-dive.lbl.gov>. This generally requires authenticating with your ORCID. Once you have done so, open your profile (upper right), then go to the `Settings` tab -> `Authentication Token`. Create a new token or click the `Renew authentication token` button if you need a new token. Copy this token to a safe place.


⚠️ Important:

- Goose Desktop must already be configured with your LLM provider and API key before the ESS-DIVE MCP extension will be usable.
- If you configure an ESS-DIVE token, the environment variable name must be exactly `ESSDIVE_API_TOKEN`.
- ESS-DIVE says API tokens expire after 24 hours, so if authenticated requests suddenly stop working, generate a fresh token and update the extension.

### Install in Goose Desktop

This is the simplest setup if you want Goose to run `essdive-mcp` directly from GitHub without cloning this repository first:

1. Install Python, `uv`, and Goose Desktop as described above. If you need private-data access, also get an ESS-DIVE token.
2. Open Goose Desktop and configure your LLM provider.
3. Add a new Extension for `essdive-mcp`.
   Use one of these commands:

```text
Windows:
uvx.exe --from git+https://github.com/ess-dive/essdive-mcp essdive-mcp

macOS/Linux:
uvx --from git+https://github.com/ess-dive/essdive-mcp essdive-mcp
```

   If Goose asks for command and arguments separately, use:

   - Windows command: `uvx.exe`
   - Windows arguments: `--from git+https://github.com/ess-dive/essdive-mcp essdive-mcp`
   - macOS/Linux command: `uvx`
   - macOS/Linux arguments: `--from git+https://github.com/ess-dive/essdive-mcp essdive-mcp`

4. If you need private-data access, set the extension environment variable:

```text
ESSDIVE_API_TOKEN=YOUR_ESS_DIVE_TOKEN_HERE
```

   For public dataset search and retrieval, you can leave the ESS-DIVE token unset.

After you save the extension, start a chat in Goose and ask a simple ESS-DIVE question. If the extension is working, Goose should call ESS-DIVE MCP tools automatically without you needing to type a tool name, though it will likely ask you for permission to use the tool first.

### First prompts to try in Goose

The exact results will change over time, but successful responses should look roughly like these examples.

Prompt:

```text
Find 3 public ESS-DIVE datasets about wildfire recovery and summarize each one in 1 sentence.
```

Expected response:

```text
Here are three public ESS-DIVE datasets related to wildfire recovery:

1. Post-fire Time Series Data from Oak Creek Watershed, Washington: This dataset includes sensor and geochemistry sample data from surface water, groundwater, precipitation, soil, and vegetation, providing insights into the ecological recovery of the watershed after a wildfire. [View Dataset](https://data.ess-dive.lbl.gov/view/doi:10.15485/3018020)

2. Pyrogenic Organic Matter Laboratory Experiment: This dataset examines aerobic respiration and geochemical characteristics from variably inundated stream sediments, contributing to our understanding of soil recovery processes post-wildfire. [View Dataset](https://data.ess-dive.lbl.gov/view/doi:10.15485/3001969)

3. Post-fire Time Series Photos from Oak Creek Watershed, Washington: This collection of photographs documents changes over time at five sites across the watershed, visually capturing the landscape's recovery after wildfire disturbance. [View Dataset](https://data.ess-dive.lbl.gov/view/doi:10.15485/3018598)
```

Prompt:

```text
Convert DOI 10.15485/2588618 to an ESS-DIVE dataset ID.
```

Expected response:

```text
The ESS-DIVE dataset ID for the DOI 10.15485/2588618 is ess-dive-f002e3e8be8a266-20260401T000217538.
```

Prompt:

```text
Search ESS-DeepDive for temperature-related fields and summarize what datasets they come from.
```

Expected response:

```text
Here are some temperature-related fields found in the ESS-DeepDive datasets, along with their summaries:

1. **HG_Soil_Temperature_C**: This field measures in situ soil temperature in degrees Celsius, with a record count of 36 values ranging from 19.1 to 26.9°C. It is part of the dataset linked to [DOI: 10.15485/2587853](https://fusion.ess-dive.lbl.gov/api/v1/deepdive/doi:10.15485/2587853:NExpt_ESSDIVE_Datafile.csv).

2. **HG_Soil_Temperature_F**: Similar to the previous field, this one captures in situ soil temperature but in degrees Fahrenheit, also containing 36 records with values from 66.4 to 80.5°F. It belongs to the same dataset as above, accessible via [DOI: 10.15485/2587853](https://fusion.ess-dive.lbl.gov/api/v1/deepdive/doi:10.15485/2587853:NExpt_ESSDIVE_Datafile.csv).

3. **temperature_c**: This field provides groundwater temperature readings in degrees Celsius, with a substantial record count of 144,966 entries ranging from 3.77 to 21.63°C, originating from the dataset associated with [DOI: 10.15485/2587412](https://fusion.ess-dive.lbl.gov/api/v1/deepdive/doi:10.15485/2587412:Machado_Silva_et_al_2024_EST_data.csv).

4. **Effect_Size_Temperature_degC**: This field quantifies the effect size of temperature changes, specifically the comparison between drying and rewetting treatments, with 19 records showing values between -0.3 and 0.5°C. It comes from the dataset tied to [DOI: 10.15485/2583945](https://fusion.ess-dive.lbl.gov/api/v1/deepdive/doi:10.15485/2583945:WHONDRS_MEL_Sample_Data.zip/WHONDRS_EL_Soil_Effect_Size.csv).

5. **Median_Temperature_degC**: Measuring the median temperature with 40 records ranging from 19.8 to 20.8°C, this field is crucial for understanding temperature variations in environmental data, linked to the same dataset as the previous field [DOI: 10.15485/2583945](https://fusion.ess-dive.lbl.gov/api/v1/deepdive/doi:10.15485/2583945:WHONDRS_MEL_Sample_Data.zip/WHONDRS_EL_Soil_Sample_Data_Summary.csv).

These fields collectively provide valuable insights into soil and groundwater temperature dynamics in various environmental contexts.
```

Prompt:

```text
Turn the point 38.9219, -106.9490 into map links I can open in geojson.io and Google Maps.
```

Expected response shape:

```text
Here are the map links for the point **38.9219, -106.9490**:

- **[Open in geojson.io](https://geojson.io/#data=data:application/json,%7B%22type%22%3A%22FeatureCollection%22%2C%22features%22%3A%5B%7B%22type%22%3A%22Feature%22%2C%22geometry%22%3A%7B%22type%22%3A%22Point%22%2C%22coordinates%22%3A%5B-106.949%2C38.9219%5D%7D%2C%22properties%22%3A%7B%7D%7D%2C%7B%22type%22%3A%22Feature%22%2C%22geometry%22%3A%7B%22type%22%3A%22Polygon%22%2C%22coordinates%22%3A%5B%5B%5B-106.949%2C38.9219%5D%2C%5B-106.949%2C38.9219%5D%2C%5B-106.949%2C38.9219%5D%2C%5B-106.949%2C38.9219%5D%2C%5B-106.949%2C38.9219%5D%5D%5D%7D%2C%22properties%22%3A%7B%22type%22%3A%22bbox%22%7D%7D%5D%7D)

- **[Open in Google Maps](https://www.google.com/maps/@?api=1&map_action=map&center=38.9219,-106.949)**

- **[Open in OpenStreetMap](https://www.openstreetmap.org/?minlon=-106.949&minlat=38.9219&maxlon=-106.949&maxlat=38.9219)**

These links will allow you to view the specified coordinates on the respective mapping platforms.
```

If you want a fuller manual setup, more client options, or more example queries, continue with the rest of this README.

## What This Project Is

This project gives an AI client a set of tools for:

- searching public ESS-DIVE datasets
- fetching dataset metadata, version history, and sharing permissions
- converting between ESS-DIVE dataset IDs and DOIs
- parsing File Level Metadata (FLMD) CSV content
- searching ESS-DeepDive field and file metadata
- looking up ESS-DIVE project acronyms, descriptions, and portal URLs
- turning coordinates into map links

## If You Are New to MCP and Skills

You do not need deep background knowledge to try this project.

- An MCP server is a small local program that exposes tools to an AI chat client.
- Your chat client is the interface where you type natural-language questions.
- This repository is the MCP server. You run it locally, then connect to it from a client.
- Agent Skills are optional instruction bundles that help an agent use a toolset more reliably for a specific job. You do not need Skills to run basic ESS-DIVE queries.

The simplest mental model is:

1. Start or register this MCP server.
2. Optionally add an ESS-DIVE token if you need private-data access.
3. Open your AI client.
4. Ask questions in plain English.

## Getting Started

Before you start, make sure you have the following prerequisites:

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

How to check the prerequisites manually:

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

### 1. Download the repository

Option A: clone it with `git`:

```bash
git clone https://github.com/ess-dive/essdive-mcp.git
cd essdive-mcp
```

Option B: on the GitHub repository page, use `Code` -> `Download ZIP`, then extract the ZIP and open the extracted `essdive-mcp` folder in your terminal or editor.

### 2. Check prerequisites from the repository

After you have cloned or extracted the repository and opened the `essdive-mcp` folder in your terminal, the easiest way to check your setup is:

```bash
./scripts/check_prereqs.sh
```

If your shell reports `Permission denied`, run the same script with `bash`, for example:

```bash
bash scripts/check_prereqs.sh
```

This script will check to see if you are missing any install tools like `uv`. It will not check to see if you have client software like Goose or Claude Code installed.

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

### 4. Optionally get an ESS-DIVE authentication token

ESS-DIVE documents the token workflow in its Dataset API docs.

1. Go to `https://data.ess-dive.lbl.gov`
2. Sign in with your ORCID
3. Open your profile (upper right-hand icon)
4. Go to `Settings` -> `Authentication Token`
5. Copy the token

The easiest way to save it locally is:

```bash
./scripts/save_token.sh
```

You only need this token if you want authenticated access, such as private datasets.

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
- starts the MCP server
- uses `essdivetoken` automatically if that file exists

If you prefer the manual command:

```bash
uv run essdive-mcp
```

If you want authenticated/private-data access, you can still provide a token explicitly:

```bash
uv run essdive-mcp --token-file ./essdivetoken
```

What should happen:

- the process starts
- it appears to sit there waiting

This is the expected result. The MCP server communicates over standard input/output, so it does not print an interactive menu. After confirming it starts cleanly, you may stop it (with `Ctrl+C`, or the equivalent on your system) and move on to one client setup below.

## Install and Connect to a Client

Choose one of the following clients to use with the ESS-DIVE MCP server. Install the client desktop app then use the instructions here to connect the client to the MCP server. These are alternatives, not sequential steps.

If your preferred client is not listed here, look for that client's MCP server settings and configure it to run:

```bash
uv run essdive-mcp
```

Client Options:
- VS Code with GitHub Copilot Chat
- Claude Code
- Codex
- Goose

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
      "args": ["run", "essdive-mcp"]
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

If you need authenticated/private-data access, you can add a token with an environment variable instead:

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
  uv run essdive-mcp
```

Then check it:

```bash
claude mcp get essdive-mcp
```

Inside Claude Code, use `/mcp` to confirm the server is connected.

Notes:

- `--transport`, `--scope`, and `--env` flags must come before the server name.
- Use `--scope project` if you want to share the server config with others in this repository.
- Add `--env ESSDIVE_API_TOKEN=...` if you need authenticated/private-data access.

### Codex

Register the server:

```bash
codex mcp add essdive-mcp -- \
  uv run essdive-mcp
```

Or add it manually to `~/.codex/config.toml`:

```toml
[mcp_servers.essdive-mcp]
command = "uv"
args = ["run", "essdive-mcp"]
```

If you need authenticated/private-data access, add `ESSDIVE_API_TOKEN` to your Codex MCP server environment or pass `--token-file`.

Then confirm it:

```bash
codex mcp get essdive-mcp
```

In the Codex TUI, use `/mcp` to inspect active MCP servers.

### Goose

If you want the lowest-friction Goose Desktop setup, use the [Quick Start](#quick-start) path near the top of this README.

For a more detailed Goose walkthrough with screenshots, see [docs/GOOSE_SETUP.md](docs/GOOSE_SETUP.md).

For a Goose Desktop extension that runs directly from GitHub without cloning this repository first:

- Name: `essdive-mcp`
- Windows command: `uvx.exe`
- Windows arguments: `--from git+https://github.com/ess-dive/essdive-mcp essdive-mcp`
- macOS/Linux command: `uvx`
- macOS/Linux arguments: `--from git+https://github.com/ess-dive/essdive-mcp essdive-mcp`
- Environment: optional `ESSDIVE_API_TOKEN=YOUR_ESS_DIVE_TOKEN_HERE`
- Timeout: `300`

If you already cloned this repository and want Goose to run your local checkout instead, add a custom STDIO extension with:

- Name: `essdive-mcp`
- Command: `uv`
- Arguments: `run essdive-mcp`
- Timeout: `300`

If you need authenticated/private-data access, set:

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
- `Show the version history for DOI 10.15485/2529445 and tell me what changed most recently.`
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
The post-filtering examples below were re-checked against the live ESS-DIVE API on April 2, 2026.

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

### Metadata post-filtering examples

These examples use a two-step pattern:

1. run a native ESS-DIVE `/packages` search
2. fetch full metadata for the current result page and filter locally on fields such as `creator.affiliation`, `variableMeasured`, `funder`, or file formats

That means `page_size` and `row_start` matter. The examples below used `page_size=5`, so the local filter examined the first 5 native matches.

Prompt:

```text
Search ESS-DIVE for "East River" datasets, then keep only results whose creators are affiliated with Lawrence Berkeley National Laboratory.
```

Equivalent tool call:

```text
search-datasets with query="East River" and creator_affiliation="Lawrence Berkeley National Laboratory" and page_size=5
```

Example result excerpt:

```text
Found 3 datasets after local metadata filtering. Scanned 5 API results from 307 native matches:

1. Data for "Depth of nutrient uptake by deep-rooted plants is regulated by water availability"
   ID: ess-dive-4c1829de1b8a2ec-20260401T171210416

2. Mountain Basin Controls on the Snow-to-Streamflow Signal: An AIC-Weighted Multiple Linear Regression Framework
   ID: ess-dive-a63ff0854da2d62-20260330T232846064

3. CHESS 2025: Leaf Area Index (LAI) for meadow, shrub, tree, and understory vegetation
   ID: ess-dive-6d3178c5222ea40-20260327T145831553
```

Prompt:

```text
Search ESS-DIVE for "East River" datasets, then keep only results where variableMeasured includes streamflow.
```

Equivalent tool call:

```text
search-datasets with query="East River" and variable_measured="streamflow" and page_size=5
```

Example result excerpt:

```text
Found 1 datasets after local metadata filtering. Scanned 5 API results from 307 native matches:

1. Mountain Basin Controls on the Snow-to-Streamflow Signal: An AIC-Weighted Multiple Linear Regression Framework
   ID: ess-dive-a63ff0854da2d62-20260330T232846064
```

Prompt:

```text
Search ESS-DIVE for "East River" datasets, then keep only results funded by NASA.
```

Equivalent tool call:

```text
search-datasets with query="East River" and funder="NASA" and page_size=5
```

Example result excerpt:

```text
Found 1 datasets after local metadata filtering. Scanned 5 API results from 307 native matches:

1. Site and endmember spectra of terrestrial vegetation and soils for the Colorado Headwaters Ecological Spectroscopy Study, June-July 2025
   ID: ess-dive-c938a042bca2b42-20260327T150016394
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

### Project reference example

Prompt:

```text
What is CHESS, and where can I find more information about it?
```

Example result excerpt:

```text
CHESS stands for Colorado Headwaters Ecological Spectroscopy Study.
It is a remote sensing and field research campaign organized by Rocky Mountain Biological Laboratory
and Berkeley Lab's Watershed Function SFA.
More information: https://ecosis.org/package/proximal-spectra-for-the-2025-colorado-headwaters-ecological-spectroscopy-study--chess-
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
search-datasets with query="East River" and creator_affiliation="Lawrence Berkeley National Laboratory" and page_size=5
search-datasets with query="East River" and variable_measured="streamflow" and page_size=5
search-datasets with query="East River" and funder="NASA" and page_size=5
get-dataset with id="ess-dive-165671432ae620e-20250908T210722395"
get-dataset-versions with id="doi:10.15485/2529445" and page_size=2
get-dataset-versions with id="doi:10.15485/2529445" and cursor="PASTE_NEXT_CURSOR_HERE"
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

What is a Skill?

- a Skill is a reusable instruction document, usually written in Markdown
- a Skill is not the same thing as an MCP server
- Skills can reference MCP tools, but they do not replace them
- agents may use Skills explicitly or implicitly

You can also use the Skills without installing this MCP server. In that case, they still provide task-specific instructions and prompt patterns, and some of them include fallback API examples. You just will not get the full MCP tool integration.

This repository includes three Skills described in [docs/SKILLS.md](docs/SKILLS.md):

- `essdive-datasets`
- `essdive-identifiers`
- `essdeepdive`

### Quick Start for Skills in Goose Desktop

If you want the simplest way to try these Skills in Goose Desktop, use Goose's standard skill directory instead of the `npx` marketplace workflow.

What you need first:

- Goose Desktop installed and configured with an LLM provider
- an ESS-DIVE API token if you need authenticated/private-data ESS-DIVE queries

You do not need Python or `uv` just to install the Skill files themselves.

If you have not set up Goose yet, start with the Goose setup instructions in the [Quick Start](#quick-start) above or the screenshot-based guide in [docs/GOOSE_SETUP.md](docs/GOOSE_SETUP.md).

Important:

- Goose's official Skill docs say this feature requires the built-in `Summon` extension in Goose `v1.25.0` or newer.
- Goose discovers Skills from `~/.agents/skills/` for global Skills or `.agents/skills/` for project-level Skills.
- For these ESS-DIVE Skills, preserve the directory structure exactly so the shared reference file stays in the expected relative location.

Goose's official Skills guide is here:

- <https://goose-docs.ai/docs/guides/context-engineering/using-skills/>

For the easiest install, copy this repository's Skill tree into one of Goose's standard Skill locations:

```text
.agents/skills/
  essdive-datasets/SKILL.md
  essdive-identifiers/SKILL.md
  essdeepdive/SKILL.md
  references/essdive_project_portals.yaml
```

That means either:

- copy the files into `~/.agents/skills/` if you want them available in all Goose sessions
- copy the files into `.agents/skills/` inside a specific project if you want them scoped to that project

If you prefer to create the files manually, create these directories and then copy-paste the contents from this repository:

- [SKILL.md](/home/harry/essdive-mcp/.agents/skills/essdive-datasets/SKILL.md)
- [SKILL.md](/home/harry/essdive-mcp/.agents/skills/essdive-identifiers/SKILL.md)
- [SKILL.md](/home/harry/essdive-mcp/.agents/skills/essdeepdive/SKILL.md)
- [essdive_project_portals.yaml](/home/harry/essdive-mcp/.agents/skills/references/essdive_project_portals.yaml)

After copying the files:

1. Start a new Goose session in the project where the Skills are available.
2. Ask Goose `What skills are available?`
3. Try a prompt like `Use the essdive-identifiers skill to convert DOI 10.15485/2588618 to an ESS-DIVE dataset ID.`

These Skills work best when paired with the ESS-DIVE MCP setup described earlier in this README, because then Goose can call the ESS-DIVE MCP tools directly. Without the MCP server, the Skills may still help Goose structure ESS-DIVE-related tasks, but behavior depends more on Goose's native tools and fallback API usage.

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
- `Use the essdive-datasets skill to list the version history for DOI 10.15485/2529445 and summarize the newest two versions.`
- `Use the essdive-identifiers skill to normalize DOI https://doi.org/10.15485/2587853 and return the ESS-DIVE ID.`
- `Use the essdeepdive skill to search for temperature fields and tell me which data file each result comes from.`

### Skill result examples

Prompt:

```text
Use the essdive-identifiers skill to convert DOI 10.15485/2588618 to an ESS-DIVE dataset ID.
```

Example result:

```text
ess-dive-f002e3e8be8a266-20260401T000217538
```

Prompt:

```text
Use the essdive-datasets skill to search for datasets within 100 meters of 38.8747, -76.5519 and summarize the matches.
```

Example result excerpt:

```text
Found 20 datasets. Showing 3 results:

1. COMPASS-FME Terrestrial Ecosystem Manipulation to Probe the Effects of Storm Treatments (TEMPEST) Experiment Level 1 Sensor Data v2-1
   ID: ess-dive-f002e3e8be8a266-20260401T000217538

2. COMPASS-FME Synoptic Sites Level 1 Sensor Data v2-1
   ID: ess-dive-3aa5e31d62e9ee6-20260331T235820880
```

Prompt:

```text
Use the essdeepdive skill to find temperature fields in ESS-DeepDive and tell me which file they come from.
```

Example result excerpt:

```text
One matching field is HG_Soil_Temperature_C from DOI doi:10.15485/2587853.
It is defined as in situ soil temperature, stored in NExpt_ESSDIVE_Datafile.csv,
and the observed values range from 19.1 to 26.9 C.
```

## Available Tools

### ESS-DIVE dataset tools

- `search-datasets`
- `get-dataset`
- `get-dataset-versions`
- `get-dataset-permissions`
- `parse-flmd-file`

### Identifier tools

- `doi-to-essdive-id`
- `essdive-id-to-doi`

### Project reference tool

- `lookup-project-portal`

### ESS-DeepDive tools

- `search-ess-deepdive`
- `get-ess-deepdive-dataset`
- `get-ess-deepdive-file`

### Mapping tool

- `coords-to-map-links`

## Command-Line Options

- `--token`, `-t`: provide an optional ESS-DIVE API token directly
- `--token-file`: read an optional ESS-DIVE API token from a file
- `--verbose`, `-v`: enable debug logging and include tracebacks in tool error responses

## Environment Variables

- `ESSDIVE_API_TOKEN`: optional ESS-DIVE API token for authenticated/private-data access
- `ESSDIVE_MCP_VERBOSE`: set to `1`, `true`, `yes`, or `on` for verbose diagnostics

## Testing

Run unit tests:

```bash
uv run pytest tests/ -m "not integration"
```

Run live integration tests for public anonymous access:

```bash
uv run pytest tests/integration -m integration
```

To also run authenticated ESS-DIVE integration coverage, set:

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
4. if you need private-data access, your token is valid

### I get an authentication error

Public dataset reads should not require a token. If authenticated/private-data requests fail, refresh your ESS-DIVE token and try again. ESS-DIVE says tokens expire after 24 hours.

### I set an environment variable but authenticated requests still fail

The variable name must be exactly `ESSDIVE_API_TOKEN`.

### I don't see all the results I expect from a dataset search

Search results will depend upon your access to private data. Datasets you do not have access to will not appear in search results. Check on the validity of your ESS-DIVE token if you are using one (see the previous two issues), verify that the entries you expect to see are either public or you have access to them, and re-try the search.

### I am at LBNL and want to use CBORG-backed models

That is optional and not required for this project. See [docs/CBORG_SETUP.md](docs/CBORG_SETUP.md).

## License

BSD-3-Clause
