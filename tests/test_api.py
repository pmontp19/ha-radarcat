"""Tests for the Meteocat radar widget HTTP client.

No network: ``aioresponses`` intercepts every request made through a real
``aiohttp.ClientSession`` (docs/04-architecture.md §5's inject_websession
rule - this module never creates its own session, so tests must not either).
The happy-path metadata assertion uses ``tests/fixtures/metadata_sample.json``,
real captured data (AGENTS.md evidence discipline).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from aiohttp import ClientError, ClientSession
from aioresponses import aioresponses
from custom_components.radarcat.api import (
    RadarcatConnectionError,
    RadarcatFormatError,
    base_tile_url,
    fetch_metadata,
    fetch_tile,
    radar_tile_url,
)
from custom_components.radarcat.const import (
    BASE_Z,
    FONS_TILES_BASE,
    METADATA_URL,
    RADAR_TILES_BASE,
    RADAR_Z,
)

from tests.conftest import load_fixture, load_json_fixture


@pytest.fixture
async def session() -> AsyncGenerator[ClientSession]:
    """A real ``aiohttp.ClientSession``, the only kind this module accepts."""
    async with ClientSession() as s:
        yield s


# ---------------------------------------------------------------------------
# fetch_metadata: happy path
# ---------------------------------------------------------------------------


async def test_fetch_metadata_happy_path(
    session: ClientSession, mock_http: aioresponses
) -> None:
    """Real captured metadata parses into the exact UTC datetimes it encodes."""
    mock_http.get(METADATA_URL, payload=load_json_fixture("metadata_sample"))

    latest, system = await fetch_metadata(session)

    assert latest == datetime(2026, 8, 17, 11, 54, tzinfo=UTC)
    assert system == datetime(2026, 8, 17, 12, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# fetch_metadata: connection errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [404, 500])
async def test_fetch_metadata_http_error_raises_connection_error(
    session: ClientSession, mock_http: aioresponses, status: int
) -> None:
    """A non-200 status raises RadarcatConnectionError, never returns."""
    mock_http.get(METADATA_URL, status=status)
    with pytest.raises(RadarcatConnectionError):
        await fetch_metadata(session)


async def test_fetch_metadata_timeout_raises_connection_error(
    session: ClientSession, mock_http: aioresponses
) -> None:
    """A request timeout raises RadarcatConnectionError."""
    mock_http.get(METADATA_URL, timeout=True)
    with pytest.raises(RadarcatConnectionError):
        await fetch_metadata(session)


async def test_fetch_metadata_network_failure_raises_connection_error(
    session: ClientSession, mock_http: aioresponses
) -> None:
    """A DNS/connection-refused style failure raises RadarcatConnectionError."""
    mock_http.get(METADATA_URL, exception=ClientError("connection refused"))
    with pytest.raises(RadarcatConnectionError):
        await fetch_metadata(session)


# ---------------------------------------------------------------------------
# fetch_metadata: format errors
# ---------------------------------------------------------------------------


async def test_fetch_metadata_non_json_body_raises_format_error(
    session: ClientSession, mock_http: aioresponses
) -> None:
    """A body that does not decode as JSON raises RadarcatFormatError."""
    mock_http.get(METADATA_URL, body="<html>not json</html>", content_type="text/html")
    with pytest.raises(RadarcatFormatError):
        await fetch_metadata(session)


async def test_fetch_metadata_missing_field_raises_format_error(
    session: ClientSession, mock_http: aioresponses
) -> None:
    """A JSON body missing one of the two expected date fields is a format error."""
    mock_http.get(METADATA_URL, payload={"dataUltimaImatge": "08/17/2026 11:54Z"})
    with pytest.raises(RadarcatFormatError):
        await fetch_metadata(session)


@pytest.mark.parametrize(
    "raw",
    [
        "2026-08-17T11:54:00Z",  # real ISO 8601 - NOT the format this source uses
        "08/17/2026 11:54",  # missing the literal Z
        "not a date",
        123,  # wrong type entirely
    ],
)
async def test_fetch_metadata_unparseable_date_raises_format_error(
    session: ClientSession, mock_http: aioresponses, raw: object
) -> None:
    """Any date that does not match "MM/dd/yyyy HH:mm'Z'" is a format error."""
    mock_http.get(
        METADATA_URL,
        payload={"dataUltimaImatge": raw, "dataSistema": "08/17/2026 12:01Z"},
    )
    with pytest.raises(RadarcatFormatError):
        await fetch_metadata(session)


# ---------------------------------------------------------------------------
# fetch_tile: happy path
# ---------------------------------------------------------------------------


async def test_fetch_tile_happy_path(
    session: ClientSession, mock_http: aioresponses
) -> None:
    """A 200 with a real tile body returns those exact bytes."""
    png = load_fixture("radar_tile_z7_x65_y80_no_echo.png")
    url = radar_tile_url(datetime(2026, 8, 17, 11, 42, tzinfo=UTC), 65, 80)
    mock_http.get(url, body=png, content_type="image/png")

    result = await fetch_tile(session, url)

    assert result == png


# ---------------------------------------------------------------------------
# fetch_tile: missing tile is normal, never an exception
# ---------------------------------------------------------------------------


async def test_fetch_tile_404_returns_none(
    session: ClientSession, mock_http: aioresponses
) -> None:
    """A 404 (expected margin tile) returns None, raises nothing."""
    url = base_tile_url(126, 157)
    mock_http.get(url, status=404)

    result = await fetch_tile(session, url)

    assert result is None


async def test_fetch_tile_empty_body_returns_none(
    session: ClientSession, mock_http: aioresponses
) -> None:
    """A 200 with an empty body is treated the same as a missing tile."""
    url = base_tile_url(128, 160)
    mock_http.get(url, status=200, body=b"")

    result = await fetch_tile(session, url)

    assert result is None


# ---------------------------------------------------------------------------
# fetch_tile: a real connection failure still raises
# ---------------------------------------------------------------------------


async def test_fetch_tile_500_raises_connection_error(
    session: ClientSession, mock_http: aioresponses
) -> None:
    """A 500 (not a clean 404) raises RadarcatConnectionError."""
    url = base_tile_url(128, 160)
    mock_http.get(url, status=500)

    with pytest.raises(RadarcatConnectionError):
        await fetch_tile(session, url)


async def test_fetch_tile_timeout_raises_connection_error(
    session: ClientSession, mock_http: aioresponses
) -> None:
    """A timeout fetching a tile raises RadarcatConnectionError."""
    url = base_tile_url(128, 160)
    mock_http.get(url, timeout=True)

    with pytest.raises(RadarcatConnectionError):
        await fetch_tile(session, url)


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------


def test_radar_tile_url_format() -> None:
    """The radar tile path is UTC and zero-padded (docs/01-data-sources.md §2)."""
    url = radar_tile_url(datetime(2026, 8, 17, 11, 42, tzinfo=UTC), 65, 80)
    assert url == (
        f"{RADAR_TILES_BASE}/2026/08/17/11/42/{RADAR_Z:02d}/000/000/065/000/000/080.png"
    )


def test_base_tile_url_format() -> None:
    """The base tile path carries no timestamp (docs/01-data-sources.md §2)."""
    url = base_tile_url(128, 160)
    assert url == f"{FONS_TILES_BASE}/{BASE_Z:02d}/000/000/128/000/000/160.png"
