"""Tests for the radarcat config flow.

Zero fields (docs/03-feature-spec.md §3): the single ``user`` step is a
confirmation screen backed by one real ``test_before_configure`` request to
the metadata endpoint, exercised here through the real ``fetch_metadata``
via ``aioresponses`` (mirrors ``tests/test_api.py``'s style) rather than
mocking the function away, so the ``async_get_clientsession(self.hass)``
wiring is actually verified. ``single_config_entry: true`` in the manifest
aborts a second flow before ``async_step_user`` even runs (read live in
``homeassistant/config_entries.py`` - see ``config_flow.py``'s docstring).
"""

from __future__ import annotations

from aioresponses import aioresponses
from custom_components.radarcat.config_flow import TITLE
from custom_components.radarcat.const import DOMAIN, METADATA_URL
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.conftest import load_json_fixture

# ---------------------------------------------------------------------------
# Step 1: the confirmation form
# ---------------------------------------------------------------------------


async def test_user_step_shows_confirmation_form(hass: HomeAssistant) -> None:
    """First call returns the fieldless confirmation form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert result["data_schema"].schema == {}


# ---------------------------------------------------------------------------
# Step 2: a successful test request creates the entry
# ---------------------------------------------------------------------------


async def test_successful_test_request_creates_entry(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """A successful metadata fetch creates the entry with a fixed title/data."""
    mock_http.get(METADATA_URL, payload=load_json_fixture("metadata_sample"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {}


async def test_entry_has_fixed_unique_id(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """The created entry carries the fixed unique_id ``radarcat``."""
    mock_http.get(METADATA_URL, payload=load_json_fixture("metadata_sample"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={}
    )

    entry = hass.config_entries.async_get_entry(result["result"].entry_id)
    assert entry.unique_id == DOMAIN


# ---------------------------------------------------------------------------
# Step 3: a failing test request reports cannot_connect
# ---------------------------------------------------------------------------


async def test_connection_error_reports_cannot_connect(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """A non-200 response maps to ``cannot_connect`` and reshows the form."""
    mock_http.get(METADATA_URL, status=500)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_format_error_reports_cannot_connect(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """An unparseable body also maps to ``cannot_connect``."""
    mock_http.get(METADATA_URL, body="<html>not json</html>", content_type="text/html")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


# ---------------------------------------------------------------------------
# Step 4: single_config_entry aborts a second instance
# ---------------------------------------------------------------------------


async def test_second_instance_is_aborted(hass: HomeAssistant) -> None:
    """A configured instance aborts a new flow before it makes any request.

    ``manifest.json``'s ``single_config_entry: true`` is enforced by
    ``FlowManager.async_init`` itself (read live in
    ``homeassistant/config_entries.py``) with the built-in
    ``single_instance_allowed`` reason, before ``async_step_user`` runs -
    the flow's own ``_abort_if_unique_id_configured()`` is unreachable
    defense-in-depth for the same scenario.
    """
    existing = MockConfigEntry(domain=DOMAIN, data={}, title=TITLE)
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
