"""Opening hours of the store chosen in the app (`store` in users/me/)."""

from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.biedronka.const import DOMAIN
from custom_components.biedronka.models import BiedronkaStore

from .test_setup_entities import FullFakeApi
from .test_shakeomat import _item

WARSAW_TZ = ZoneInfo("Europe/Warsaw")


def _store(today: str, tomorrow: str) -> dict:
    """Shaped like the app's store model (x3c / z3c)."""
    return {
        "code": "Z123",
        "name": "Biedronka",
        "street": "ul. Przykładowa 1",
        "zip_code": "00-001",
        "city": "Warszawa",
        "latitude": 52.0,
        "longitude": 21.0,
        "opening_hours": [
            {"date": today, "opening_time": "00:00:00", "closing_time": "23:59:00", "store_is_closed": False},
            {"date": tomorrow, "opening_time": None, "closing_time": None, "store_is_closed": True},
        ],
        "is_closed_now": False,
        "target_hour": "2026-10-13T21:59:00+02:00",
        "is_in_refurbishment": False,
    }


class StoreApi(FullFakeApi):
    store: dict | None = None

    async def users_me(self, refresh: bool = False):
        return {"card_number": "1234", "first_name": "Ala", "store": self.store}


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"card_number": "1234", "access_token": "access", "refresh_token": "refresh"},
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


async def test_store_hours_and_open_sensor(hass, entry, enable_custom_integrations):
    today = dt_util.now().date()
    api = StoreApi({"c1": [_item("a")]})
    api.store = _store(today.isoformat(), (today + timedelta(days=1)).isoformat())
    await _setup(hass, entry, api)

    hours = hass.states.get("sensor.moja_biedronka_1234_store_opening_hours")
    assert hours.state == "00:00–23:59"
    assert hours.attributes["address"] == "Warszawa, ul. Przykładowa 1"
    assert hours.attributes["days"][1] == {
        "date": (today + timedelta(days=1)).isoformat(),
        "hours": None,
    }
    assert hass.states.get("binary_sensor.moja_biedronka_1234_store_open").state == "on"


async def test_no_store_chosen(hass, entry, enable_custom_integrations):
    await _setup(hass, entry, StoreApi({"c1": [_item("a")]}))
    assert hass.states.get("sensor.moja_biedronka_1234_store_opening_hours").state == "unknown"
    assert hass.states.get("binary_sensor.moja_biedronka_1234_store_open").state == "unknown"


def test_open_at_follows_todays_hours():
    store = BiedronkaStore.from_payload(
        {
            "code": "Z1",
            "opening_hours": [
                {"date": "2026-10-13", "opening_time": "06:00:00", "closing_time": "22:00:00"},
                {"date": "2026-10-18", "store_is_closed": True},
            ],
        }
    )
    noon = datetime(2026, 10, 13, 12, 0, tzinfo=WARSAW_TZ)
    assert store.open_at(noon) is True
    assert store.open_at(noon.replace(hour=23)) is False
    assert store.open_at(datetime(2026, 10, 18, 12, 0, tzinfo=WARSAW_TZ)) is False
    assert store.hours("2026-10-18") is None
