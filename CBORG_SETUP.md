# CBORG Setup for Agentic Tols

This guide explains how to set up CBORG to access Claude models for use with the ESS-DIVE MCP server.

## Getting Your CBORG API Key

1. Visit https://cborg.lbl.gov/api_request/
2. Request an API key following the instructions on the page
3. Once approved, you'll receive an API key in the format `sk-XXXXXXXX`
4. Save this key securely

## Setting Up Environment Variables for Claude

To use Claude through CBORG, you need to set three environment variables:

```bash
export ANTHROPIC_AUTH_TOKEN=sk-XXXXXXXX
export ANTHROPIC_BASE_URL=https://api.cborg.lbl.gov
export ANTHROPIC_MODEL=anthropic/claude-sonnet
```

(Add these to `~/.bashrc` or `~/.zshrc`)

Replace `sk-XXXXXXXX` with your actual CBORG API key.

Then start Claude Code normally - it will automatically use the CBORG endpoint.

## Setting Up Environment Variables for Goose

To use CBORG or other custom providers with Goose:

1. Open Goose Settings
2. Navigate to **Configure Providers**
3. Click **Add Custom Provider** and fill in:
   - **Provider Type**: `OpenAI Compatible`
   - **Display Name**: `CBORG`
   - **API URL**: `https://api.cborg.lbl.gov`
   - **API Key**: `YOUR_API_KEY_HERE`
   - **Available Models (comma-separated)**: `anthropic/claude-opus, gpt-5.1, openai/gpt-5, anthropic/claude-sonnet`
4. Save the provider configuration

You can now select CBORG models when starting conversations in Goose.
