"""Python 3.14-compatible synchronous facade over HTTPX2 ASGI transport."""

import asyncio
from typing import Any

import httpx2


class ASGITestClient:
    """Run individual ASGI requests without AnyIO's blocking portal."""

    def __init__(self, app: object) -> None:
        self.app = app

    def __enter__(self) -> "ASGITestClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def request(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        async def send() -> httpx2.Response:
            transport = httpx2.ASGITransport(app=self.app)
            async with httpx2.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(send())

    def get(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("POST", url, **kwargs)
