# Secure MCP Tunnel Setup

> Status: archived alternative. The current PR now uses [`DEV_HTTP_CONNECTOR_SETUP.md`](DEV_HTTP_CONNECTOR_SETUP.md) for ChatGPT Apps SDK server URL testing.

This guide is kept for reference if Secure MCP Tunnel is revisited later. It is not the current recommended path for this branch.

CAD Chat Bridge can remain a local stdio MCP server. If Secure MCP Tunnel is used in the future, the local server can stay inside the workstation trust boundary while ChatGPT reaches it through an OpenAI-managed tunnel endpoint.

## Local stdio vs cloud ChatGPT connector testing

Local stdio testing means the MCP client runs on the same workstation and starts the server with a command such as:

```powershell
python -m cad_chat_bridge.mcp_server
```

That path is useful for local clients such as Codex, Claude Desktop, MCP Inspector, or any MCP client that can launch a stdio server on the same machine.

Cloud ChatGPT cannot directly connect to a local process's stdin/stdout on your workstation. If Secure MCP Tunnel is used, keep this project as a local stdio MCP server and use Secure MCP Tunnel to bridge ChatGPT to the local stdio command.

## Why this path was considered

The MVP should not expose broad CAD control capabilities. Secure MCP Tunnel keeps the private MCP server address local to the machine or network where `tunnel-client` runs. The client connects outbound to OpenAI and forwards MCP JSON-RPC requests to the configured local stdio command.

## Prerequisites

- Windows workstation for AutoCAD validation.
- AutoCAD already running for COM tests.
- Python 3.10 or newer.
- A checkout of this repository.
- OpenAI tunnel access in the relevant Platform organization and ChatGPT workspace.
- A `tunnel_id` from Platform tunnel settings.
- A runtime API key for `tunnel-client` stored in your local shell or password manager, not in git.
- The latest `tunnel-client` binary from the official OpenAI tunnel settings page or the public release channel.

## Local package setup

PowerShell example:

```powershell
git clone -b init-mvp-skeleton https://github.com/putaojuju/cad-chat-bridge.git
cd cad-chat-bridge
python -m pip install -e ".[dev,mcp]"
python -m pytest -q
```

Optional: use an explicit virtualenv Python path so `tunnel-client` always starts the same environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,mcp]"
.\.venv\Scripts\python.exe -m pytest -q
```

## Local stdio smoke test

Before using the tunnel, verify that the server can start locally:

```powershell
python -m cad_chat_bridge.mcp_server
```

Stop it with Ctrl+C after confirming it starts. The tunnel client will start the stdio server itself through `--mcp-command`.

## Configure tunnel-client for stdio MCP

Set the runtime key in your local shell using your normal secret-handling process. Do not commit it.

PowerShell example with the active Python:

```powershell
tunnel-client init `
  --sample sample_mcp_stdio_local `
  --profile cad-chat-bridge `
  --tunnel-id <YOUR_TUNNEL_ID> `
  --mcp-command "python -m cad_chat_bridge.mcp_server"
```

PowerShell example with a virtualenv Python path:

```powershell
tunnel-client init `
  --sample sample_mcp_stdio_local `
  --profile cad-chat-bridge `
  --tunnel-id <YOUR_TUNNEL_ID> `
  --mcp-command ".\.venv\Scripts\python.exe -m cad_chat_bridge.mcp_server"
```

Then check and run:

```powershell
tunnel-client doctor --profile cad-chat-bridge --explain
tunnel-client run --profile cad-chat-bridge
```

Keep `tunnel-client run` open while testing from ChatGPT. Connector discovery and tool calls depend on the running client.

## MVP cloud test checklist

First-round cloud testing must be limited to these five MVP tools:

- `cad_ping`
- `cad_diagnose_access`
- `cad_get_active_document`
- `cad_list_catalog`
- `cad_describe_catalog_item`

## Security rules

- Keep the MVP tool set limited.
- Do not add tools that pass through arbitrary CAD commands.
- Do not add tools that evaluate caller-supplied CAD scripts.
- Do not add save or save-as tools during connector testing.
- Do not put API keys, tunnel IDs for private environments, customer names, shared-drive paths, or real drawing files into git.

## References

- OpenAI Secure MCP Tunnel: https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
- OpenAI Apps SDK quickstart: https://developers.openai.com/apps-sdk/quickstart
