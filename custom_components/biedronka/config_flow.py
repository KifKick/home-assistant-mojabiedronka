"""Config flow for Biedronka — Browser Companion or a pasted app:// redirect."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from ha_browser_companion import CompanionLoginFlow, CompanionStart, captured_query
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .api import BiedronkaApi
from .auth import KeycloakLogin, auth_code_from_redirect
from .const import (
    COMPANION_WAIT,
    CONF_ACCESS_TOKEN,
    CONF_AUTO_SHAKEOMAT,
    CONF_CARD_NUMBER,
    CONF_PHONE,
    CONF_REDIRECT_URL,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_AUTO_SHAKEOMAT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .exceptions import BiedronkaAuthError, BiedronkaCannotConnect


class BiedronkaConfigFlow(CompanionLoginFlow, ConfigFlow, domain=DOMAIN):
    """Sign in through Browser Companion or by pasting the app:// redirect."""

    VERSION = 1
    companion_client_id = DOMAIN

    def __init__(self) -> None:
        self._login: KeycloakLogin | None = None
        self._manual_login: KeycloakLogin | None = None
        self._existing_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        # Without Supervisor (HA Container / Core) the add-on cannot exist.
        if not self.companion_supervisor_present():
            return await self.async_step_manual()
        return self.async_show_menu(step_id="user", menu_options=["companion", "manual"])

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Sign in in any browser, then paste the app:// redirect (or its code).

        The PKCE verifier lives in this flow, so the pasted code only works
        with the link shown on this form.
        """
        if self._manual_login is None:
            self._manual_login = KeycloakLogin(async_get_clientsession(self.hass))
        auth_url = self._manual_login.prepare()

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                code = auth_code_from_redirect(user_input[CONF_REDIRECT_URL])
                assert self._manual_login.verifier is not None
                tokens = await self._manual_login.exchange_code(
                    code, self._manual_login.verifier
                )
            except BiedronkaCannotConnect:
                errors["base"] = "cannot_connect"
            except BiedronkaAuthError:
                errors["base"] = "invalid_code"
            else:
                return await self._async_finish(tokens)

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REDIRECT_URL): TextSelector(
                        TextSelectorConfig(multiline=True)
                    )
                }
            ),
            description_placeholders={"auth_url": auth_url},
            errors=errors,
        )

    async def async_companion_start(self) -> CompanionStart:
        if self._login is None:
            self._login = KeycloakLogin.create()
        return CompanionStart(start_url=self._login.prepare(), wait=COMPANION_WAIT)

    async def async_companion_finish(
        self, captured: dict[str, Any]
    ) -> ConfigFlowResult:
        code = captured_query(captured, "code")
        if not code:
            try:
                code = auth_code_from_redirect(str(captured.get("url") or ""))
            except BiedronkaAuthError:
                return await self.async_step_companion_failed()
        if self._login is None or not self._login.verifier:
            return await self.async_step_companion_failed()
        try:
            tokens = await self._login.exchange_code(str(code), self._login.verifier)
            return await self._async_finish(tokens)
        except BiedronkaCannotConnect:
            return self.async_abort(reason="cannot_connect")
        except BiedronkaAuthError:
            return await self.async_step_companion_failed()

    async def async_companion_on_close(self) -> None:
        if self._login is not None:
            await self._login.close()
            self._login = None

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        self._existing_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Sign in again on demand, keeping the entry and its entities."""
        self._existing_entry = self._get_reconfigure_entry()
        return await self.async_step_user()

    async def _async_finish(self, tokens: dict[str, str]) -> ConfigFlowResult:
        session = async_get_clientsession(self.hass)
        api = BiedronkaApi(
            session, tokens[CONF_ACCESS_TOKEN], tokens[CONF_REFRESH_TOKEN]
        )
        try:
            user = await api.users_me()
        except BiedronkaAuthError:
            return self.async_abort(reason="invalid_token")
        except BiedronkaCannotConnect:
            return self.async_abort(reason="cannot_connect")

        phone = str((user or {}).get("phone") or "") or None
        card = str((user or {}).get("card_number") or "unknown")
        await self.async_set_unique_id(card)
        if self._existing_entry:
            if self._existing_entry.unique_id not in (None, card):
                return self.async_abort(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._existing_entry,
                data={
                    CONF_ACCESS_TOKEN: api.access_token,
                    CONF_REFRESH_TOKEN: api.refresh_token,
                    CONF_PHONE: phone,
                    CONF_CARD_NUMBER: card,
                },
            )
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Biedronka {card}",
            data={
                CONF_ACCESS_TOKEN: api.access_token,
                CONF_REFRESH_TOKEN: api.refresh_token,
                CONF_PHONE: phone,
                CONF_CARD_NUMBER: card,
            },
            options={
                CONF_AUTO_SHAKEOMAT: DEFAULT_AUTO_SHAKEOMAT,
                CONF_SCAN_INTERVAL: int(DEFAULT_SCAN_INTERVAL.total_seconds() // 60),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: ConfigEntry) -> OptionsFlow:
        return BiedronkaOptionsFlow()


class BiedronkaOptionsFlow(OptionsFlow):
    """Poll interval and auto Shakeomat."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=int(
                        options.get(
                            CONF_SCAN_INTERVAL,
                            DEFAULT_SCAN_INTERVAL.total_seconds() // 60,
                        )
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=120,
                        step=5,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
                vol.Required(
                    CONF_AUTO_SHAKEOMAT,
                    default=options.get(CONF_AUTO_SHAKEOMAT, DEFAULT_AUTO_SHAKEOMAT),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
