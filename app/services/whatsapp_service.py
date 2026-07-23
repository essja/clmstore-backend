"""
CLMStore — WhatsApp Business Cloud API Integration Service
Handles Meta Graph API outgoing messages, interactive buttons, list messages, and HMAC signature verification.
"""
from __future__ import annotations

import hmac
import hashlib
import httpx
import logging
from typing import Any, Dict, List, Optional

from app.config.settings import get_settings

logger = logging.getLogger("clmstore.whatsapp")
settings = get_settings()


class WhatsAppService:
    def __init__(self) -> None:
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.api_version = settings.WHATSAPP_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"

    @staticmethod
    def verify_webhook_signature(payload: bytes, signature_header: Optional[str]) -> bool:
        """Validates incoming Meta X-Hub-Signature-256 HMAC header for webhook security."""
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        if not settings.SECRET_KEY:
            return True # Fallback if secret key not configured

        expected_sig = signature_header.split("sha256=")[1]
        mac = hmac.new(settings.SECRET_KEY.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
        computed_sig = mac.hexdigest()

        return hmac.compare_digest(computed_sig, expected_sig)

    async def _send_raw(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sends raw json payload to Meta Cloud API endpoint."""
        if not self.phone_number_id or not self.access_token:
            logger.info(f"[SIMULATED WHATSAPP OUTGOING]: {payload}")
            return {"status": "simulated", "payload": payload}

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(self.base_url, json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.error(f"WhatsApp API Error [{resp.status_code}]: {resp.text}")
            return resp.json()

    async def send_text_message(self, recipient_number: str, text: str) -> Dict[str, Any]:
        """Sends plain text message to customer WhatsApp number."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_number,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        return await self._send_raw(payload)

    async def send_interactive_buttons(
        self, recipient_number: str, body_text: str, buttons: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Sends quick reply interactive action buttons (max 3 buttons).
        `buttons` format: [{"id": "opt_1", "title": "Order Food"}]
        """
        formatted_buttons = [
            {
                "type": "reply",
                "reply": {"id": btn["id"], "title": btn["title"][:20]}, # Meta max 20 chars
            }
            for btn in buttons[:3]
        ]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": formatted_buttons},
            },
        }
        return await self._send_raw(payload)

    async def send_interactive_list(
        self,
        recipient_number: str,
        header_text: str,
        body_text: str,
        button_label: str,
        sections: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Sends section list message for selecting restaurants or menu items.
        `sections` format: [{"title": "Categories", "rows": [{"id": "1", "title": "Balmaya", "description": "Sierra Leonean"}]}]
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_number,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header_text[:60]},
                "body": {"text": body_text[:1024]},
                "action": {
                    "button": button_label[:20],
                    "sections": sections,
                },
            },
        }
        return await self._send_raw(payload)
