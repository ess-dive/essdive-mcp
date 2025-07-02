# ESS-DIVE MCP Server

An MCP (Model Context Protocol) server for querying the ESS-DIVE (Environmental System Science Data Infrastructure for a Virtual Ecosystem) API.

## Overview

This project implements a Model Context Protocol server that allows language models to search and retrieve information from the ESS-DIVE repository. The server provides access to dataset search functionality and detailed dataset information through the ESS-DIVE API.

## Features

- Search for datasets with various filtering options
- Retrieve detailed information about specific datasets
- Access dataset metadata, creators, keywords, and file listings
- Results formatted in human-readable text or markdown

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
python main.py
```

### Command Line Options

- `--name`: Set the name of the MCP server (default: `essdive-server`)
- `--api-token`: Provide an ESS-DIVE API token for authentication (optional)

### Environment Variables

- `ESSDIVE_API_TOKEN`: Alternative way to provide the ESS-DIVE API token

### Using with Claude Desktop

1. Run the server
2. In Claude Desktop, connect to the running server
3. Use the available tools and resources:
   - Search for datasets by keywords, authors, or content
   - Retrieve detailed information about specific datasets

## Available Tools

### search-datasets

Search for datasets in the ESS-DIVE repository.

Parameters:
- `query`: Search query text
- `creator`: Filter by dataset creator
- `provider_name`: Filter by dataset project/provider
- `is_public`: If true, only return public packages
- `date_published`: Filter by publication date
- `keywords`: Search for datasets with specific keywords
- `row_start`: The row number to start on (for pagination)
- `page_size`: Number of results per page (max 100)
- `format`: Format of the results (summary, detailed, raw)

### get-dataset

Get detailed information about a specific dataset.

Parameters:
- `id`: ESS-DIVE dataset identifier

## Available Resources

- `essdive://search` - Search for datasets
- `essdive://dataset-info?id=<dataset-id>` - Get detailed information about a specific dataset

## License

MIT