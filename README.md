# ESS-DIVE MCP Server

An MCP (Model Context Protocol) server for querying the ESS-DIVE (Environmental System Science Data Infrastructure for a Virtual Ecosystem) API and the ESS-DeepDive fusion database.

## Overview

This project implements a Model Context Protocol server that allows language models to search and retrieve information from the ESS-DIVE repository and the ESS-DeepDive fusion database. The server provides comprehensive access to dataset search, detailed dataset information, identifier conversion, FLMD parsing, dataset permissions, and fusion database queries through the ESS-DIVE and ESS-DeepDive APIs.

## Features

- **ESS-DIVE Dataset Tools**:
  - Search for datasets with various filtering options (keywords, creators, dates, etc.)
  - Retrieve detailed information about specific datasets
  - Access dataset metadata, creators, keywords, and file listings
  - Get dataset sharing permissions
  - Parse File Level Metadata (FLMD) CSV files

- **Identifier Conversion**:
  - Convert between DOIs and ESS-DIVE dataset IDs
  - Support for flexible DOI formats (with/without prefix, URLs, etc.)
  - Automatic DOI normalization

- **ESS-DeepDive Fusion Database**:
  - Search the fusion database for data fields and values
  - Filter by field names, definitions, text values, numeric values, dates, and record counts
  - Retrieve detailed field information for specific files
  - Support for pagination and DOI filtering
  - Download file metadata and information

## Example Queries

### Searching

```
> Search ESS-DIVE for datasets involving snowfall in Colorado. 

● essdive-mcp - search-datasets (MCP)(query: "snowfall Colorado", page_size: 10, format: "summary")
  ⎿ {                                                                                                                                                                                                                         
      "result": "Found 5 datasets. Showing 5 results:\n\n1. Groundwater and Surface Water Flow (GSFLOW) model files to explore bedrock circulation depth and porosity in Copper Creek, Colorado\n   ID: ess-dive-9ea5fe57db73c
    90-20241024T093714082510\n   Published: 2024\n   URL: https://data.ess-dive.lbl.gov/view/doi:10.15485/2453885\n\n2. Data from: \"Warming and provenance limit tree recruitment across and beyond the elevation range of su
    …
```

## Installation

### Install from Source

1. Clone this repository
2. Navigate to the project directory
3. Install using uv:

```bash
uv init
uv add .
```

## Usage

### Run the Server

```bash
uv run python src/essdive_mcp/main.py --token YOUR_ESS_DIVE_TOKEN_HERE
```

### Install MCP in Claude Code

Claude Code can connect to local MCP servers over stdio. All options
(`--transport`, `--env`, `--scope`, `--header`) must come before the server
name, and `--` separates Claude's flags from the server command.

