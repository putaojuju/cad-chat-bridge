# ChatGPT MCP Setup

This document shows how to run CAD Chat Bridge as a local stdio MCP server.

## Install

```bash
python -m pip install -e ".[mcp]"
```

For development:

```bash
python -m pip install -e ".[dev,mcp]"
pytest
```

## Run

```bash
python -m cad_chat_bridge.mcp_server
```

## Example client configuration

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

## Windows and AutoCAD notes

AutoCAD access requires Windows, AutoCAD already running, pywin32, and compatible process integrity levels. If AutoCAD is elevated but Python is not, COM access can fail. Use `cad_diagnose_access` to inspect the local environment.

## MVP tools

The first skeleton registers only:

- `cad_ping`
- `cad_diagnose_access`
- `cad_get_active_document`
- `cad_list_catalog`
- `cad_describe_catalog_item`

The MVP intentionally does not register write-capable tools, save operations, web services, tunnels, or private business catalogs.
