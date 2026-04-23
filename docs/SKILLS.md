# ESS-DIVE Skills

This guide describes the optional Agent Skills bundled with this repository.

You do not need Skills for basic natural-language queries. Start without them if you are new to MCP, then add Skills if you want more predictable agent behavior for repeated ESS-DIVE tasks.

You also do not need this repository's MCP server in order to use the Skills themselves. The Skills can still be installed as reusable instruction documents, but without the MCP server they will rely on whatever built-in tools or fallback HTTP/API approaches your client supports.

## What A Skill Is

A Skill is a reusable instruction document that helps an AI agent handle a recurring task pattern.

In this repository, the Skills help an agent:

- search ESS-DIVE datasets
- convert between DOIs and ESS-DIVE IDs
- query ESS-DeepDive field and file metadata
- resolve ESS-DIVE project acronyms and portal URLs from a shared local reference file

A Skill is not:

- the MCP server itself
- a replacement for authentication
- a place to store API keys
- a substitute for the project README

The MCP server provides the tools. A Skill helps the agent decide how and when to use them.

## When You Need Skills

Use a Skill when you want:

- more consistent agent behavior on repeated ESS-DIVE tasks
- built-in examples for a specific task family
- a clearer hint to the agent about which ESS-DIVE tools to use

Skills may be used:

- explicitly, by naming the Skill in your prompt
- implicitly, when the agent recognizes that a Skill matches your request

## Skills With And Without MCP

With the MCP server:

- the agent can call the ESS-DIVE and ESS-DeepDive tools exposed by `essdive-mcp`
- the Skills can guide the agent toward those tools directly

Without the MCP server:

- the Skills still provide reusable instructions, examples, and task framing
- some Skill docs include fallback direct API examples
- behavior depends more on your client's native tools and capabilities

The shared project reference file lives at [`../.agents/skills/references/essdive_project_portals.yaml`](../.agents/skills/references/essdive_project_portals.yaml).

## Available Skills

### `essdive-datasets`

Search ESS-DIVE datasets with keyword, temporal, and geographic filters; fetch metadata, version history, and permissions; and parse FLMD CSV content.

See [`../.agents/skills/essdive-datasets/SKILL.md`](../.agents/skills/essdive-datasets/SKILL.md).

This Skill also covers a two-step search pattern for dataset metadata fields that are not native `/packages` query params, such as `variableMeasured`, `measurementTechnique`, `funder`, `creator.affiliation`, and file-level distribution metadata.

What that enables in practice:

- start with a broad search like `East River`
- then narrow the current result page by creator affiliation, measured variable, funder, license, or file metadata

Verified live on April 2, 2026 with `page_size=5`:

- `query="East River"` plus `creator_affiliation="Lawrence Berkeley National Laboratory"` narrowed the first page from 5 results down to 3
- `query="East River"` plus `variable_measured="streamflow"` narrowed the same first page to 1 result
- `query="East River"` plus `funder="NASA"` narrowed the same first page to 1 result

Because this filtering happens after the initial API search, `page_size` and `row_start` affect what gets inspected locally.

### `essdive-identifiers`

Convert between ESS-DIVE dataset IDs and DOIs.

See [`../.agents/skills/essdive-identifiers/SKILL.md`](../.agents/skills/essdive-identifiers/SKILL.md).

### `essdeepdive`

Query the ESS-DeepDive fusion database for fields and file metadata.

See [`../.agents/skills/essdeepdive/SKILL.md`](../.agents/skills/essdeepdive/SKILL.md).

### Shared mapping helper

All three Skills also reference `coords-to-map-links` for turning points or bounding boxes into links for tools such as geojson.io and OpenStreetMap.

## Install In Claude Code

Register the local marketplace:

```bash
/plugin marketplace add ./.claude-plugin/marketplace.json
```

Then install one or more ESS-DIVE Skills from that marketplace.

## Install In Codex

Run:

```bash
./scripts/install_codex_skills.sh
```

This creates symlinks in `~/.codex/skills` or `$CODEX_HOME/skills`.

To remove them:

```bash
./scripts/uninstall_codex_skills.sh
```

## Example Prompts

### `essdive-datasets`

- `Use the essdive-datasets skill to find public ESS-DIVE datasets about wildfire recovery and summarize the top results.`
- `Use the essdive-datasets skill to search for BIONTE datasets sorted by name ascending and summarize the first three.`
- `Use the essdive-datasets skill to search for BIONTE datasets, then continue to the next page with the returned cursor.`
- `Use the essdive-datasets skill to search for BIONTE datasets, keep the pagination cursor, and show me the next page if I ask for more results.`
- `Use the essdive-datasets skill to search for BIONTE datasets and then show me the next page without exposing the cursor values.`
- `Use the essdive-datasets skill to search for datasets inside the bounding box [38.9187, -106.9532, 38.9263, -106.9451] and summarize the matches.`
- `Use the essdive-datasets skill to search for datasets within 100 meters of 38.8747, -76.5519 and summarize the matches.`
- `Use the essdive-datasets skill to show the version history for DOI 10.15485/2529445 and summarize the newest two versions.`
- `Use the essdive-datasets skill to check the status of dataset ess-dive-f78cb03d11550da-20260309T160313214.`
- `Use the essdive-datasets skill to search for East River datasets and then keep only results with Lawrence Berkeley Lab creator affiliations.`
- `Use the essdive-datasets skill to search for East River datasets and then keep only results where variableMeasured includes streamflow.`

### `essdive-identifiers`

- `Use the essdive-identifiers skill to convert DOI 10.15485/2587853 to an ESS-DIVE dataset ID.`
- `Use the essdive-identifiers skill to normalize https://doi.org/10.15485/2587853 and return the DOI and dataset ID.`

### `essdeepdive`

- `Use the essdeepdive skill to find temperature fields in ESS-DeepDive and summarize the results by dataset DOI.`
- `Use the essdeepdive skill to inspect a specific ESS-DeepDive file and list its variables.`
