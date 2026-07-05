# ChatGPT MCP Setup

This document shows how to run CAD Chat Bridge as a local stdio MCP server and how to test it from ChatGPT cloud through the development HTTP connector fallback.

## Install

```bash
python -m pip install -e ".[mcp]"
```

For development:

```bash
python -m pip install -e ".[dev,mcp]"
pytest
```

## Run locally with stdio

```bash
python -m cad_chat_bridge.mcp_server
```

## Example local client configuration

```json
{
  "mcpServers": {
    "cad-chat-bridge": {
      "command": "python",
      "args": ["-m", "cad_chat_bridge.mcp_server"]
    }
  }
}
```

## Run local dev HTTP fallback

```bash
python -m cad_chat_bridge.http_mcp_server --host 127.0.0.1 --port 3333
```

The HTTP MCP endpoint is:

```text
http://127.0.0.1:3333/mcp
```

For ChatGPT server URL testing, expose that local port with a development tunnel such as ngrok or Cloudflare Tunnel and use the HTTPS URL ending in `/mcp`.

See [`DEV_HTTP_CONNECTOR_SETUP.md`](DEV_HTTP_CONNECTOR_SETUP.md) for the full dev connector workflow.

## Windows and AutoCAD notes

AutoCAD access requires Windows, AutoCAD already running, pywin32, and compatible process integrity levels. If AutoCAD is elevated but Python is not, COM access can fail. Use `cad_diagnose_access` to inspect the local environment.

## MVP tools

The first skeleton registers only:

- `cad_ping`
- `cad_diagnose_access`
- `cad_get_active_document`
- `cad_list_catalog`
- `cad_describe_catalog_item`

The MVP intentionally does not register write-capable tools, save operations, arbitrary command passthrough, arbitrary AutoLISP execution, or private business catalogs.
