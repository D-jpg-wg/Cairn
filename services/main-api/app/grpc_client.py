import app.grpc_gen  # noqa: F401 — кладёт grpc_gen на sys.path для стабов
import grpc

from search import search_pb2, search_pb2_grpc

from app.core.config import setting

_channel: grpc.aio.Channel | None = None
_stub: search_pb2_grpc.SearchServiceStub | None = None


async def start_search_client() -> None:
    global _channel, _stub
    _channel = grpc.aio.insecure_channel(setting.search_grpc_addr)
    _stub = search_pb2_grpc.SearchServiceStub(_channel)


async def stop_search_client() -> None:
    if _channel is not None:
        await _channel.close()


async def search_entries(owner_id: str, query: str, limit: int = 10) -> list[str]:
    if _stub is None:
        raise RuntimeError("search gRPC client not initialized")
    request = search_pb2.SearchRequest(owner_id=owner_id, query=query, limit=limit)
    response = await _stub.Search(request, timeout=2.0)
    return list(response.entry_ids)
