"""Tests for the SPA catch-all: index.html caching and static-file confinement."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.responses import FileResponse, JSONResponse

from app.main import spa_response


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    d = tmp_path / "frontend-dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<html>app</html>")
    (d / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("nope")
    return d


def _served(resp) -> Path | None:
    return Path(resp.path) if isinstance(resp, FileResponse) else None


@pytest.mark.parametrize("path", ["", "jobs", "jobs/abc", "index.html", "./index.html"])
def test_spa_routes_get_uncached_index(dist: Path, path: str):
    resp = spa_response(path, dist)
    assert _served(resp) == (dist / "index.html").resolve()
    assert resp.headers["cache-control"] == "no-cache"


def test_static_file_served(dist: Path):
    resp = spa_response("favicon.svg", dist)
    assert _served(resp) == (dist / "favicon.svg").resolve()
    assert "cache-control" not in resp.headers


@pytest.mark.parametrize(
    "path", ["../secret.txt", "assets/../../secret.txt", "/etc/passwd", "a\x00b", "x" * 5000]
)
def test_paths_outside_dist_fall_back_to_index(dist: Path, path: str):
    resp = spa_response(path, dist)
    assert _served(resp) == (dist / "index.html").resolve()


@pytest.mark.parametrize("path", ["api/nope", "mcp", "mcp/x"])
def test_api_paths_404(dist: Path, path: str):
    resp = spa_response(path, dist)
    assert isinstance(resp, JSONResponse) and resp.status_code == 404
