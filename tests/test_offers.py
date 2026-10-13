"""Shakeomarka, "Tylko dla Ciebie" card offers and new-offer events."""

from unittest.mock import patch

import pytest
from homeassistant.const import STATE_UNKNOWN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.biedronka.const import DOMAIN
from custom_components.biedronka.models import ShakeomatReward

from .test_setup_entities import FullFakeApi
from .test_shakeomat import _iso, _item

J4U = "j4u-carousel"
OTHER = "promo-carousel"


def _promo(promo_id: str, **overrides) -> dict:
    """Shaped like the real "Tylko dla Ciebie" items from the dashboard."""
    item = {
        "type": "SINGLE_PRODUCT_PROMOTION",
        "offer_type": "WELCOME",
        "id": promo_id,
        "from_shakeomat": False,
        "name": "Śmietanka UHT 30% Łaciata, 0,5 l",
        "details": None,
        "limit_message": "Limit 4 (maks. 2 szt. za 5 zł) na kartę Moja Biedronka",
        "start": _iso(-24),
        "end": _iso(100),
        "price_tag_info": "DRUGI ZA 5 ZŁ",
        "price": "",
        "regular_price": "9.99",
        "discount": 24,
        "badges": [{"label": "z kartą Moja Biedronka"}],
    }
    item.update(overrides)
    return item


class OffersApi(FullFakeApi):
    """Carousels carry a `type`, like the real API ("j4u" = Tylko dla Ciebie)."""

    async def carousel(self, carousel_id: str):
        kind = "j4u" if carousel_id == J4U else "standard"
        return {"id": carousel_id, "type": kind, "items": self.carousels[carousel_id]}


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"card_number": "1234", "access_token": "a", "refresh_token": "r"},
        options={"auto_shakeomat": False},
        unique_id="1234",
    )
    entry.add_to_hass(hass)
    return entry


def _patched(api):
    return (
        patch("custom_components.biedronka.BiedronkaApi", return_value=api),
        patch("custom_components.biedronka.async_get_clientsession", return_value=None),
    )


async def _setup(hass, entry, api):
    first, second = _patched(api)
    with first, second:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def _refresh(hass, entry):
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_card_offers_come_only_from_tylko_dla_ciebie(
    hass, entry, enable_custom_integrations
):
    api = OffersApi(
        {J4U: [_promo("cream")], OTHER: [_promo("general", name="Masło")]}
    )
    await _setup(hass, entry, api)

    state = hass.states.get("sensor.moja_biedronka_1234_card_offers")
    assert state.state == "1"
    [offer] = state.attributes["offers"]
    assert offer["name"] == "Śmietanka UHT 30% Łaciata, 0,5 l"
    assert offer["kind"] == "card"
    assert offer["price"] is None
    assert offer["summary"].startswith(
        "Śmietanka UHT 30% Łaciata, 0,5 l: drugi za 5 zł (regularnie 9,99 zł). "
        "Limit 4 (maks. 2 szt. za 5 zł) na kartę. Ważne "
    )


async def test_shakeomarka_has_its_own_entities(
    hass, entry, enable_custom_integrations
):
    api = OffersApi(
        {
            J4U: [
                _item("marka", item_type="SHAKEOMARKA"),
                _promo(
                    "pepsi",
                    offer_type="SHAKEOMARKA",
                    from_shakeomat=True,
                    name="Pepsi Zero, 1,75 l",
                ),
                _promo(
                    "milk",
                    offer_type="SHAKEOMAT",
                    from_shakeomat=True,
                    name="Müllermilch, 400 g",
                ),
            ]
        }
    )
    await _setup(hass, entry, api)

    marka = hass.states.get("sensor.moja_biedronka_1234_shakeomarka")
    assert marka.state == "available"
    assert [o["offer_id"] for o in marka.attributes["offers"]] == ["marka"]
    assert hass.states.get("sensor.moja_biedronka_1234_shakeomat").state == "none"

    last_marka = hass.states.get("sensor.moja_biedronka_1234_last_shakeomarka_offer")
    assert last_marka.state == "Pepsi Zero, 1,75 l"
    last_shake = hass.states.get("sensor.moja_biedronka_1234_last_shakeomat_offer")
    assert last_shake.state == "Müllermilch, 400 g"
    assert hass.states.get("sensor.moja_biedronka_1234_card_offers").state == "0"


async def test_events_fire_once_per_new_offer_but_not_on_first_run(
    hass, entry, enable_custom_integrations
):
    api = OffersApi({J4U: [_promo("cream")]})
    await _setup(hass, entry, api)

    card_event = "event.moja_biedronka_1234_new_card_offer"
    marka_event = "event.moja_biedronka_1234_new_shakeomarka_offer"
    assert hass.states.get(card_event).state == STATE_UNKNOWN

    api.carousels[J4U] = [
        _promo("cream"),
        _promo("coffee", name="Kawa mielona, 500 g"),
        _promo(
            "pepsi",
            offer_type="SHAKEOMARKA",
            from_shakeomat=True,
            name="Pepsi Zero, 1,75 l",
        ),
    ]
    await _refresh(hass, entry)

    card = hass.states.get(card_event)
    assert card.state != STATE_UNKNOWN
    assert card.attributes["event_type"] == "new_offer"
    assert card.attributes["name"] == "Kawa mielona, 500 g"
    assert card.attributes["summary"].startswith("Kawa mielona, 500 g: drugi za 5 zł")
    assert hass.states.get(marka_event).attributes["name"] == "Pepsi Zero, 1,75 l"

    fired_at = card.state
    await _refresh(hass, entry)
    assert hass.states.get(card_event).state == fired_at


