"""Entity set-up and removal of the pre-rework Shakeomat slot entities."""

from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.biedronka.const import DOMAIN

from .test_shakeomat import FakeApi, _item


class FullFakeApi(FakeApi):
    """Adds the non-Shakeomat endpoints touched during a coordinator refresh."""

    async def users_me(self, refresh: bool = False):
        return {"card_number": "1234", "first_name": "Ala"}

    async def transactions(self, page: int = 1):
        return {"transactions": [], "page_count": 1}

    async def transaction_details(self, transaction_id: str):
        return {}

    async def e_receipt(self, transaction_id: str, output_format: str = "json"):
        return {}

    coupons_payload: dict | None = None
    loyalty: list | None = None
    wallets_payload: list | None = None
    notifications_payload: dict | None = None
    history_payload: dict | None = None

    async def coupons(self):
        return self.coupons_payload or {"meta": {"kinds": []}, "coupons": []}

    async def loyalty_actions(self):
        return self.loyalty or []

    async def wallets(self):
        return self.wallets_payload or []

    async def notifications(self):
        return self.notifications_payload or {"notifications": []}

    async def wallet_history(self, wallet_id, end_date, page=1):
        return self.history_payload or {"transactions": []}


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "card_number": "1234",
            "access_token": "access",
            "refresh_token": "refresh",
        },
        options={"auto_shakeomat": False},
        unique_id="1234",
    )
    entry.add_to_hass(hass)
    return entry


async def _setup(hass, entry, api):
    with (
        patch("custom_components.biedronka.BiedronkaApi", return_value=api),
        patch("custom_components.biedronka.async_get_clientsession", return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_entities_are_created(hass, entry, enable_custom_integrations):
    api = FullFakeApi({"c1": [_item("a"), _item("b")]})
    await _setup(hass, entry, api)

    assert hass.states.get("sensor.moja_biedronka_1234_shakeomat").state == "available"
    assert hass.states.get("sensor.moja_biedronka_1234_shakeomats_ready").state == "2"
    assert hass.states.get("sensor.moja_biedronka_1234_recent_receipts").state == "0"
    assert hass.states.get("sensor.moja_biedronka_1234_vouchers").state == "0"
    assert hass.states.get("sensor.moja_biedronka_1234_nearest_voucher_expiry").state == "unknown"
    assert hass.states.get("button.moja_biedronka_1234_reveal_shakeomats") is not None
    assert hass.states.get("sensor.moja_biedronka_1234_shakeomat_1") is None


async def test_legacy_slot_entities_are_removed(
    hass, entry, enable_custom_integrations
):
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        "sensor", DOMAIN, "1234_shakeomat_2", config_entry=entry
    )

    api = FullFakeApi({"c1": [_item("a")]})
    await _setup(hass, entry, api)

    assert registry.async_get(legacy.entity_id) is None


async def test_two_accounts_get_separate_devices(hass, entry, enable_custom_integrations):
    from homeassistant.helpers import device_registry as dr

    second = MockConfigEntry(
        domain=DOMAIN,
        data={
            "card_number": "9900000005678",
            "access_token": "access",
            "refresh_token": "refresh",
        },
        options={"auto_shakeomat": False},
        unique_id="9900000005678",
    )
    second.add_to_hass(hass)
    # Setting up the integration loads every entry of the domain.
    await _setup(hass, entry, FullFakeApi({"c1": [_item("a")]}))
    assert second.state is ConfigEntryState.LOADED

    assert hass.states.get("sensor.moja_biedronka_1234_shakeomat") is not None
    assert hass.states.get("sensor.moja_biedronka_5678_shakeomat") is not None
    names = {device.name for device in dr.async_get(hass).devices.values()}
    assert {"Moja Biedronka 1234", "Moja Biedronka 5678"} <= names


async def test_existing_entity_ids_survive_the_rename(
    hass, entry, enable_custom_integrations
):
    from homeassistant.helpers import entity_registry as er

    er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        "1234_shakeomat",
        config_entry=entry,
        suggested_object_id="moja_biedronka_shakeomat",
    )
    await _setup(hass, entry, FullFakeApi({"c1": [_item("a")]}))

    assert hass.states.get("sensor.moja_biedronka_shakeomat") is not None
    assert hass.states.get("sensor.moja_biedronka_1234_shakeomat") is None


async def test_diagnostics_redact_tokens(hass, entry, enable_custom_integrations):
    from custom_components.biedronka.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    await _setup(hass, entry, FullFakeApi({"c1": [_item("a")]}))
    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["data"]["refresh_token"] == "**REDACTED**"
    assert result["entry"]["data"]["card_number"] == "**REDACTED**"
    assert result["carousels"]["c1"]["items"][0]["offer_id"] == "a"
