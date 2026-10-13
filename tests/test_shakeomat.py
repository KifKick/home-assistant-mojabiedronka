"""Shakeomat discovery, activation and reward history."""

from datetime import datetime, timedelta

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.biedronka.const import DOMAIN
from custom_components.biedronka.coordinator import WARSAW, BiedronkaCoordinator
from custom_components.biedronka.exceptions import BiedronkaError
from custom_components.biedronka.models import (
    STATUS_AVAILABLE,
    STATUS_CLAIMED,
    STATUS_COOLDOWN,
    BiedronkaData,
)


def _iso(offset_hours: float) -> str:
    return (datetime.now(WARSAW) + timedelta(hours=offset_hours)).isoformat()


def _item(offer_id: str, item_type: str = "SHAKEOMAT", **kwargs) -> dict:
    return {
        "type": item_type,
        "offer_id": offer_id,
        "available_from": kwargs.get("available_from", _iso(-1)),
        "available_to": kwargs.get("available_to", _iso(6)),
        "meta": kwargs.get("meta", "assets-1"),
        "offer_type": item_type,
    }


class FakeApi:
    """Minimal stand-in for BiedronkaApi covering the Shakeomat endpoints."""

    def __init__(
        self, carousels: dict[str, list[dict]], assets: list[dict] | None = None
    ):
        self.carousels = carousels
        self.assets = assets or []
        self.activated: list[str] = []
        self.fail_on: set[str] = set()

    async def dashboard(self):
        return {
            "sections": [
                {"type": "CAROUSELS", "param": param, "slug": param}
                for param in self.carousels
            ]
        }

    async def carousel(self, carousel_id: str):
        return {"id": carousel_id, "items": self.carousels[carousel_id]}

    async def shakeomat_assets(self):
        return self.assets

    async def reveal_and_activate(self, offer_id: str):
        self.activated.append(offer_id)
        if offer_id in self.fail_on:
            raise BiedronkaError("http_409")
        return {
            "name": f"Oferta {offer_id}",
            "details": "Limit 1 sztuka",
            "price": "4,99",
            "discount": "-50%",
            "image_url": f"https://example.invalid/{offer_id}.png",
            "start": _iso(0),
            "end": _iso(24),
        }


@pytest.fixture
def coordinator_factory(hass):
    def _make(api: FakeApi) -> BiedronkaCoordinator:
        entry = MockConfigEntry(domain=DOMAIN, data={"card_number": "1234"}, options={})
        entry.add_to_hass(hass)
        return BiedronkaCoordinator(hass, entry, api)

    return _make


async def test_two_offers_of_the_same_type_are_both_kept(coordinator_factory):
    api = FakeApi(
        {
            "c1": [
                _item("second", available_from=_iso(3), available_to=_iso(9)),
                _item("first"),
            ]
        }
    )
    coordinator = coordinator_factory(api)
    await coordinator.async_load_rewards()

    offers = await coordinator._load_shakeomats()

    assert [offer.offer_id for offer in offers] == ["first", "second"]
    assert [offer.status for offer in offers] == [STATUS_AVAILABLE, STATUS_COOLDOWN]


async def test_offers_from_several_carousels_are_deduplicated(coordinator_factory):
    api = FakeApi(
        {
            "c1": [
                _item("a"),
                _item("b", "SHAKEOMARKA"),
                {"type": "ACTION", "id": "x"},
            ],
            "c2": [_item("a"), _item("c", "SHAKEOMAT_2")],
        }
    )
    coordinator = coordinator_factory(api)
    await coordinator.async_load_rewards()

    offers = await coordinator._load_shakeomats()

    assert sorted(offer.offer_id for offer in offers) == ["a", "b", "c"]


async def test_assets_name_is_matched_by_meta(coordinator_factory):
    api = FakeApi(
        {"c1": [_item("a", meta="winter")]},
        assets=[{"id": "winter", "name": "Zimowy Shakeomat"}],
    )
    coordinator = coordinator_factory(api)
    await coordinator.async_load_rewards()

    offers = await coordinator._load_shakeomats()

    assert offers[0].assets_name == "Zimowy Shakeomat"