async def test_announced_offers_survive_a_restart(
    hass, entry, enable_custom_integrations
):
    api = OffersApi({J4U: [_promo("cream")]})
    await _setup(hass, entry, api)
    first, second = _patched(api)
    with first, second:
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("event.moja_biedronka_1234_new_card_offer").state == (
        STATE_UNKNOWN
    )


def test_summary_uses_price_note_and_date_range():
    reward = ShakeomatReward(
        offer_id="x",
        name="Napój mleczny Müllermilch, 400 g",
        details="Limit 4 szt. na kartę Moja Biedronka",
        price="2.99",
        price_tag_info="DRUGI 74% TANIEJ",
        price_tag_note="KAŻDA Z 2 SZTUK",
        regular_price="4.79",
        valid_from="2026-10-11T22:00:00Z",
        valid_to="2026-10-17T21:59:59Z",
    )
    assert reward.summary == (
        "Napój mleczny Müllermilch, 400 g: drugi 74% taniej "
        "(2,99 zł każda z 2 sztuk, regularnie 4,79 zł). "
        "Limit 4 szt. na kartę. Ważne 12.10–17.10."
    )


STICKERS = {
    # Trimmed from the real loyalty-actions/ payload.
    "id": "a1b2c3d4-0000-4000-8000-000000000001",
    "name": "Gang_Zaradniaków_Ongoing",
    "status": "ongoing",
    "type": "carrier",
    "publication_end_date": "2026-11-14T22:59:59Z",
    "end_on": "2026-11-28T22:59:59Z",
    "page_headline": "Szczegóły",
    "popup_headline": "Gang Zaradniaków",
    "widget_secondarytext": "Sprawdź liczbę zebranych naklejek i wymieniaj je na nagrody!",
    "wallet_first": "Wallet100",
    "award1_stickers_value": 10,
    "award2_stickers_value": 20,
    "award3_stickers_value": 30,
    "popup_electronic_carrier_badge1": "Książka za darmo",
    "popup_electronic_carrier_badge2": "Zaradniak Breloczek ze zniżką za 19,99 zł",
    "popup_electronic_carrier_badge3": "Zaradniak Maskotka ze zniżką za 24,99 zł",
    "award_regular_price_1": "14,99",
    "award_regular_price_2": "39,99",
    "award_regular_price_3": "49,99",
}


async def test_loyalty_action_with_wallet_balance(
    hass, entry, enable_custom_integrations
):
    api = OffersApi({J4U: []})
    api.loyalty = [STICKERS, {**STICKERS, "id": "old", "status": "finished"}]
    api.wallets_payload = [
        {"perspectiv_id": "Wallet100", "balance": 12},
        {"perspectiv_id": "kropki", "balance": 0},
    ]
    await _setup(hass, entry, api)

    actions = hass.states.get("sensor.moja_biedronka_1234_loyalty_actions")
    assert actions.state == "1"
    assert len(actions.attributes["actions"]) == 2
    balance = hass.states.get("sensor.moja_biedronka_1234_loyalty_balance")
    assert balance.state == "12.0"
    assert balance.attributes["action"] == "Gang Zaradniaków"
    assert balance.attributes["unit"] == "naklejki"
    assert balance.attributes["available_rewards"] == 1
    assert balance.attributes["next_reward"]["title"] == (
        "Zaradniak Breloczek ze zniżką za 19,99 zł"
    )
    assert balance.attributes["missing_to_next_reward"] == 8
    assert [r["cost"] for r in balance.attributes["rewards"]] == [10, 20, 30]


async def test_new_voucher_and_loyalty_action_events(
    hass, entry, enable_custom_integrations
):
    api = OffersApi({J4U: []})
    await _setup(hass, entry, api)

    api.coupons_payload = {
        "coupons": [
            {
                "number": "V1",
                "status": "READY_TO_USE",
                "meta": "E-voucher",
                "discount_description": {"pl": "-10 zł"},
                "usage_conditions": {"pl": "Przy zakupach za min. 50 zł"},
                "valid_from": _iso(-1),
                "valid_to": _iso(72),
            },
            {"number": "OLD", "status": "BURNED", "valid_to": _iso(72)},
        ]
    }
    api.loyalty = [STICKERS]
    await _refresh(hass, entry)

    voucher = hass.states.get("event.moja_biedronka_1234_new_voucher")
    assert voucher.attributes["number"] == "V1"
    assert voucher.attributes["summary"].startswith(
        "Voucher: -10 zł. Przy zakupach za min. 50 zł. Ważne "
    )
    action = hass.states.get("event.moja_biedronka_1234_new_loyalty_action")
    assert action.attributes["summary"] == (
        "Nowa akcja: Gang Zaradniaków. Sprawdź liczbę zebranych naklejek i "
        "wymieniaj je na nagrody! Zbieranie do 14.11, odbiór nagród do 28.11."
    )


async def test_offer_that_appeared_during_a_restart_is_announced(
    hass, entry, enable_custom_integrations
):
    api = OffersApi({J4U: [_promo("cream")]})
    await _setup(hass, entry, api)

    api.carousels[J4U] = [_promo("cream"), _promo("coffee", name="Kawa, 500 g")]
    first, second = _patched(api)
    with first, second:
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    card = hass.states.get("event.moja_biedronka_1234_new_card_offer")
    assert card.attributes["name"] == "Kawa, 500 g"
