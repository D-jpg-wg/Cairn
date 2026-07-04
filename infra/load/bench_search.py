"""Прямой бенч gRPC-сервиса search (мимо main-api).

Стабы и grpcio берутся из окружения main-api:

    cd services/main-api && uv run python ../../infra/load/bench_search.py
"""

import asyncio
import os
import sys
import time
import uuid

sys.path.insert(0, os.getcwd())  # app.grpc_gen виден при запуске из services/main-api

import grpc  # noqa: E402

from app.grpc_gen.search import search_pb2, search_pb2_grpc  # noqa: E402

TARGET = os.environ.get("SEARCH_TARGET", "localhost:50051")
CONCURRENCY = 20
DURATION = 10.0


async def worker(
    stub: search_pb2_grpc.SearchServiceStub, deadline: float, lat: list[float]
) -> None:
    owner = str(uuid.uuid4())
    while time.monotonic() < deadline:
        t0 = time.monotonic()
        await stub.Search(
            search_pb2.SearchRequest(owner_id=owner, query="заметка", limit=10),
            timeout=2.0,
        )
        lat.append(time.monotonic() - t0)


async def main() -> None:
    lat: list[float] = []
    async with grpc.aio.insecure_channel(TARGET) as channel:
        stub = search_pb2_grpc.SearchServiceStub(channel)
        deadline = time.monotonic() + DURATION
        await asyncio.gather(*(worker(stub, deadline, lat) for _ in range(CONCURRENCY)))

    lat.sort()
    n = len(lat)
    print(
        f"reqs={n} rps={n / DURATION:.0f} "
        f"p50={lat[n // 2] * 1000:.1f}ms p95={lat[int(n * 0.95)] * 1000:.1f}ms "
        f"max={lat[-1] * 1000:.1f}ms"
    )


if __name__ == "__main__":
    asyncio.run(main())
