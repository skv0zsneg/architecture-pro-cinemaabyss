import logging
import random
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from .config import Settings

logger = logging.getLogger("uvicorn.error")
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def forwarded_headers(headers: httpx.Headers) -> list[tuple[bytes, bytes]]:
    excluded = HOP_BY_HOP | {"host", "content-length"}
    excluded.update(value.strip().lower() for value in headers.get("connection", "").split(","))
    return [(name, value) for name, value in headers.raw if name.decode().lower() not in excluded]


def select_upstream(path: str, settings: Settings) -> tuple[str, str]:
    if path == "/api/events" or path.startswith("/api/events/"):
        return "events-service", settings.events_service_url
    if path == "/api/movies/health":
        return "movies-service", settings.movies_service_url
    if (path == "/api/movies" or path.startswith("/api/movies/")) and (
        not settings.gradual_migration
        or random.randrange(100) < settings.movies_migration_percent
    ):
        return "movies-service", settings.movies_service_url
    return "monolith", settings.monolith_url


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(timeout=settings.upstream_timeout) as client:
            app.state.client = client
            yield

    app = FastAPI(title="CinemaAbyss Proxy", lifespan=lifespan)

    @app.get("/health", response_class=PlainTextResponse)
    async def health():
        return "Strangler Fig Proxy is healthy"

    @app.api_route(
        "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    )
    async def proxy(request: Request, path: str):
        service, base_url = select_upstream("/" + path, settings)
        url = httpx.URL(base_url.rstrip("/") + request.scope["raw_path"].decode("ascii"))
        url = url.copy_with(query=request.scope["query_string"])
        headers = forwarded_headers(httpx.Headers(request.headers.raw))
        outgoing = httpx.Request(request.method, url, headers=headers, content=await request.body())
        try:
            upstream = await app.state.client.send(outgoing)
        except httpx.TimeoutException:
            return JSONResponse({"error": "Upstream timed out"}, status_code=504)
        except httpx.RequestError:
            return JSONResponse({"error": "Upstream unavailable"}, status_code=502)
        logger.info(
            "%s %s -> %s status=%s", request.method, request.url.path, service, upstream.status_code
        )
        response = Response(content=upstream.content, status_code=upstream.status_code)
        response.raw_headers.extend(
            (name, value)
            for name, value in forwarded_headers(upstream.headers)
            if name.decode().lower() != "content-encoding"
        )
        response.headers["X-Upstream-Service"] = service
        return response

    return app


app = create_app()
