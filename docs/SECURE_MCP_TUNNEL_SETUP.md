# Secure MCP Tunnel Setup

This guide documents the preferred cloud ChatGPT test path for CAD Chat Bridge.

CAD Chat Bridge remains a local stdio MCP server. For ChatGPT cloud testing, use OpenAI Secure MCP Tunnel so the local server can stay inside the workstation trust boundary while ChatGPT reaches it through an OpenAI-managed tunnel endpoint.

## Local stdio vs cloud ChatGPT connector testing

Local stdio testing means the MCP client runs on the same workstation and starts the server with a command such as:

```powershell
python -m cad_chat_bridge.mcp_server
```

That path is useful for local clients such as Codex, Claude Desktop, MCP Inspector, or any MCP client that can launch a stdio server on the same machine.

Cloud ChatGPT cannot directly connect to a local process's stdin/stdout on your workstation. For cloud ChatGPT connector testing, keep this project as a local stdio MCP server and use Secure MCP Tunnel to bridge ChatGPT to the local stdio command.

## Why this path

The MVP is intentionally not an HTTP server and does not bind a public port. A generic public HTTP tunnel is not the right default for an AutoCAD bridge because the target process is a local desktop CAD session.

Secure MCP Tunnel keeps the private MCP server address local to the machine or network where `tunnel-client` runs. The client connects outbound to OpenAI and forwards MCP JSON-RPC requests to the configured local stdio command.

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

## Connect from ChatGPT

In ChatGPT:

1. Open Settings.
2. Open Apps & Connectors.
3. Enable Developer mode under Advanced settings if required by your workspace.
4. Go to Connectors and create a custom connector.
5. Choose Tunnel as the connection type.
6. Select the available tunnel or paste the `tunnel_id`.
7. Create the connector and add it to a new chat.

If the tunnel is not visible, check that the tunnel is associated with the target ChatGPT workspace and that your account has permission to use it.

## MVP cloud test checklist

First-round cloud testing must be limited to these five MVP tools:

- `cad_ping`
- `cad_diagnose_access`
- `cad_get_active_document`
- `cad_list_catalog`
- `cad_describe_catalog_item`

Expected results:

- Without AutoCAD or on non-Windows, diagnostic tools should return structured errors rather than crashing.
- With AutoCAD open on Windows, `cad_get_active_document` should return the current document metadata.
- If AutoCAD and Python run at different Windows integrity levels, diagnostics should point to that mismatch.

## AutoCAD permission notes

Run AutoCAD and the MCP Python process at the same Windows integrity level:

- both normal user, or
- both elevated.

A mismatch can prevent COM access. Prefer normal user for both unless you have a specific local reason to elevate.

## Security rules for cloud testing

- Keep the MVP implementation local stdio-only.
- Do not add HTTP server code to this MVP just for cloud testing.
- Do not expose the local AutoCAD bridge through ngrok, a generic public HTTP tunnel, or a public port.
- Do not add tools that pass through arbitrary CAD commands.
- Do not add tools that evaluate caller-supplied CAD scripts.
- Do not add save or save-as tools during this tunnel test.
- Do not put API keys, tunnel IDs for private environments, customer names, shared-drive paths, or real drawing files into git.

## Troubleshooting

- Re-run `tunnel-client doctor --profile cad-chat-bridge --explain`.
- Confirm `tunnel-client run --profile cad-chat-bridge` is still running.
- Confirm the tunnel is associated with the ChatGPT workspace you are using.
- Confirm your account has tunnel use permission.
- Confirm the `--mcp-command` Python path points to the environment where this package is installed.
- If COM access fails, run `cad_diagnose_access` and compare the AutoCAD and Python integrity levels.

## References

- OpenAI Secure MCP Tunnel: https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
- OpenAI Apps SDK quickstart: https://developers.openai.com/apps-sdk/quickstart
