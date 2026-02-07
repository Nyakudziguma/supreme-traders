# weltrade/services.py

import uuid
from decimal import Decimal

from .binance_client import binance_withdraw_usdt_trc20, BinanceAPIError 


class WeltradeWithdrawalError(Exception):
    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


def perform_weltrade_withdrawal(address: str, amount: Decimal):
    """
    Core function to withdraw USDT TRC20 for Weltrade.
    Returns (withdraw_order_id, binance_response) on success.
    Raises WeltradeWithdrawalError on failure.
    """
    withdraw_order_id = f"weltrade-{uuid.uuid4().hex}"
    amount_out = format(amount, "f")

    try:
        resp = binance_withdraw_usdt_trc20(
            address=address,
            amount=amount_out,
            withdraw_order_id=withdraw_order_id,
        )
        return withdraw_order_id, resp

    except BinanceAPIError as e:
        # Wrap so the WhatsApp flow just deals with one error type
        raise WeltradeWithdrawalError(
            "Binance withdrawal failed",
            status_code=getattr(e, "status_code", None),
            payload=getattr(e, "payload", {}),
        )

    except Exception as e:
        raise WeltradeWithdrawalError(str(e))