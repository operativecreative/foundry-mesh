#!/usr/bin/env python3
"""
Mesh HTTP server — exposes workflow execution via REST API.

Endpoints:
  POST /workflow — submit and execute a workflow
  GET  /workflow/{id} — get workflow status
  GET  /health — health check
  GET  /metrics — execution metrics
"""
import asyncio
import json
from typing import Dict, Any
from datetime import datetime, timezone

from mesh.engine import WorkflowEngine, EngineConfig
from mesh.types import Workflow, DagNode, NodeType, TaskResult, TaskStatus


class MeshServer:
    def __init__(self, host="0.0.0.0", port=8080):
        self.host = host
        self.port = port
        self.engine = WorkflowEngine(EngineConfig(
            checkpoint_interval=2,
            repair_max_retries=2,
            default_model="openai_fast",
        ))
        self.workflows: Dict[str, Any] = {}

    async def handle_request(self, reader, writer):
        """Simple HTTP request handler."""
        try:
            data = await reader.read(65536)
            if not data:
                return

            request = data.decode("utf-8")
            lines = request.split("\r\n")
            if not lines:
                return

            request_line = lines[0]
            parts = request_line.split()
            if len(parts) < 2:
                await self._send_response(writer, 400, {"error": "Bad request"})
                return

            method, path = parts[0], parts[1]

            # Parse body
            body = ""
            if "\r\n\r\n" in request:
                body = request.split("\r\n\r\n", 1)[1]

            if path == "/health" and method == "GET":
                await self._send_response(writer, 200, {
                    "status": "healthy",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            elif path == "/workflow" and method == "POST":
                try:
                    payload = json.loads(body) if body else {}
                    workflow_id = payload.get("id", "default")

                    # Build workflow from payload
                    nodes = {}
                    for node_def in payload.get("nodes", []):
                        async def make_fn(node_id, prompt):
                            async def fn():
                                return await self.engine.router.generate(prompt)
                            return fn

                        fn = await make_fn(node_def["id"], node_def.get("prompt", ""))
                        nodes[node_def["id"]] = DagNode(
                            id=node_def["id"],
                            node_type=NodeType.TASK,
                            fn=fn,
                            dependencies=node_def.get("dependencies", []),
                        )

                    workflow = Workflow(
                        id=workflow_id,
                        name=payload.get("name", "unnamed"),
                        nodes=nodes,
                    )

                    summary = await self.engine.run(workflow)
                    self.workflows[workflow_id] = summary

                    await self._send_response(writer, 200, summary)

                except Exception as e:
                    await self._send_response(writer, 500, {"error": str(e)})

            elif path.startswith("/workflow/") and method == "GET":
                workflow_id = path.split("/")[-1]
                if workflow_id in self.workflows:
                    await self._send_response(writer, 200, self.workflows[workflow_id])
                else:
                    await self._send_response(writer, 404, {"error": "Workflow not found"})

            elif path == "/metrics" and method == "GET":
                await self._send_response(writer, 200, {
                    "workflows_executed": len(self.workflows),
                    "repair_stats": self.engine.get_repair_stats(),
                    "router_log": self.engine.get_router_log(),
                })

            else:
                await self._send_response(writer, 404, {"error": "Not found"})

        except Exception as e:
            await self._send_response(writer, 500, {"error": str(e)})
        finally:
            await writer.drain()
            writer.close()

    async def _send_response(self, writer, status: int, data: Dict[str, Any]):
        body = json.dumps(data).encode()
        headers = (
            f"HTTP/1.1 {status} OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode()
        writer.write(headers + body)
        await writer.drain()

    async def start(self):
        server = await asyncio.start_server(self.handle_request, self.host, self.port)
        print(f"Mesh server listening on http://{self.host}:{self.port}")
        async with server:
            await server.serve_forever()


async def main():
    server = MeshServer()
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
