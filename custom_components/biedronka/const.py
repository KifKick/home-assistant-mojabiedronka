"""Constants for the unofficial Biedronka integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "biedronka"

API_BASE: Final = "https://api.prod.biedronka.cloud/api/v7"
AUTH_BASE: Final = "https://konto.biedronka.pl"
REALM: Final = "loyalty"
CLIENT_ID: Final = "cma20"
REDIRECT_URI: Final = "app://cma20.biedronka.pl"
COMPANION_WAIT: Final = {
    "event": "http_redirect",
    "status_codes": [302],
    "location_prefixes": [REDIRECT_URI],
}

# Lowest app version known to work. The API reports a newer one with HTTP 426
# and the integration then switches to it on its own (see BiedronkaApi).
API_APP_VERSION: Final = "2.56.0"
API_USER_AGENT: Final = f"Android/{API_APP_VERSION}"
KEYCLOAK_USER_AGENT: Final = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
)
ACCEPT_LANGUAGE: Final = "pl-PL"

CONF_ACCESS_TOKEN: Final = "access_token"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_PHONE: Final = "phone"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_AUTO_SHAKEOMAT: Final = "auto_shakeomat"
CONF_CARD_NUMBER: Final = "card_number"
CONF_REDIRECT_URL: Final = "redirect_url"
CONF_APP_VERSION: Final = "app_version"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)
DEFAULT_AUTO_SHAKEOMAT: Final = False

PLATFORMS: Final = ["sensor", "binary_sensor", "button", "switch", "event"]

SHAKEOMAT_TYPES: Final = ("SHAKEOMAT", "SHAKEOMAT_2", "SHAKEOMARKA")
MAX_REWARD_HISTORY: Final = 20
MAX_RECEIPTS: Final = 5
STORAGE_VERSION: Final = 1
ATTRIBUTION: Final = "Dane z nieoficjalnego API Moja Biedronka"
