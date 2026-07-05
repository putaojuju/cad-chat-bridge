# CAD Chat Bridge

CAD Chat Bridge is a public, local-first MCP bridge for connecting ChatGPT-compatible MCP clients to a running AutoCAD process.

The first MVP is intentionally small:

- expose a minimal MCP server over stdio;
- provide a development-only HTTP MCP fallback for Apps SDK server URL testing;
- diagnose whether local AutoCAD COM access is available;
- read the active document metadata when AutoCAD is already running;
- list and describe a safe local command catalog;
- generate conservative viewport/selection probe scripts for future read-only AutoCAD context reads.

It does **not** expose arbitrary AutoLISP execution, arbitrary AutoCAD command execution, drawing save operations, or private business automation.

## Install

```bash
python -m pip install -e ".[dev,mcp]"
```

`pywin32` is only installed on Windows when using the `mcp` extra. AutoCAD COM tools require Windows, AutoCAD, and `pywin32`.

## Run the stdio MCP server

```bash
python -m cad_chat_bridge.mcp_server
```

Example local MCP client configuration:

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

## Run the dev HTTP MCP fallback

```bash
python -m cad_chat_bridge.http_mcp_server --host 127.0.0.1 --port 3333
```

The development HTTP MCP endpoint is:

```text
http://127.0.0.1:3333/mcp
```

Use this only for development connector testing through an external tunnel such as ngrok or Cloudflare Tunnel. See [`docs/DEV_HTTP_CONNECTOR_SETUP.md`](docs/DEV_HTTP_CONNECTOR_SETUP.md).

## MVP tools

Implemented in the first skeleton:

- `cad_ping`
- `cad_diagnose_access`
- `cad_get_active_document`
- `cad_list_catalog`
- `cad_describe_catalog_item`

Not implemented or registered in the MVP:

- `cad_run_lisp(lisp_code)`
- `cad_send_command(command)`
- `cad_load_lisp(path)`
- arbitrary file writes
- drawing save / save-as
- private business catalogs, company drawing rules, shared-drive paths, customer data, or internal retrieval systems

## Local tests

```bash
python -m pip install -e ".[dev]"
pytest
```

Windows + AutoCAD validation is required for COM access checks and active-document reads.