Local scope (default, only for you in this project; stored in `~/.claude.json`
under this project's path):

```
claude mcp add --transport stdio --env ESSDIVE_API_TOKEN=YOUR_ESS_DIVE_TOKEN_HERE essdive-mcp -- \
  uv run python ./src/essdive_mcp/main.py
```

Project scope (shared via `.mcp.json` in the repo). Claude Code will prompt
for approval before using a project-scoped server. To reset approvals:

```
claude mcp reset-project-choices
```

```
claude mcp add --transport stdio --scope project --env ESSDIVE_API_TOKEN=YOUR_ESS_DIVE_TOKEN_HERE essdive-mcp -- \
  uv run python ./src/essdive_mcp/main.py
```

User scope (available across all projects):

```
claude mcp add --transport stdio --scope user --env ESSDIVE_API_TOKEN=YOUR_ESS_DIVE_TOKEN_HERE essdive-mcp -- \
  uv run python ./src/essdive_mcp/main.py
```

Note: in older Claude Code versions, `local` scope was called `project`, and
`user` scope was called `global`.

Manage servers:

```
claude mcp list
claude mcp get essdive-mcp
claude mcp remove essdive-mcp
```

Within Claude Code, use `/mcp` to check server status.

### Install MCP in Codex

Codex uses the same MCP configuration for both the CLI and the IDE extension.
You can add servers with the CLI or edit `~/.codex/config.toml` directly. You
can also create a project-scoped config at `.codex/config.toml` (trusted
projects only).

Add the server with the CLI:

```
codex mcp add essdive-mcp --env ESSDIVE_API_TOKEN=YOUR_ESS_DIVE_TOKEN_HERE -- \
  uv run python ./src/essdive_mcp/main.py
```

Or configure it in `~/.codex/config.toml`:

```
[mcp_servers.essdive-mcp]
command = "uv"
args = ["run", "python", "./src/essdive_mcp/main.py"]

[mcp_servers.essdive-mcp.env]
ESSDIVE_API_TOKEN = "YOUR_ESS_DIVE_TOKEN_HERE"
```

Manage servers:

```
codex mcp list
codex mcp get essdive-mcp
codex mcp remove essdive-mcp
```

In the Codex TUI, use `/mcp` to view active servers.

## Skills (Claude Code + Codex)

This repository includes skill definitions under `skills/` that can be used by
Claude Code and Codex.

### Claude Code

Register the skills plugin:

```
/plugin marketplace add ./.claude-plugin/marketplace.json
```

### Codex

Copy or symlink the skill folders into your Codex skills directory (usually
`~/.codex/skills`), for example:

```
ln -s "$(pwd)/skills/essdive-datasets" ~/.codex/skills/essdive-datasets
ln -s "$(pwd)/skills/essdive-identifiers" ~/.codex/skills/essdive-identifiers
ln -s "$(pwd)/skills/essdeepdive" ~/.codex/skills/essdeepdive
```

Or use the helper script:

```
./scripts/install_codex_skills.sh
```

Remove the links later with:

```
./scripts/uninstall_codex_skills.sh
```


### Command Line Options

- `--name`: Set the name of the MCP server (default: `essdive-server`)
- `--token`: Provide an ESS-DIVE API token for authentication

### Environment Variables

The server can also be configured using environment variables:

- `ESSDIVE_API_TOKEN`: Your ESS-DIVE API token. This is used for authenticated requests to the ESS-DIVE API. It can be used as an alternative to the `--token` command-line argument.

### Using with Claude Desktop

1. Run the server
2. In Claude Desktop, connect to the running server
3. Use the available tools and resources:
   - Search for datasets by keywords, authors, or content
   - Retrieve detailed information about specific datasets

## Available Tools

### ESS-DIVE Dataset Tools

#### search-datasets

Search for datasets in the ESS-DIVE repository with flexible filtering options.

**Parameters:**
- `query` (optional): Full-text search query across dataset metadata
- `creator` (optional): Filter by dataset creator
- `provider_name` (optional): Filter by dataset project/provider
- `date_published` (optional): Filter by publication date (e.g., "[2016 TO 2023]")
- `keywords` (optional): Search for datasets with specific keywords (string or list)
- `row_start` (optional): The row number to start on for pagination (default: 1)
- `page_size` (optional): Number of results per page, max 100 (default: 25)
- `format` (optional): Format of results - `summary`, `detailed`, or `raw` (default: summary)

**Example:**
```
search-datasets with query="soil carbon" and page_size=10
```

#### get-dataset

Get detailed information about a specific ESS-DIVE dataset.

**Parameters:**
- `id` (required): ESS-DIVE dataset identifier

**Returns:** Complete dataset metadata including name, description, creators, keywords, files, and distribution information.

#### get-dataset-permissions

Get sharing permissions for a specific ESS-DIVE dataset.

**Parameters:**
- `id` (required): ESS-DIVE dataset identifier

**Returns:** List of users/groups with access and their permission levels.

#### parse-flmd-file

Parse a File Level Metadata (FLMD) CSV file and extract file descriptions.

**Parameters:**
- `content` (required): The FLMD CSV file content as a string

**Returns:** JSON mapping of filenames to their descriptions.

**FLMD Format:** CSV file with columns for filename and file description (supports case-insensitive header matching).

### Identifier Conversion Tools

#### doi-to-essdive-id

Convert a DOI to an ESS-DIVE dataset ID by querying the ESS-DIVE API.

**Parameters:**
- `doi` (required): A DOI in any common format:
  - `doi:10.xxxx/...`
  - `10.xxxx/...`
  - `https://doi.org/10.xxxx/...`
  - `http://doi.org/10.xxxx/...`

**Returns:** JSON with original DOI and converted ESS-DIVE ID.

**Use Case:** When you have a DOI but need the ESS-DIVE dataset ID for other tools.

#### essdive-id-to-doi

Convert an ESS-DIVE dataset ID to a DOI by querying the ESS-DIVE API.

**Parameters:**
- `essdive_id` (required): An ESS-DIVE dataset identifier

**Returns:** JSON with original ESS-DIVE ID and normalized DOI (format: `doi:10.xxxx/...`).

**Use Case:** When you have an ESS-DIVE dataset ID but need the DOI for external services.

### ESS-DeepDive Fusion Database Tools

#### search-ess-deepdive

Search the ESS-DeepDive fusion database for data fields and values.

**Parameters:**
- `field_name` (optional): Search for a specific field name (max 100 chars)
- `field_definition` (optional): Search field definitions (max 100 chars)
- `field_value_text` (optional): Search for text field values (case insensitive)
- `field_value_numeric` (optional): Filter by numeric value
- `field_value_date` (optional): Filter by date value (yyyy-mm-dd or yyyy-mm-ddTHH:MM:SS)
- `record_count_min` (optional): Filter by minimum record count
- `record_count_max` (optional): Filter by maximum record count
- `doi` (optional): Filter by DOI (comma-separated for multiple, max 100)
- `row_start` (optional): Starting row for pagination (default: 1)
- `page_size` (optional): Results per page, max 100 (default: 25)
- `max_pages` (optional): Maximum number of pages to automatically fetch (for large result sets)

**Returns:** Search results with field metadata and pagination info. Automatically collects results across multiple pages if `max_pages` is specified.

**Example:**
```
search-ess-deepdive with field_name="temperature" and record_count_min=100
```

#### get-ess-deepdive-dataset

Get detailed field information for a specific dataset file in ESS-DeepDive.

**Parameters:**
- `doi` (required): The DOI of the dataset (with or without 'doi:' prefix)
- `file_path` (required): The file path within the dataset

**Returns:** Complete field metadata including field names, definitions, data types, record counts, and value ranges.

#### get-ess-deepdive-file

Retrieve detailed information about a specific file from ESS-DeepDive (Get-Dataset-File endpoint).

**Parameters:**
- `doi` (required): The DOI of the dataset (format: `doi:10.xxxx/...` or `10.xxxx/...`)
- `file_path` (required): The file path within the dataset (e.g., "dataset.zip/data.csv")

**Returns:** JSON with summary of key file information and complete API response including:
- All field names and their definitions
- Data types and summary statistics for each field
- File metadata and download information
- Record counts and value ranges
- Download URLs

**Use Case:** After finding a file of interest from `search-ess-deepdive`, retrieve complete field-level metadata before downloading.

## License

BSD
