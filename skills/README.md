# essdive-mcp skills

This directory contains skill definitions for Claude Code and Codex.

## Available skills

### essdive-datasets

Search ESS-DIVE datasets, fetch metadata and permissions, and parse FLMD CSV content.

See `essdive-datasets/SKILL.md` for full documentation.

### essdive-identifiers

Convert between ESS-DIVE dataset IDs and DOIs.

See `essdive-identifiers/SKILL.md` for full documentation.

### essdeepdive

Query the ESS-DeepDive fusion database for fields and file metadata.

See `essdeepdive/SKILL.md` for full documentation.

### Mapping helper

All skills also include `coords-to-map-links` to turn points or bounding boxes into
map links (geojson.io and OpenStreetMap).

## Use in Claude Code

```
/plugin marketplace add ./.claude-plugin/marketplace.json
```

This registers the skills as a plugin in Claude Code.

## Use in Codex

Run the helper script to symlink the skills into your Codex skills directory:

```
./scripts/install_codex_skills.sh
```

To remove the links:

```
./scripts/uninstall_codex_skills.sh
```
