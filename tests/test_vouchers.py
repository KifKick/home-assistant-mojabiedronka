"""Voucher list from promos/coupons/ and the soonest still-valid expiry."""

from datetime import datetime, timedelta

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.biedronka.const import DOMAIN
from custom_components.biedronka.coordinator import (
    WARSAW,
    BiedronkaCoordinator,
    nearest_expiring_voucher,
)
from custom_components.biedronka.exceptions import BiedronkaError
from custom_components.biedronka.models import Voucher


def _iso(offset_hours: float) -> str:
    return (datetime.now(WARSAW) + timedelta(hours=offset_hours)).isoformat()


def _coupon(**kwargs) -> dict:
    return {
        "meta": kwargs.get("meta", "E-voucher"),
        "number": kwargs.get("number", "ABC"),
        "valid_from": kwargs.get("valid_from", _iso(-2)),
        "valid_to": kwargs.get("valid_to", _iso(48)),
        "status": kwargs.get("status", "READY_TO_USE"),
        "discount_description": kwargs.get(
            "discount_description", {"pl": "Rabat 5 zł", "en": "5 PLN off"}
        ),
        "usage_conditions": kwargs.get(
            "usage_conditions", {"en": "One use", "sk": "Jedno použitie"}
        ),
        "burned_date": kwargs.get("burned_date"),
        "burned_location": kwargs.get("burned_location"),
        "badges": kwargs.get("badges", [{"name": "new", "label": "Nowy"}]),
    }


class VoucherFakeApi:
    """Stand-in that can serve or fail the coupons endpoint."""

    def __init__(self, coupons: dict | None = None, *, fail: bool = False):
        self.coupons_payload = coupons if coupons is not None else {"coupons": []}
        self.fail = fail

    async def users_me(self, refresh: bool = False):
        return {"card_number": "1234", "first_name": "Ala"}

    async def transactions(self, page: int = 1):
        return {"transactions": [], "page_count": 1}

    async def dashboard(self):
        return []

    async def shakeomat_assets(self):
        return []

    async def coupons(self):
        if self.fail:
            raise BiedronkaError("http_500")
        return self.coupons_payload

    async def loyalty_actions(self):
        return []

    async def wallets(self):
        return []


@pytest.fixture
def coordinator_factory(hass):
    def _make(api: VoucherFakeApi) -> BiedronkaCoordinator:
        entry = MockConfigEntry(domain=DOMAIN, data={"card_number": "1234"}, options={})
        entry.add_to_hass(hass)
        return BiedronkaCoordinator(hass, entry, api)

    return _make


async def test_coupons_keep_polish_text_status_and_badges(coordinator_factory):
    later = _iso(72)
    sooner = _iso(24)
    api = VoucherFakeApi(
        {
            "meta": {"kinds": [{"name": "E-voucher"}]},
            "coupons": [
                _coupon(number="LATER", valid_to=later, status="PENDING"),
                _coupon(
                    number="USED",
                    status="BURNED",
                    valid_to=_iso(-1),
                    burned_date=_iso(-2),
                    burned_location="Biedronka 123",
                    badges=[],
                    discount_description={"en": "Used offer", "sk": "Použité"},
                    usage_conditions={"sk": "Len na predajni"},
                ),
                _coupon(number="SOON", valid_to=sooner),
                "not-a-coupon",
            ],
        }
    )
    coordinator = coordinator_factory(api)

    data = await coordinator._async_update_data()

    assert [voucher.number for voucher in data.vouchers] == ["USED", "SOON", "LATER"]
    soon = data.vouchers[1]
    assert soon.as_dict() == {
        "summary": soon.summary,
        "kind": "E-voucher",
        "number": "SOON",
        "status": "READY_TO_USE",
        "valid_from": soon.valid_from,
        "valid_to": sooner,
        "discount": "Rabat 5 zł",
        "conditions": "One use",
        "burned_date": None,
        "burned_location": None,
        "badges": ["Nowy"],
    }
    assert soon.summary.startswith("Voucher: Rabat 5 zł. One use. Ważne ")
    used = data.vouchers[0]
    assert used.status == "BURNED"
    assert used.discount == "Used offer"
    assert used.conditions == "Len na predajni"
    assert used.burned_location == "Biedronka 123"
    assert data.user["card_number"] == "1234"


async def test_empty_coupon_payload_leaves_other_data(coordinator_factory):
    coordinator = coordinator_factory(VoucherFakeApi({}))

    data = await coordinator._async_update_data()

    assert data.vouchers == []
    assert data.user["first_name"] == "Ala"
    assert data.receipts == []


async def test_coupon_error_does_not_fail_the_refresh(coordinator_factory):
    coordinator = coordinator_factory(VoucherFakeApi(fail=True))

    data = await coordinator._async_update_data()

    assert data.vouchers == []
    assert data.user["card_number"] == "1234"


def test_nearest_expiry_skips_inactive_and_past_vouchers():
    now = datetime.now(WARSAW)
    vouchers = [
        Voucher(number="burned", status="BURNED", valid_to=_iso(1)),
        Voucher(number="expired", status="EXPIRED", valid_to=_iso(2)),
        Voucher(number="past", status="READY_TO_USE", valid_to=_iso(-3)),
        Voucher(number="later", status="PENDING", valid_to=_iso(30)),
        Voucher(number="soon", status="READY_TO_USE", valid_to=_iso(5)),
        Voucher(number="open", status="READY_TO_USE", valid_to=None),
    ]

    chosen = nearest_expiring_voucher(vouchers, now)

    assert chosen is not None
    assert chosen.number == "soon"
