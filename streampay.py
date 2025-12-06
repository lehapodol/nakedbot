import binascii
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx
from nacl.bindings import crypto_sign, crypto_sign_BYTES
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from config import (
    API_BASE_URL,
    STREAMPAY_PRIVATE_KEY_HEX,
    STREAMPAY_PUBLIC_KEY_HEX,
    STREAMPAY_STORE_ID,
)

logger = logging.getLogger(__name__)

PRIVATE_KEY = binascii.unhexlify(STREAMPAY_PRIVATE_KEY_HEX) if STREAMPAY_PRIVATE_KEY_HEX else None
PUBLIC_KEY: Optional[VerifyKey] = (
    VerifyKey(binascii.unhexlify(STREAMPAY_PUBLIC_KEY_HEX)) if STREAMPAY_PUBLIC_KEY_HEX else None
)


async def streampay_get_currencies():
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        resp = await client.get("/api/payment/currencies")
    if resp.status_code == 200:
        return resp.json().get("data", [])
    elif resp.status_code == 406:
        raise Exception("No available currencies")
    elif resp.status_code == 500:
        raise Exception("Internal server error")
    raise Exception(f"Unexpected status code: {resp.status_code}, body={resp.text}")


def _ensure_keys():
    if not PRIVATE_KEY or not STREAMPAY_STORE_ID:
        raise ValueError("Streampay keys or store id are not configured")
    if not PUBLIC_KEY:
        raise ValueError("Streampay public key is not configured")


def _build_signature(content: bytes) -> bytes:
    _ensure_keys()
    signature = binascii.hexlify(crypto_sign(content, PRIVATE_KEY)[:crypto_sign_BYTES])
    return signature


async def streampay_create_payment(
    external_id: str,
    customer: str,
    description: str,
    system_currency: str,
    amount: float,
    payment_type: int = 2,
) -> Dict[str, Any]:
    req_content = json.dumps(
        dict(
            store_id=STREAMPAY_STORE_ID,
            customer=customer,
            external_id=external_id,
            description=description,
            system_currency=system_currency,
            payment_type=payment_type,
            amount=amount,
        )
    )

    timestamp = bytes(datetime.utcnow().strftime("%Y%m%d:%H%M"), "ascii")
    to_sign = req_content.encode("utf-8") + timestamp
    signature = _build_signature(to_sign)

    headers = {"Content-Type": "application/json", "Signature": signature}

    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        resp = await client.post("/api/payment/create", content=req_content, headers=headers)

    if resp.status_code == 200:
        resp_data = resp.json().get("data", {})
        invoice_id = resp_data.get("invoice") or resp_data.get("id") or resp_data.get("invoice_id")
        pay_url = (
            resp_data.get("pay_url")
            or resp_data.get("payment_url")
            or resp_data.get("pay_link")
            or resp_data.get("payment_link")
        )
        return {"invoice_id": invoice_id, "pay_url": pay_url, "raw": resp_data}
    elif resp.status_code == 403:
        raise Exception("Invalid signature")
    elif resp.status_code == 406:
        raise Exception("Invalid request data")
    elif resp.status_code == 500:
        raise Exception("Internal server error")
    raise Exception(f"Unexpected status code: {resp.status_code}, body={resp.text}")


async def streampay_get_invoice(invoice_id: str) -> dict:
    query_params = {"id": invoice_id}
    req_content = f"id={query_params['id']}"

    timestamp = bytes(datetime.utcnow().strftime("%Y%m%d:%H%M"), "ascii")
    to_sign = req_content.encode("utf-8") + timestamp
    signature = _build_signature(to_sign)
    headers = {"Signature": signature}

    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        resp = await client.get("/api/public/invoice", headers=headers, params=query_params)

    if resp.status_code == 200:
        return resp.json().get("data", {})
    elif resp.status_code == 403:
        raise Exception("Invalid signature")
    elif resp.status_code == 406:
        raise Exception("Invalid request data")
    elif resp.status_code == 500:
        raise Exception("Internal server error")
    raise Exception(f"Unexpected status code: {resp.status_code}, body={resp.text}")


async def streampay_cancel_invoice(invoice_id: str):
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        resp = await client.post(
            "/api/payment/action",
            headers={"Content-Type": "application/json"},
            json={"invoice": invoice_id, "action_type": "cancel"},
        )

    if resp.status_code == 200:
        return True
    elif resp.status_code == 406:
        raise Exception("Operation unavailable")
    elif resp.status_code == 500:
        raise Exception("Internal server error")
    raise Exception(f"Unexpected status code: {resp.status_code}, body={resp.text}")


def validate_streampay_signature(values: Dict[str, Any], signature_hex: str) -> bool:
    if not PUBLIC_KEY:
        raise ValueError("Streampay public key is not configured")

    signature = binascii.unhexlify(signature_hex)
    now = datetime.utcnow()

    ordered_content = "&".join(f"{k}={values[k]}" for k in sorted(values.keys())).encode("utf-8")

    for _ in range(2, 0, -1):
        try:
            to_sign = ordered_content + bytes(now.strftime("%Y%m%d:%H%M"), "ascii")
            PUBLIC_KEY.verify(to_sign, signature)
            return True
        except BadSignatureError:
            now -= timedelta(minutes=1)
            continue
    return False

