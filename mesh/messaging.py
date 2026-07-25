#!/usr/bin/env python3
"""
Messaging — NATS client. No fallbacks. No placebos.

If NATS is unavailable, every operation fails explicitly.
"""
import asyncio
from typing import Dict, Any, List, Optional, Callable


class NatsClient:
    """NATS client. Requires running NATS server."""

    def __init__(self, url: str = "nats://localhost:4222"):
        self.url = url
        self._nc = None
        self._connected = False

    async def connect(self):
        import nats
        self._nc = await nats.connect(self.url)
        self._connected = True
        print(f"Connected to NATS at {self.url}")

    async def publish(self, subject: str, payload: Dict[str, Any]):
        if not self._connected:
            raise RuntimeError("NATS not connected. Call connect() first.")
        await self._nc.publish(subject, payload)

    async def subscribe(self, subject: str, handler: Callable):
        if not self._connected:
            raise RuntimeError("NATS not connected. Call connect() first.")
        await self._nc.subscribe(subject, cb=handler)

    async def close(self):
        if self._nc:
            await self._nc.close()
            self._connected = False
