"""REST client for api.prod.biedronka.cloud v7."""

from __future__ import annotations

import json as json_lib
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from .auth import jwt_payload, refresh_tokens
from .const import ACCEPT_LANGUAGE, API_APP_VERSION, API_BASE
from .exceptions import BiedronkaAuthError, BiedronkaCannotConnect, BiedronkaError

_LOGGER = logging.getLogger(__name__)

SaveTokens = Callable[[dict[str, str]], Awaitable[None]]
SaveAppVersion = Callable[[str], Awaitable[None]]

# Sent with HTTP 426 "Upgrade Required" when the app version is too old.
MIN_VERSION_HEADER = "min-supported-version-android"
_VERSION_IN_TEXT = re.compile(r"(\d+(?:\.\d+)+)")


def version_tuple(version: str | None) -> tuple[int, ...] | None:
    """'2.24.0' -> (2, 24, 0); None for anything that is not a dotted number."""
    if not version or not re.fullmatch(r"\d+(?:\.\d+)*", version.strip()):
        return None
    return tuple(int(part) for part in version.strip().split("."))


def newest_version(*versions: str | None) -> str:
    """The highest valid version, never lower than the built-in one."""
    valid = [v.strip() for v in (API_APP_VERSION, *versions) if version_tuple(v)]
    return max(valid, key=lambda v: version_tuple(v) or ())


def required_version(headers: Any, body: str) -> str | None:
    """Minimum app version from a 426 response: header first, then the message."""
    header = headers.get(MIN_VERSION_HEADER) if headers is not None else None
    if version_tuple(header):
        return header.strip()
    match = _VERSION_IN_TEXT.search(body or "")
    return match.group(1) if match and version_tuple(match.group(1)) else None


def _loads_json(text: str) -> Any:
    """Parse a body as JSON even when the server omits application/json."""
    if not text:
        return None
    try:
        return json_lib.loads(text)
    except json_lib.JSONDecodeError:
        return text


class BiedronkaApi:
    """Thin authenticated JSON client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str,
        refresh_token: str,
        save_tokens: SaveTokens | None = None,
        *,
        app_version: str | None = None,
        save_app_version: SaveAppVersion | None = None,
    ) -> None:
        self._session = session
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._save_tokens = save_tokens
        self._app_version = newest_version(app_version)
        self._save_app_version = save_app_version

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    @property
    def app_version(self) -> str:
        """App version sent as `User-Agent: Android/<version>`."""
        return self._app_version

    async def _upgrade_app_version(self, version: str | None) -> bool:
        """Adopt the version a 426 asked for. False when it would not help."""
        if not version or (version_tuple(version) or ()) <= (
            version_tuple(self._app_version) or ()
        ):
            return False
        _LOGGER.warning(
            "Biedronka API now requires app version %s (was %s); switching to it",
            version,
            self._app_version,
        )
        self._app_version = version
        if self._save_app_version:
            await self._save_app_version(version)
        return True

    async def ensure_fresh_token(self) -> None:
        payload = jwt_payload(self._access_token)
        exp = payload.get("exp")
        if isinstance(exp, (int, float)):
            if exp - 60 > time.time():
                return
        await self._refresh()

    async def _refresh(self) -> None:
        tokens = await refresh_tokens(self._session, self._refresh_token)
        self._access_token = tokens["access_token"]
        self._refresh_token = tokens["refresh_token"]
        if self._save_tokens:
            await self._save_tokens(tokens)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
        force_json: bool = False,
    ) -> Any:
        await self.ensure_fresh_token()
        return await self._request_once(
            method,
            path,
            params=params,
            json=json,
            extra_headers=headers,
            force_json=force_json,
            retry=True,
        )

    async def _request_once(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        json: Any,
        extra_headers: dict[str, str] | None,
        force_json: bool,
        retry: bool,
    ) -> Any:
        url = f"{API_BASE}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "User-Agent": f"Android/{self._app_version}",
            "Accept-Language": ACCEPT_LANGUAGE,
            "Accept": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=json,
                headers=headers,
                allow_redirects=True,
            ) as response:
                if response.status == 401 and retry:
                    await self._refresh()
                    return await self._request_once(
                        method,
                        path,
                        params=params,
                        json=json,
                        extra_headers=extra_headers,
                        force_json=force_json,
                        retry=False,
                    )
                if response.status == 401:
                    raise BiedronkaAuthError("unauthorized")
                if response.status == 426:
                    body = await response.text()
                    if await self._upgrade_app_version(
                        required_version(response.headers, body)
                    ):
                        return await self._request_once(
                            method,
                            path,
                            params=params,
                            json=json,
                            extra_headers=extra_headers,
                            force_json=force_json,
                            retry=retry,
                        )
                    _LOGGER.error("Biedronka API rejected the app version: %s", body[:300])
                    raise BiedronkaError("upgrade_required")
                if response.status == 204:
                    return None
                if response.status >= 400:
                    body = await response.text()
                    _LOGGER.debug("API %s %s: %s", response.method, response.url, body[:500])
                    raise BiedronkaError(f"http_{response.status}")
                if force_json:
                    return _loads_json(await response.text())
                if response.content_type and "json" not in response.content_type:
                    return await response.text()
                return await response.json(content_type=None)
        except TimeoutError as err:
            raise BiedronkaCannotConnect("timeout") from err
        except aiohttp.ClientError as err:
            raise BiedronkaCannotConnect(str(err)) from err

    async def users_me(self, refresh: bool = False) -> dict[str, Any]:
        return await self.request("GET", "users/me/", params={"refresh": str(refresh).lower()})

    async def transactions(self, page: int = 1) -> dict[str, Any]:
        return await self.request("GET", "transactions/", params={"page": page})

    async def transaction_details(self, transaction_id: str) -> dict[str, Any]:
        return await self.request("GET", f"transactions/{transaction_id}/")

    async def e_receipt(self, transaction_id: str, output_format: str = "json") -> Any:
        """Download a fiscal e-receipt; the app uses output-format=json."""
        return await self.request(
            "GET",
            f"transactions/{transaction_id}/e-receipt/",
            headers={"output-format": output_format},
            force_json=True,
        )

    async def dashboard(self) -> Any:
        return await self.request("GET", "dashboards/dashboard/")

    async def carousel(self, carousel_id: str) -> dict[str, Any]:
        return await self.request("GET", f"promos/carousels/{carousel_id}/")

    async def shakeomat_assets(self) -> Any:
        return await self.request("GET", "promos/shakeomats/")

    async def coupons(self) -> dict[str, Any]:
        return await self.request("GET", "promos/coupons/")

    async def loyalty_actions(self) -> Any:
        """Sticker / points campaigns ("Akcja" on the app's home screen)."""
        return await self.request("GET", "loyalty-actions/")

    async def wallets(self) -> Any:
        """Balances of the sticker / points wallets: perspectiv_id + balance."""
        return await self.request("GET", "users/me/wallets/")

    async def reveal_and_activate(self, offer_id: str) -> Any:
        return await self.request("PATCH", f"offers/{offer_id}/reveal-and-activate/")
