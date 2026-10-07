"""Deterministic MCP JSON-RPC peer for native discovery and execution gates."""

import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI(title="Woobe MCP qualification peer")


@app.get("/health")
async def health():
    return {"ready": True}


@app.post("/mcp")
async def mcp(request: Request):
    payload = await request.json()
    method = payload.get("method")
    if method == "notifications/initialized":
        return Response(status_code=202)
    if method == "initialize":
        result = {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "portable-peer", "version": "1.0"},
        }
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": "lookup",
                    "description": "Lookup portable tenant",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"tenant": {"type": "string"}},
                        "required": ["tenant"],
                        "additionalProperties": False,
                    },
                }
            ]
        }
    elif method == "tools/call":
        params = payload.get("params") or {}
        if params.get("name") != "lookup":
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": payload.get("id"),
                    "error": {"code": -32602, "message": "Unknown Tool"},
                }
            )
        result = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {"tenant": (params.get("arguments") or {}).get("tenant")}
                    ),
                }
            ],
            "isError": False,
        }
    else:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": payload.get("id"),
                "error": {"code": -32601, "message": "Unknown method"},
            }
        )
    return JSONResponse(
        {"jsonrpc": "2.0", "id": payload.get("id"), "result": result},
        headers={"Mcp-Session-Id": "portable-native-session"},
    )


@app.get("/http-protected")
async def protected_lookup(request: Request):
    if (
        request.headers.get("authorization")
        != "Bearer ephemeral-native-environment-token"
        or request.headers.get("x-tool-token") != "ephemeral-native-tool-token"
    ):
        return JSONResponse(
            {"error": "Destination authentication is required"}, status_code=403
        )
    return {"tenant": "portable-tenant", "authenticated": True}
