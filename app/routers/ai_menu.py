"""
CLMStore — AI Menu Extraction
Accepts a menu photo or PDF, sends it to Claude vision, returns structured categories+items.
"""
from __future__ import annotations

import base64
import json
import re

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config.settings import settings

router = APIRouter()

_EXTRACT_PROMPT = """\
You are a menu digitisation assistant for CLMStore, a Sierra Leone food delivery app.

Look at this menu image (or PDF page) and extract ALL food/drink items you can see.

Return ONLY valid JSON in this exact shape — no markdown, no extra text:
{
  "categories": [
    {
      "name": "Category Name",
      "items": [
        {
          "name": "Item Name",
          "description": "Short description if visible, otherwise empty string",
          "price": 0
        }
      ]
    }
  ]
}

Rules:
- If no category headings are visible, put everything under "Main Menu".
- Prices must be numbers (no currency symbols). If you cannot read a price clearly, use 0.
- Strip "Le", "SLL", commas, or any currency text from prices.
- Include every item you can see, even if description or price is missing.
- Do not include anything that is not a food or drink item (e.g. restaurant name, phone numbers).
"""


def _clean_json(text: str) -> dict:
    """Strip markdown fences if Claude wrapped the JSON, then parse."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _html_to_text(html: str) -> str:
    """Strip HTML tags and return plain text, skipping scripts/styles/nav."""
    from html.parser import HTMLParser

    class _Extractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self._parts: list[str] = []
            self._skip = False

        def handle_starttag(self, tag, attrs):
            if tag.lower() in ("script", "style", "noscript", "head", "nav", "footer", "header"):
                self._skip = True

        def handle_endtag(self, tag):
            if tag.lower() in ("script", "style", "noscript", "head", "nav", "footer", "header"):
                self._skip = False

        def handle_data(self, data):
            if not self._skip:
                t = data.strip()
                if t:
                    self._parts.append(t)

        def text(self) -> str:
            return "\n".join(self._parts)

    ext = _Extractor()
    ext.feed(html)
    return ext.text()


_URL_PROMPT = """\
You are a menu digitisation assistant for CLMStore, a Sierra Leone food delivery app.

Below is text extracted from a restaurant website or menu page. Extract ALL food/drink items you can find.

Return ONLY valid JSON — no markdown, no extra text:
{
  "categories": [
    {
      "name": "Category Name",
      "items": [
        {
          "name": "Item Name",
          "description": "Short description or empty string",
          "price": 0
        }
      ]
    }
  ]
}

Rules:
- If no category headings are visible put everything under "Main Menu".
- Prices must be plain numbers. Strip Le, SLL, $, commas, spaces.
- If a price is unclear use 0.
- Skip navigation links, phone numbers, opening hours, addresses.
- If no menu items are found at all return {"categories": []}.

PAGE TEXT:
"""


@router.post("/ai-extract")
async def ai_extract_menu(
    file: UploadFile = File(...),
    restaurant_id: int = Form(...),
):
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "AI menu extraction is not configured. "
                "Add ANTHROPIC_API_KEY to your .env file and restart the server."
            ),
        )

    content_type = file.content_type or ""
    is_image = content_type.startswith("image/")
    is_pdf = content_type == "application/pdf"

    if not is_image and not is_pdf:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please upload an image (JPG/PNG/WEBP) or a PDF file.",
        )

    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File is too large. Maximum size is 10 MB.",
        )

    b64 = base64.standard_b64encode(raw).decode("utf-8")

    try:
        import anthropic as _anthropic

        client = _anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        if is_image:
            media_type = content_type  # e.g. "image/jpeg"
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": _EXTRACT_PROMPT},
                        ],
                    }
                ],
            )
        else:
            # PDF — use the document source type (Claude supports it natively)
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": _EXTRACT_PROMPT},
                        ],
                    }
                ],
            )

        raw_text = message.content[0].text
        result = _clean_json(raw_text)

        categories = result.get("categories", [])
        if not categories:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not find any menu items in the file. Please try a clearer photo.",
            )

        return {"success": True, "categories": categories}

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="AI could not parse the menu. Please try a clearer photo or use CSV upload instead.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI extraction failed: {str(exc)}",
        )


# ── URL / Website import ──────────────────────────────────────────────────────

class UrlExtractRequest(BaseModel):
    url: str
    restaurant_id: int


@router.post("/ai-extract-url")
async def ai_extract_from_url(body: UrlExtractRequest):
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI menu extraction is not configured. Add ANTHROPIC_API_KEY to your .env file.",
        )

    # ── Fetch the page ────────────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                body.url,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That website took too long to respond. Please try again.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not open that URL: {str(exc)}",
        )

    # ── Strip HTML → plain text ───────────────────────────────────────────────
    page_text = _html_to_text(resp.text)
    page_text = page_text[:12000]  # cap at ~12k chars to control AI cost

    if len(page_text.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "That page doesn't have enough readable text. "
                "It may require a login or is a JavaScript-only app. "
                "Try taking a photo of your menu instead."
            ),
        )

    # ── Send to Claude ────────────────────────────────────────────────────────
    try:
        import anthropic as _anthropic

        client = _anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": _URL_PROMPT + page_text,
                }
            ],
        )

        raw_text = message.content[0].text
        result = _clean_json(raw_text)
        categories = result.get("categories", [])

        if not categories:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "No menu items found on that page. "
                    "The site may require a login or doesn't show menu items publicly. "
                    "Try uploading a photo of your menu instead."
                ),
            )

        return {"success": True, "categories": categories}

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="AI could not parse the menu from that page. Try CSV upload instead.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI extraction failed: {str(exc)}",
        )
