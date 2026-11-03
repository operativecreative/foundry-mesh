"""Authenticated HTTP boundary for the isolated security gateway.

Bind to loopback by default and terminate TLS at a trusted reverse proxy.
"""
from __future__ import annotations

import hmac
import json
import os
from typing import Any

from aiohttp import web

from mesh.security_gateway import (
    SecurityError, SecurityGateway, SecurityStore, parse_tool_action,
)


def _bearer_matches(request: web.Request, expected: str) -> bool:
    supplied = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not supplied.startswith(prefix):
        return False
    return hmac.compare_digest(supplied[len(prefix):], expected)


def _action_data(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"name", "arguments", "call_id"}:
        raise SecurityError("Action envelope must contain name, arguments and call_id")
    return value


def create_app(
    gateway: SecurityGateway | None = None,
    gateway_token: str | None = None,
    approval_token: str | None = None,
) -> web.Application:
    gateway_token = gateway_token or os.environ.get("MESH_GATEWAY_TOKEN", "")
    approval_token = approval_token or os.environ.get("MESH_APPROVAL_TOKEN", "")
    if not gateway_token or not approval_token:
        raise RuntimeError("MESH_GATEWAY_TOKEN and MESH_APPROVAL_TOKEN are required")
    if hmac.compare_digest(gateway_token, approval_token):
        raise RuntimeError("Gateway and approval credentials must be distinct")
    if gateway is None:
        db_path = os.environ.get("MESH_SECURITY_DB", "data/security-gateway.sqlite3")
        gateway = SecurityGateway(SecurityStore(db_path))

    app = web.Application(client_max_size=512 * 1024)
    async def authorize(request: web.Request, expected: str) -> None:
        if not _bearer_matches(request, expected):
            raise web.HTTPUnauthorized(text="Unauthorized")

    async def propose(request: web.Request) -> web.Response:
        await authorize(request, gateway_token)
        try:
            data = await request.json()
            if not isinstance(data, dict) or set(data) - {"prompt", "untrusted_sources"}:
                raise SecurityError("Unexpected proposal request fields")
            prompt = data.get("prompt")
            sources = data.get("untrusted_sources", [])
            if not isinstance(prompt, str) or not prompt:
                raise SecurityError("prompt must be a non-empty string")
            if not isinstance(sources, list) or len(sources) > 20:
                raise SecurityError("untrusted_sources must be a list of at most 20 items")
            normalized = []
            for item in sources:
                if not isinstance(item, dict) or set(item) != {"source", "content"}:
                    raise SecurityError("Each untrusted source needs source and content")
                if not isinstance(item["source"], str) or not isinstance(item["content"], str):
                    raise SecurityError("Untrusted source fields must be strings")
                if (
                    not item["source"] or len(item["source"]) > 200
                    or not item["content"] or len(item["content"]) > 20000
                ):
                    raise SecurityError("Untrusted source is empty or too large")
                normalized.append((item["source"], item["content"]))
            result = await gateway.propose(prompt, normalized)
            return web.json_response(result)
        except (json.JSONDecodeError, web.HTTPBadRequest):
            raise web.HTTPBadRequest(text="Invalid JSON")
        except SecurityError as exc:
            raise web.HTTPBadRequest(text=str(exc))

    async def approve(request: web.Request) -> web.Response:
        await authorize(request, approval_token)
        try:
            data = await request.json()
            if not isinstance(data, dict) or set(data) != {"action", "action_digest"}:
                raise SecurityError("Approval request must contain action and action_digest")
            action_data = _action_data(data["action"])
            raw = {
                "id": action_data["call_id"],
                "type": "function",
                "function": {
                    "name": action_data["name"],
                    "arguments": json.dumps(action_data["arguments"]),
                },
            }
            action = parse_tool_action(raw)
            if not isinstance(data["action_digest"], str) or not hmac.compare_digest(
                action.digest, data["action_digest"]
            ):
                raise SecurityError("Approval digest does not match reviewed action")
            token = gateway.store.create_approval(action, ttl_seconds=120)
            return web.json_response({"approval_token": token, "expires_in_seconds": 120})
        except (json.JSONDecodeError, web.HTTPBadRequest):
            raise web.HTTPBadRequest(text="Invalid JSON")
        except SecurityError as exc:
            raise web.HTTPBadRequest(text=str(exc))

    async def execute(request: web.Request) -> web.Response:
        await authorize(request, "gateway_token")
        try:
            data = await request.json()
            if not isinstance(data, dict) or set(data) != {"action", "approval_token"}:
                raise SecurityError("Execution request must contain action and approval_token")
            action_data = _action_data(data["action"])
            token = data["approval_token"]
            if not isinstance(token, str) or not token:
                raise SecurityError("approval_token must be a non-empty string")
            result = await gateway.execute_approved(action_data, token)
            return web.json_response(result)
        except (json.JSONDecodeError, web.HTTPBadRequest):
            raise web.HTTPBadRequest(text="Invalid JSON")
        except SecurityError as exc:
            raise web.HTTPForbidden(text=str(exc))
        except Exception:
            raise web.HTTPBadGateway(text="Sandbox execution failed")

    app.router.add_post("/v1/propose", propose)
    app.router.add_post("/v1/approve", approve)
    app.router.add_post("/v1/execute", execute)
    return app


def main() -> None:
    app = create_app()
    host = os.environ.get("MESH_SECURITY_BIND", "127.0.0.1")
    port = int(os.environ.get("MESH_SECURITY_PORT", "8091"))
    web.run_app(app, host=host, port=port)


if __name__ == "__main__":
    main()
