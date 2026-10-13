"""Manual sign-in (pasted app:// redirect) for installs without Supervisor."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.biedronka.const import DOMAIN
from custom_components.biedronka.exceptions import (
    BiedronkaAuthError,
    BiedronkaCannotConnect,
)

TOKENS = {"access_token": "access", "refresh_token": "refresh"}
REDIRECT = (
    "Failed to launch 'app://cma20.biedronka.pl?code=abc.def"
    "&session_state=1' because the scheme does not have a registered handler."
)


@pytest.fixture(autouse=True)
def _custom(enable_custom_integrations):
    return


@pytest.fixture
def no_supervisor():
    with patch(
        "custom_components.biedronka.config_flow.BiedronkaConfigFlow.companion_supervisor_present",
        return_value=False,
    ):
        yield


@pytest.fixture
def exchange():
    with patch(
        "custom_components.biedronka.config_flow.KeycloakLogin.exchange_code",
        new=AsyncMock(return_value=TOKENS),
    ) as mock:
        yield mock


@pytest.fixture
def users_me():
    with (
        patch(
            "custom_components.biedronka.config_flow.BiedronkaApi.users_me",
            new=AsyncMock(return_value={"card_number": "1234", "phone": "48500"}),
        ),
        patch("custom_components.biedronka.async_setup_entry", return_value=True),
    ):
        yield


async def test_without_supervisor_shows_manual_form(hass, no_supervisor):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    url = result["description_placeholders"]["auth_url"]
    assert "client_id=cma20" in url
    assert "code_challenge=" in url


async def test_with_supervisor_offers_menu(hass):
    with patch(
        "custom_components.biedronka.config_flow.BiedronkaConfigFlow.companion_supervisor_present",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["companion", "manual"]


async def test_manual_creates_entry(hass, no_supervisor, exchange, users_me):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"redirect_url": REDIRECT}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Biedronka 1234"
    assert result["data"]["refresh_token"] == "refresh"
    code, verifier = exchange.await_args.args
    assert code == "abc.def"
    assert verifier


async def test_manual_keeps_link_between_attempts(hass, no_supervisor):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    first_url = result["description_placeholders"]["auth_url"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"redirect_url": "  "}
    )
    assert result["errors"] == {"base": "invalid_code"}
    assert result["description_placeholders"]["auth_url"] == first_url


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (BiedronkaAuthError("token_rejected"), "invalid_code"),
        (BiedronkaCannotConnect("timeout"), "cannot_connect"),
    ],
)
async def test_manual_exchange_errors(hass, no_supervisor, error, expected):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "custom_components.biedronka.config_flow.KeycloakLogin.exchange_code",
        new=AsyncMock(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"redirect_url": REDIRECT}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_manual_reauth_updates_entry(hass, no_supervisor, exchange, users_me):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"card_number": "1234", "access_token": "old", "refresh_token": "old"},
        unique_id="1234",
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "manual"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"redirect_url": REDIRECT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["refresh_token"] == "refresh"


async def test_manual_reconfigure_updates_entry(
    hass, no_supervisor, exchange, users_me
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"card_number": "1234", "access_token": "old", "refresh_token": "old"},
        unique_id="1234",
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "manual"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"redirect_url": REDIRECT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["refresh_token"] == "refresh"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reconfigure_rejects_other_card(hass, no_supervisor, exchange, users_me):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"card_number": "9999", "access_token": "old", "refresh_token": "old"},
        unique_id="9999",
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"redirect_url": REDIRECT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data["refresh_token"] == "old"
