"""MCP token management endpoints — create, list, revoke."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import get_current_user_or_api_key
from app.models import McpTokenCreate, McpTokenResponse, User
from app.services import mcp_token_service

router = APIRouter(prefix="/api/settings/mcp-tokens", tags=["settings"])

AuthUser = Annotated[User, Depends(get_current_user_or_api_key)]


@router.post("", response_model=McpTokenResponse)
async def create_token(body: McpTokenCreate, user: AuthUser):
    """Create a new MCP token."""
    return await mcp_token_service.create_token(user.id, body.name)


@router.get("", response_model=list[McpTokenResponse])
async def list_tokens(user: AuthUser):
    """List all MCP tokens for the current user."""
    return await mcp_token_service.list_tokens(user.id)


@router.delete("/{token_id}", status_code=204)
async def revoke_token(token_id: str, user: AuthUser):
    """Revoke an MCP token."""
    await mcp_token_service.revoke_token(user.id, token_id)
