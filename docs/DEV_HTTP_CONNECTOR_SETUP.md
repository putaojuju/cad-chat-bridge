# Dev HTTP Connector Setup

This document describes the development-only HTTP MCP fallback for testing CAD Chat Bridge from ChatGPT with a server URL.

## Status

This is a development testing fallback, not a production deployment recommendation.

The normal implementation boundary is still small and safe:

- only the five MVP tools are registered;
- no arbitrary AutoLISP execution;
- no arbitrary AutoCAD command passthrough;
- no LISP file loading;
- no file-write tools;
- no drawing save or save-as tools;
- no private business catalog.

## Start the local HTTP MCP server

Install the MCP extra, then run the development HTTP entry point:

```powershell
git clone -b init-mvp-skeleton https://github.com/putaojuju/cad-chat-bridge.git
cd cad-chat-bridge
python -m pip install -e ".[dev,mcp]"
python -m pytest -q
python -m cad_chat_bridge.http_mcp_server --host 127.0.0.1 --port 3333
```

The MCP endpoint is:

```text
http://127.0.0.1:3333/mcp
```

The default host is `127.0.0.1`. The server does not bind to `0.0.0.0` by default.

## Expose the local port for ChatGPT server URL testing

Use a development tunnel such as ngrok or Cloudflare Tunnel to expose the local port.

Example with ngrok:

```powershell
ngrok http 3333
```

Example with Cloudflare Tunnel:

```powershell
cloudflared tunnel --url http://127.0.0.1:3333
```

Use the HTTPS URL from the tunnel and append `/mcp`.

Example ChatGPT server URL:

```text
https://example-tunnel-domain/mcp
```

## ChatGPT connector settings

In ChatGPT connector setup:

1. Create a custom connector.
2. Choose the server URL / Apps SDK HTTP route.
3. Enter the HTTPS tunnel URL ending in `/mcp`.
4. For the first development pass, choose no authentication / none if the UI allows it.
5. If the UI requires OAuth, stop here: this MVP does not implement OAuth yet.
6. Add the connector to a fresh chat and test only the five MVP tools.

## First test scope

Only test these tools:

- `cad_ping`
- `cad_diagnose_access`
- `cad_get_active_document`
- `cad_list_catalog`
- `cad_describe_catalog_item`

Do not add broader CAD control tools just to make the connector test easier.

## Active document path redaction

HTTP mode redacts the AutoCAD document `FullName` by default. `cad_get_active_document` should return only the file name, AutoCAD application/status fields, and `quiescent` unless path exposure is explicitly enabled.

To temporarily include `full_name` for local-only debugging, set:

```powershell
$env:CAD_CHAT_BRIDGE_HTTP_EXPOSE_FULLNAME = "1"
```

Do not enable this when sharing logs, screenshots, or connector output.

## Binding safety

The development HTTP server defaults to loopback:

```text
127.0.0.1:3333
```

Do not bind this bridge directly to a public interface. If a temporary external test is needed, prefer a tunnel that forwards to the loopback address.

A non-loopback wildcard bind requires an explicit local environment override and should not be used for normal testing:

```powershell
$env:CAD_CHAT_BRIDGE_HTTP_ALLOW_PUBLIC_BIND = "1"
```

## Windows and AutoCAD notes

For AutoCAD COM tests:

- AutoCAD must be running locally.
- `pywin32` must be installed through the `mcp` extra on Windows.
- Python and AutoCAD should run at compatible Windows integrity levels.
- Prefer running both as a normal user unless you have a specific local reason to elevate both.

## Troubleshooting

- Confirm `python -m cad_chat_bridge.http_mcp_server --host 127.0.0.1 --port 3333` is running.
- Confirm the tunnel points to `http://127.0.0.1:3333`.
- Confirm the ChatGPT server URL ends with `/mcp`.
- Confirm the connector is not configured for OAuth unless OAuth support has been added in a future PR.
- Test `cad_ping` before calling AutoCAD-specific tools.
- If AutoCAD access fails, call `cad_diagnose_access` and inspect Windows integrity-level hints.
