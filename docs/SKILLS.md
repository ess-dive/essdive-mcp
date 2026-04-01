# ESS-DIVE Skills

This guide describes the optional Agent Skills bundled with this repository.

You do not need Skills for basic natural-language queries. Start without them if you are new to MCP, then add Skills if you want more predictable agent behavior for repeated ESS-DIVE tasks.

## What A Skill Is

A Skill is a reusable instruction document that helps an AI agent handle a recurring task pattern.

In this repository, the Skills help an agent:

- search ESS-DIVE datasets
- convert between DOIs and ESS-DIVE IDs
- query ESS-DeepDive field and file metadata

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

## Available Skills

### `essdive-datasets`

Search ESS-DIVE datasets with keyword, temporal, and geographic filters; fetch metadata and permissions; and parse FLMD CSV content.

See [`../.agents/skills/essdive-datasets/SKILL.md`](../.agents/skills/essdive-datasets/SKILL.md).

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
- `Use the essdive-datasets skill to search for datasets inside the bounding box [38.9187, -106.9532, 38.9263, -106.9451] and summarize the matches.`
- `Use the essdive-datasets skill to search for datasets within 100 meters of 38.8747, -76.5519 and summarize the matches.`

### `essdive-identifiers`

- `Use the essdive-identifiers skill to convert DOI 10.15485/2587853 to an ESS-DIVE dataset ID.`
- `Use the essdive-identifiers skill to normalize https://doi.org/10.15485/2587853 and return the DOI and dataset ID.`

### `essdeepdive`

- `Use the essdeepdive skill to find temperature fields in ESS-DeepDive and summarize the results by dataset DOI.`
- `Use the essdeepdive skill to inspect a specific ESS-DeepDive file and list its variables.`
