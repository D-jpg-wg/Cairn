import app.grpc_gen  # noqa: F401 - кладет grpc_gen на sys.path для стабов
import grpc
from search import search_pb2, search_pb2_grpc
from app.core.config import settings


class SearchService(search_pb2_grpc.SearchServiceServicer):
    async def Search(self, request, context):
        print(
            f"[search] gRPC Search: owner={request.owner_id} "
            f"query={request.query!r} limit={request.limit} ",
            flush=True,
        )
        return search_pb2.SearchResponse(entry_ids=[])


async def serve() -> None:
    server = grpc.aio.server()
    search_pb2_grpc.add_SearchServiceServicer_to_server(SearchService(), server)
    server.add_insecure_port(f"[::]:{settings.grpc_port}")
    await server.start()
    print(f"[search] gRPC сервер слушает :{settings.grpc_port}", flush=True)
    await server.wait_for_termination()