async def test_claimed_offer_survives_the_next_one_appearing(coordinator_factory):
    api = FakeApi({"c1": [_item("first")]})
    coordinator = coordinator_factory(api)
    await coordinator.async_load_rewards()

    await coordinator.async_activate_shakeomat("first", refresh=False)

    api.carousels["c1"] = [_item("second")]
    offers = await coordinator._load_shakeomats()
    data = BiedronkaData()
    coordinator._apply_shakeomats(data, offers)

    assert [offer.offer_id for offer in offers] == ["second"]
    assert data.last_reward is not None
    assert data.last_reward.offer_id == "first"
    assert [reward.offer_id for reward in data.reward_history] == ["first"]


async def test_already_claimed_offer_is_not_activated_twice(coordinator_factory):
    api = FakeApi({"c1": [_item("first")]})
    coordinator = coordinator_factory(api)
    await coordinator.async_load_rewards()

    await coordinator.async_activate_shakeomat("first", refresh=False)
    offers = await coordinator._load_shakeomats()

    assert offers[0].status == STATUS_CLAIMED

    await coordinator._activate_offers(offers, refresh=False)

    assert api.activated == ["first"]


async def test_activate_all_reveals_every_offer_and_survives_one_failure(
    coordinator_factory,
):
    api = FakeApi({"c1": [_item("a"), _item("b"), _item("c")]})
    api.fail_on = {"b"}
    coordinator = coordinator_factory(api)
    await coordinator.async_load_rewards()

    claimed = await coordinator.async_activate_all(refresh=False)

    assert api.activated == ["a", "b", "c"]
    assert [reward["offer_id"] for reward in claimed] == ["a", "c"]


async def test_rewards_are_restored_from_storage(coordinator_factory, hass):
    api = FakeApi({"c1": [_item("first")]})
    coordinator = coordinator_factory(api)
    await coordinator.async_load_rewards()
    await coordinator.async_activate_shakeomat("first", refresh=False)

    revived = BiedronkaCoordinator(hass, coordinator.entry, api)
    await revived.async_load_rewards()

    offers = await revived._load_shakeomats()

    assert offers[0].status == STATUS_CLAIMED


REVEALED_PRODUCT = {
    "id": "p1",
    "offer_type": "SINGLE_PRODUCT_PROMOTION",
    "from_shakeomat": True,
    "name": "Napój mleczny Müllermilch, 400 g",
    "details": "Limit 4 szt. na kartę Moja Biedronka",
    "description": "shake, angel hair",
    "limit_message_short": "Limit 4 szt.",
    "start": "2026-10-12T22:00:00Z",
    "end": "2026-10-13T21:59:59Z",
    "image_url": "https://example.invalid/p1.webp",
    "price_tag_info": None,
    "unit": "1 l",
    "price": "2.99",
    "unit_price": "7.48",
    "regular_price": "4.79",
    "regular_unit_price": "11.98",
    "omnibus_price": "4.49",
    "discount": 37,
    "discount_to_omnibus_price": 33,
    "product_main_ean_code": "4025500000000",
    "promotion_type": "SHAKEOMAT",
    "badges": [{"name": "card", "label": "Z kartą"}],
    "deposit": None,
    "origin_country": "DE",
}


async def test_reward_keeps_prices_for_notifications(coordinator_factory, hass):
    api = FakeApi({"c1": [_item("first")]})
    api.reveal_and_activate = lambda offer_id: _async(REVEALED_PRODUCT)
    coordinator = coordinator_factory(api)
    await coordinator.async_load_rewards()

    reward = await coordinator.async_activate_shakeomat("first", refresh=False)

    assert reward["price"] == "2.99"
    assert reward["regular_price"] == "4.79"
    assert reward["omnibus_price"] == "4.49"
    assert reward["unit_price"] == "7.48"
    assert reward["unit"] == "1 l"
    assert reward["discount"] == "37"
    assert reward["ean"] == "4025500000000"
    assert reward["badges"] == ["Z kartą"]
    assert reward["summary"] == (
        "Napój mleczny Müllermilch, 400 g: 2,99 zł zamiast 4,79 zł (−37%). "
        "Limit 4 szt. na kartę. Ważne do 13.10 23:59."
    )

    revived = BiedronkaCoordinator(hass, coordinator.entry, api)
    await revived.async_load_rewards()
    restored = revived._rewards["first"].as_dict()
    assert restored == reward


