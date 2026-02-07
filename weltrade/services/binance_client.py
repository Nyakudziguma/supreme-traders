import time
import hmac
import hashlib
import random
from urllib.parse import urlencode
import requests
from django.utils import timezone
from ..models import BinanceSettings


# ============================
# BINANCE CONFIG
# ============================

BINANCE_BASE_URL = "https://api.binance.com"

# ============================
# ERRORS
# ============================

class BinanceAPIError(Exception):
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"Binance API error ({status_code}): {payload}")

# ============================
# HELPERS
# ============================

def get_random_binance_credentials():
    """
    Select a random active Binance API account from DB.
    """
    accounts = BinanceSettings.objects.filter(is_active=True)

    if not accounts.exists():
        raise Exception("No active Binance API accounts found")

    account = random.choice(list(accounts))
    account.last_used_at = timezone.now()
    account.save(update_fields=["last_used_at"])

    return account.api_key, account.api_secret


def _sign_params(params: dict, api_secret: str) -> str:
    """
    Sign Binance params using HMAC SHA256.
    """
    query = urlencode(params)
    signature = hmac.new(
        api_secret.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{query}&signature={signature}"

# ============================
# MAIN BINANCE METHODS
# ============================

def binance_withdraw_usdt_trc20(*, address: str, amount: str, withdraw_order_id: str) -> dict:
    """
    Withdraw USDT via TRC20 using a random Binance account from DB.
    """
    api_key, api_secret = get_random_binance_credentials()
    ts = int(time.time() * 1000)

    params = {
        "coin": "USDT",
        "network": "TRX",
        "address": address,
        "amount": amount,
        "withdrawOrderId": withdraw_order_id,
        "timestamp": ts,
    }

    signed_query = _sign_params(params, api_secret)
    url = f"{BINANCE_BASE_URL}/sapi/v1/capital/withdraw/apply?{signed_query}"

    headers = {
        "X-MBX-APIKEY": api_key,
    }

    response = requests.post(url, headers=headers, timeout=30)

    try:
        data = response.json()
    except Exception:
        raise BinanceAPIError(response.status_code, {"error": "Non-JSON response", "text": response.text})

    if response.status_code != 200:
        raise BinanceAPIError(response.status_code, data)

    if isinstance(data, dict) and ("code" in data and data.get("code") not in (0, None)):
        raise BinanceAPIError(response.status_code, data)

    return data

# ============================
# FAILOVER SAFE WRAPPER
# ============================

def safe_binance_withdraw_usdt_trc20(*, address: str, amount: str, withdraw_order_id: str):
    """
    Try withdrawal using all active accounts until one succeeds.
    """
    accounts = list(BinanceSettings.objects.filter(is_active=True))

    if not accounts:
        raise Exception("No active Binance accounts available")

    for account in accounts:
        try:
            ts = int(time.time() * 1000)

            params = {
                "coin": "USDT",
                "network": "TRX",
                "address": address,
                "amount": amount,
                "withdrawOrderId": withdraw_order_id,
                "timestamp": ts,
            }

            signed_query = _sign_params(params, account.api_secret)
            url = f"{BINANCE_BASE_URL}/sapi/v1/capital/withdraw/apply?{signed_query}"

            headers = {
                "X-MBX-APIKEY": account.api_key,
            }

            response = requests.post(url, headers=headers, timeout=30)
            data = response.json()

            if response.status_code == 200 and not ("code" in data and data.get("code")):
                account.last_used_at = timezone.now()
                account.save(update_fields=["last_used_at"])
                return data

        except Exception:
            continue

    raise Exception("All Binance accounts failed to process withdrawal")
