"""
CLMStore — Payment Pydantic Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.utils.constants import PaymentProvider, PaymentStatus, TransactionType


class PaymentInitiateRequest(BaseModel):
    order_id: int
    provider: PaymentProvider
    payment_details: Optional[Dict[str, Any]] = Field(
        default=None, description="e.g. {phone_number: '+23276123456'} for mobile money"
    )


class PaymentVerifyResponse(BaseModel):
    success: bool
    status: PaymentStatus
    transaction_id: Optional[str] = None
    message: str


class TransactionResponse(BaseModel):
    id: int
    payment_id: int
    type: TransactionType
    amount: float
    currency: str
    status: str
    reference: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: int
    order_id: int
    payment_id: int
    invoice_number: str
    pdf_url: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ReceiptResponse(BaseModel):
    id: int
    order_id: int
    payment_id: int
    receipt_number: str
    pdf_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    provider: PaymentProvider
    provider_ref: Optional[str]
    amount: float
    currency: str
    status: PaymentStatus
    failure_reason: Optional[str]
    refunded_amount: float
    created_at: datetime

    transactions: List[TransactionResponse] = []
    invoice: Optional[InvoiceResponse] = None
    receipt: Optional[ReceiptResponse] = None

    class Config:
        from_attributes = True


class RefundRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)
    amount: Optional[float] = Field(default=None, description="Null for full refund")
