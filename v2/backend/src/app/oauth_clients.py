"""CIMD public clients. Bounded HTTPS fetches to explicitly trusted hosts only."""

import asyncio
import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import aiohttp
from aiohttp.resolver import DefaultResolver

from .config import get_settings


class ClientMetadataError(ValueError):
    pass


def parse_url(value: str):
    if not isinstance(value, str) or len(value) > 2048 or re.search(r"[\x00-\x20\x7f\\]", value):
        raise ClientMetadataError("Invalid URL")
    try:
        url = urlsplit(value)
        port = url.port
        if not url.hostname or url.username is not None or url.password is not None or url.fragment:
            raise ValueError()
        if port is not None and not 1 <= port <= 65535:
            raise ValueError()
        return url
    except ValueError as exc:
        raise ClientMetadataError("Invalid URL") from exc


LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def valid_redirect(value: str):
    url = parse_url(value)
    if url.scheme != "https" and not (url.scheme == "http" and url.hostname in LOOPBACK):
        raise ClientMetadataError("Callbacks must use HTTPS or HTTP loopback")
    return url


def redirect_matches(actual: str, registered: str) -> bool:
    try:
        a, r = valid_redirect(actual), valid_redirect(registered)
    except ClientMetadataError:
        return False
    if a.scheme == r.scheme == "http" and r.hostname in LOOPBACK:
        # Native clients choose a fresh listener port. Only that component may
        # vary; host/path/query are still bound to the published callback.
        return (a.hostname, a.path, a.query) == (r.hostname, r.path, r.query)
    return actual == registered


@dataclass(frozen=True)
class Client:
    client_id: str
    client_name: str
    redirect_uris: tuple[str, ...]

    def allows_redirect(self, uri: str) -> bool:
        return any(redirect_matches(uri, registered) for registered in self.redirect_uris)


class PublicResolver(DefaultResolver):
    async def resolve(self, host, port=0, family=socket.AF_INET):
        records = await super().resolve(host, port, family)
        # Validate the actual connector resolution, not a separate DNS preflight.
        if not records or any(not ipaddress.ip_address(r["host"]).is_global for r in records):
            raise OSError("Non-public metadata address")
        return records


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ClientMetadataError("Duplicate metadata field")
        result[key] = value
    return result


async def fetch_metadata(url: str) -> dict:
    """Never forward request cookies/credentials; never follow HTTP redirects."""
    connector = aiohttp.TCPConnector(resolver=PublicResolver(), use_dns_cache=False)
    try:
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=5),
            trust_env=False,
            auto_decompress=False,
        ) as session:
            async with session.get(
                url,
                allow_redirects=False,
                headers={"Accept": "application/json", "Accept-Encoding": "identity"},
            ) as response:
                if response.status != 200 or response.content_type != "application/json":
                    raise ClientMetadataError("Client metadata unavailable")
                body = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    body.extend(chunk)
                    if len(body) > 65536:
                        raise ClientMetadataError("Client metadata too large")
                return json.loads(body, object_pairs_hook=_unique_object)
    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        ValueError,
        RecursionError,
        UnicodeError,
    ) as exc:
        raise ClientMetadataError("Unable to read client metadata") from exc


async def resolve_client(client_id: str) -> Client:
    url = parse_url(client_id)
    try:
        ipaddress.ip_address(url.hostname)
    except ValueError:
        pass
    else:
        # aiohttp does not invoke its resolver for literal IPs.
        raise ClientMetadataError("Client metadata must use a trusted DNS hostname")
    if (
        url.scheme != "https"
        or url.port not in (None, 443)
        or url.hostname not in get_settings().oauth_cimd_hosts
        or not url.path
        or url.path == "/"
        or url.query
    ):
        raise ClientMetadataError("Client metadata host is not enabled")
    data = await fetch_metadata(client_id)
    if not isinstance(data, dict) or data.get("client_id") != client_id:
        raise ClientMetadataError("Client identity does not match its metadata URL")
    name, redirects = data.get("client_name"), data.get("redirect_uris")
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise ClientMetadataError("Invalid client name")
    if not isinstance(redirects, list) or not 1 <= len(redirects) <= 20:
        raise ClientMetadataError("Invalid callback list")
    for redirect in redirects:
        valid_redirect(redirect)
    # OpenAI publishes both fields during its CIMD transition. The plural
    # field is authoritative; the singular field is only a preference then.
    methods = data.get("token_endpoint_auth_methods_supported")
    if methods is None:
        methods = [data.get("token_endpoint_auth_method", "none")]
    if (
        not isinstance(methods, list)
        or not all(isinstance(m, str) for m in methods)
        or "none" not in methods
    ):
        raise ClientMetadataError("Client must support public-client PKCE")
    grants = data.get("grant_types", ["authorization_code"])
    responses = data.get("response_types", ["code"])
    if (
        not isinstance(grants, list)
        or "authorization_code" not in grants
        or not isinstance(responses, list)
        or "code" not in responses
    ):
        raise ClientMetadataError("Client must support authorization codes")
    return Client(client_id, name, tuple(redirects))
