# CBORG Setup

This guide explains how to use Berkeley Lab's CBORG service with AI clients that can also use this repository's MCP server.

CBORG is optional for `essdive-mcp`. Most users can ignore this page unless they specifically want to run Claude Code, Codex, or another supported client against CBORG-hosted models.

## Before You Start

CBORG's API key page says:

- you must store API keys securely
- you should not put raw API keys in source code
- keys are created through the CBORG key manager
- keys have an initial monthly budget
- keys expire after one year

CBORG also states that the API is experimental and should not be used for confidential, export-controlled, or public-facing chatbot workloads.

## Request a CBORG API Key

1. Open [CBORG API Key Request](https://cborg.lbl.gov/api_request/).
2. Review the terms of service.
3. Continue to the CBORG Key Manager.
4. Sign in with your Lab-connected Google identity.
5. Create or copy your API key.

Store the key in an environment variable instead of committing it to a file:

```bash
export CBORG_API_KEY=sk-REPLACE_ME
```

## Verify That The Key Works

The CBORG API FAQ shows two simple checks.

Verify the key itself:

```bash
curl --location "https://api.cborg.lbl.gov/key/info" \
  --header "Authorization: Bearer $CBORG_API_KEY"
```

Check current spend:

```bash
curl --location "https://api.cborg.lbl.gov/user/info" \
  --header "Authorization: Bearer $CBORG_API_KEY"
```

CBORG also documents a spend page at <https://api.cborg.lbl.gov/key/manage>.

## Claude Code With CBORG

CBORG maintains a Claude Code setup page with current model environment variables.

Set:

```bash
export CBORG_API_KEY=sk-REPLACE_ME

export ANTHROPIC_AUTH_TOKEN=$CBORG_API_KEY
export ANTHROPIC_BASE_URL=https://api.cborg.lbl.gov

export ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-4-5
export ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-4-6
export ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-4-6

export ANTHROPIC_MODEL=claude-sonnet-4-6
export CLAUDE_CODE_SUBAGENT_MODEL=claude-haiku-4-5

export DISABLE_NON_ESSENTIAL_MODEL_CALLS=1
export DISABLE_TELEMETRY=1
export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=8192
```

Then verify:

```bash
env | grep ANTHROPIC
```

Start Claude Code:

```bash
cd /path/to/essdive-mcp
claude
```

After Claude Code is using CBORG, you can configure `essdive-mcp` exactly as described in the main [README](../README.md).

## Codex With CBORG

CBORG's Codex page uses the OpenAI-compatible interface:

```bash
export CBORG_API_KEY=sk-REPLACE_ME

export OPENAI_API_KEY=$CBORG_API_KEY
export OPENAI_BASE_URL=https://api.cborg.lbl.gov
```

Then verify:

```bash
env | grep OPENAI
```

Start Codex:

```bash
cd /path/to/essdive-mcp
codex
```

CBORG's Codex page notes:

- the default model is `o4-mini`
- `gpt-5-codex` is supported and recommended for best performance

For example:

```bash
codex -m gpt-5-codex
```

Or configure the model in your Codex config.

## Other OpenAI-Compatible Clients

The following setup is an inference from the CBORG API FAQ, which says OpenAI-compatible clients must override the base URL to CBORG.

For clients that accept an OpenAI-style API key and base URL:

- API key: your `CBORG_API_KEY`
- base URL: `https://api.cborg.lbl.gov`

If the client runs on LBL-Net, the FAQ says you may use:

- `https://api-local.cborg.lbl.gov`

This can apply to some third-party tools, but you should still check that tool's own CBORG documentation before relying on it.

## Troubleshooting

### Invalid API key errors

The CBORG FAQ says this often happens when an OpenAI-compatible app is still pointing at the wrong provider endpoint. Make sure the base URL is set to:

```text
https://api.cborg.lbl.gov
```

### Unexpected costs

CBORG's Claude Code page warns that Claude Code can become expensive if it uses too many tools, too much context, or more model capacity than needed.

### Need current model names

The CBORG FAQ points to the model info endpoint:

```bash
curl --location "https://api.cborg.lbl.gov/model/info" \
  --header "Authorization: Bearer $CBORG_API_KEY"
```

## Sources

- [CBORG API FAQ](https://cborg.lbl.gov/api_faq/)
- [CBORG API Key Request](https://cborg.lbl.gov/api_request/)
- [Claude Code with CBORG](https://cborg.lbl.gov/tools_claudecode/)
- [Using CBORG with OpenAI Codex CLI](https://cborg.lbl.gov/tools_codex/)
- [CBORG Model Selection Overview](https://cborg.lbl.gov/tools_ai_101/)
