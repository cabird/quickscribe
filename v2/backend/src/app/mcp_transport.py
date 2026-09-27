"""Stateless Streamable HTTP: every tool request carries its own identity.

QuickScribe has request/response tools and no server-push subscriptions. Avoid
stateful transport sessions (and cross-user session-ID ownership) entirely.
FastAPI-MCP still generates and executes the existing REST-backed tools.
"""

from fastapi import Request
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.responses import Response


class MCPResponse(Response):
    def __init__(self, manager: StreamableHTTPSessionManager):
        super().__init__()
        self.manager = manager

    async def __call__(self, scope, receive, send):
        # The SDK's stateless handler only terminates its transport after a
        # successful response. Own its task group for this request so send
        # failures and cancellations also close every spawned server task.
        async with self.manager.run():
            await self.manager.handle_request(scope, receive, send)


def mount_stateless(server, router, transport, mount_path, dependencies):
    def create_manager():
        return StreamableHTTPSessionManager(
            app=transport.mcp_server,
            stateless=True,
            json_response=True,
            security_settings=transport.security_settings,
        )

    @router.api_route(
        mount_path,
        methods=["GET", "POST", "DELETE"],
        include_in_schema=False,
        operation_id="mcp_http",
        dependencies=dependencies,
    )
    async def handle_mcp(request: Request):
        # QuickScribe has no server-push notifications or transport sessions.
        # Do not leave a standalone SSE GET open indefinitely.
        if request.method != "POST":
            return Response(status_code=405, headers={"Allow": "POST"})
        return MCPResponse(create_manager())
