"""Config flow for the radarcat integration.

Single step, zero fields (docs/03-feature-spec.md §3): the radar covers all
of Catalonia, so there is nothing per-user to pick, unlike the sibling repos
that resolve a location/radius. Submitting the confirmation makes one test
request to the metadata endpoint (rule: ``test_before_configure``) before
creating the entry. ``single_config_entry: true`` in the manifest already
aborts a second flow before ``async_step_user`` even runs (with the built-in
``single_instance_allowed`` reason); ``_abort_if_unique_id_configured()``
below is the same defense-in-depth the sibling flows use in case that flag
is ever bypassed.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RadarcatConnectionError, RadarcatFormatError, fetch_metadata
from .const import DOMAIN

__all__ = ["RadarcatConfigFlow"]

TITLE = "RadarCat"


class RadarcatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for radarcat."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the confirmation screen and verify the endpoint on submit.

        ``fetch_metadata`` deciding between creating the entry (any
        successful response) and reporting ``cannot_connect`` (network,
        timeout or an unparseable body) is the whole of this flow's logic.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                await fetch_metadata(session)
            except (RadarcatConnectionError, RadarcatFormatError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=TITLE, data={})

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({}), errors=errors
        )
