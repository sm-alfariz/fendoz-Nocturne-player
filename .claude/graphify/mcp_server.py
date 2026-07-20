#!/usr/bin/env python3
"""
Minimal MCP stdio server wrapping graphify CLI.
Zero dependencies — uses only stdlib (json, subprocess, sys).

Exposes 4 tools:
  graphify_query     — BFS traversal for codebase questions
  graphify_explain   — plain-language explanation of a concept
  graphify_path      — shortest path between two concepts
  graphify_affected  — what would break if I change X
"""

import json
import subprocess
import sys
import os

GRAPHIFY_PY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "graphify-out", ".graphify_python",
)

def _get_python():
    try:
        return open(GRAPHIFY_PY).read().strip()
    except FileNotFoundError:
        return sys.executable

def _run_graphify(*args, timeout=15):
    """Run graphify CLI and return stdout."""
    python = _get_python()
    cmd = [python, "-m", "graphify"] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip()
    except subprocess.TimeoutExpired:
        return "Error: graphify command timed out"
    except Exception as e:
        return f"Error: {e}"

TOOLS = [
    {
        "name": "graphify_query",
        "description": "BFS traversal of the codebase knowledge graph. Ask questions like 'how does playback work' or 'what calls PlayerEngine'. Returns relevant nodes and edges.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural language question about the codebase",
                },
                "budget": {
                    "type": "integer",
                    "description": "Max tokens in output (default 2000)",
                    "default": 2000,
                },
                "dfs": {
                    "type": "boolean",
                    "description": "Use depth-first instead of breadth-first",
                    "default": False,
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "graphify_explain",
        "description": "Plain-language explanation of a concept or node in the codebase graph. Shows the node, its community, and key connections.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string",
                    "description": "Node name or concept to explain (e.g. 'PlayerEngine', 'SignalBus')",
                },
            },
            "required": ["concept"],
        },
    },
    {
        "name": "graphify_path",
        "description": "Find the shortest path between two concepts in the codebase. Shows how they're connected through the graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_concept": {
                    "type": "string",
                    "description": "Starting concept (e.g. 'SongsView')",
                },
                "to_concept": {
                    "type": "string",
                    "description": "Target concept (e.g. 'PlayerEngine')",
                },
            },
            "required": ["from_concept", "to_concept"],
        },
    },
    {
        "name": "graphify_affected",
        "description": "Reverse traversal: find all nodes that would be impacted if you change or remove a concept. Use before refactoring.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string",
                    "description": "Concept to check impact for (e.g. 'Track', 'PlayerEngine')",
                },
                "depth": {
                    "type": "integer",
                    "description": "Traversal depth (default 2)",
                    "default": 2,
                },
            },
            "required": ["concept"],
        },
    },
]

# ── JSON-RPC over stdio ─────────────────────────────────────────────

def handle_request(req):
    method = req.get("method")
    params = req.get("params", {})
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "graphify", "version": "0.1.0"},
            },
        }

    if method == "notifications/initialized":
        return None  # no response needed

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        result = call_tool(tool_name, args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": result}],
                "isError": result.startswith("Error"),
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def call_tool(name, args):
    if name == "graphify_query":
        cmd_args = ["query", args["question"], "--budget", str(args.get("budget", 2000))]
        if args.get("dfs"):
            cmd_args.append("--dfs")
        return _run_graphify(*cmd_args)

    if name == "graphify_explain":
        return _run_graphify("explain", args["concept"])

    if name == "graphify_path":
        return _run_graphify("path", args["from_concept"], args["to_concept"])

    if name == "graphify_affected":
        return _run_graphify(
            "affected", args["concept"],
            "--depth", str(args.get("depth", 2)),
        )

    return f"Error: unknown tool {name}"


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        resp = handle_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
