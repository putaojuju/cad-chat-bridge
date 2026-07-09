# Safety Model

CAD Chat Bridge is designed as a local-only MCP bridge. The public MVP deliberately keeps the trust boundary narrow.

## Trust Boundary

The bridge runs on the same machine as AutoCAD and communicates with MCP clients over stdio. It does not start an HTTP service, bind a TCP port, expose a tunnel, or make AutoCAD reachable from the public internet.

## Default Capabilities

The MVP only registers tools for:

- server reachability checks;
- local AutoCAD access diagnostics;
- active-document metadata reads;
- safe catalog discovery;
- safe catalog item description.

Viewport and selection probe generation exists as library code and tests, but the MVP does not execute the probe through COM yet.

## Explicitly Forbidden in the MVP

The public MVP must not register tools that provide:

- arbitrary AutoLISP execution;
- arbitrary AutoCAD command execution;
- arbitrary LISP file loading;
- arbitrary file writes;
- drawing save or save-as operations;
- public HTTP endpoints, tunnels, or remote listeners;
- private business catalogs or company-specific CAD automation.

## Catalog Boundary

The catalog is a manifest, not a command shell. A catalog item must declare:

- a stable public id;
- whether it is enabled;
- whether it is runnable;
- its effect category;
- whether it modifies drawings, writes files, or loads LISP;
- a parameter schema.

The first skeleton only lists and describes catalog items. It does not run them.

## File Boundary

Any future tool that writes artifacts must write only inside a controlled local artifact root. Caller-supplied absolute paths, parent directory traversal, shared-drive paths, and network locations must be rejected unless a future explicit allowlist policy is added and reviewed.

## AutoCAD Boundary

AutoCAD COM access is local and optional. COM calls must have:

- platform checks;
- dependency checks;
- timeouts;
- `IsQuiescent` checks before commands in future write-capable tools;
- clear diagnostic errors instead of hanging the MCP stdio channel.

## Private Data Boundary

This public repository must not include:

- company drawing rules;
- stone-ordering or production business logic;
- shared-drive paths;
- intranet retrieval code;
- order ledgers;
- customer names;
- real drawing fixtures;
- private AutoLISP command catalogs.