def test_reward_from_old_storage_has_summary():
    from custom_components.biedronka.models import ShakeomatReward

    reward = ShakeomatReward.from_dict(
        {"offer_id": "x", "name": "Kawa", "price": "4,99", "discount": "-50%"}
    )
    assert reward is not None
    assert reward.regular_price is None
    assert reward.badges == []
    assert reward.summary == "Kawa: 4,99 zł (−50%)."


async def _async(value):
    return value


def _revealed(promo_id: str, **overrides) -> dict:
    item = {
        "type": "SINGLE_PRODUCT_PROMOTION",
        "id": promo_id,
        "from_shakeomat": True,
        "name": "Napój gazowany Pepsi Zero, 1,75 l",
        "details": "Limit 6 szt. na kartę Moja Biedronka",
        "price_tag_info": "2+1 GRATIS",
        "price": "4.66",
        "regular_price": "6.99",
        "start": _iso(-1),
        "end": _iso(100),
        "badges": [{"label": "Shakeomarka"}],
    }
    item.update(overrides)
    return item


async def test_offer_revealed_in_app_becomes_a_reward(coordinator_factory):
    api = FakeApi({"c1": [_revealed("pepsi")]})
    coordinator = coordinator_factory(api)
    await coordinator.async_load_rewards()

    assert await coordinator._load_shakeomats() == []

    reward = coordinator._rewards["app_pepsi"]
    assert reward.source == "app"
    assert reward.promo_id == "pepsi"
    assert reward.badges == ["Shakeomarka"]
    assert reward.summary.startswith(
        "Napój gazowany Pepsi Zero, 1,75 l: 2+1 gratis "
        "(4,66 zł/szt. w promocji, regularnie 6,99 zł)."
    )

    await coordinator._load_shakeomats()
    assert list(coordinator._rewards) == ["app_pepsi"]


async def test_revealed_offer_fills_gaps_in_our_reward(coordinator_factory):
    from custom_components.biedronka.models import ShakeomatReward

    end = _iso(10)
    api = FakeApi(
        {
            "c1": [
                _revealed(
                    "milk",
                    name="Napój mleczny Müllermilch, 400 g",
                    price_tag_info="DRUGI 74% TANIEJ",
                    price="2.99",
                    regular_price="4.75",
                    end=end,
                )
            ]
        }
    )
    coordinator = coordinator_factory(api)
    await coordinator.async_load_rewards()
    coordinator._rewards["shake1"] = ShakeomatReward(
        offer_id="shake1",
        name="Napój mleczny Müllermilch, 400 g",
        price="2.99",
        discount="37",
        valid_to=end,
        source=None,
    )

    await coordinator._load_shakeomats()

    assert list(coordinator._rewards) == ["shake1"]
    reward = coordinator._rewards["shake1"]
    assert reward.price_tag_info == "DRUGI 74% TANIEJ"
    assert reward.regular_price == "4.75"
    assert reward.source is None
    assert "drugi 74% taniej (2,99 zł/szt. w promocji, regularnie 4,75 zł)" in (
        reward.summary
    )


async def test_expired_revealed_offer_is_ignored(coordinator_factory):
    api = FakeApi({"c1": [_revealed("old", end=_iso(-1))]})
    coordinator = coordinator_factory(api)
    await coordinator.async_load_rewards()
    await coordinator._load_shakeomats()
    assert coordinator._rewards == {}


def test_summary_for_text_only_deal():
    from custom_components.biedronka.models import ShakeomatReward

    reward = ShakeomatReward(
        offer_id="x",
        name="Passata Gusto Bello, 690 g",
        details="Limit 4 (maks. 2 szt. za 2 zł) na kartę Moja Biedronka",
        price="DRUGI ZA 2 ZŁ",
        price_tag_info="DRUGI ZA 2 ZŁ",
        regular_price="7.55",
        discount="36",
        valid_to="2026-10-13T21:59:59Z",
    )
    assert reward.summary == (
        "Passata Gusto Bello, 690 g: drugi za 2 zł (regularnie 7,55 zł). "
        "Limit 4 (maks. 2 szt. za 2 zł) na kartę. "
        "Ważne do 13.10 23:59."
    )
