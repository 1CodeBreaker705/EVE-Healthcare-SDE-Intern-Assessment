from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from .models import BookingStatus, PaymentStatus

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class DiagnosticTestBase(BaseModel):
    name: str
    price: float

class DiagnosticTestCreate(DiagnosticTestBase):
    pass

class DiagnosticTestResponse(DiagnosticTestBase):
    id: int
    centre_id: int
    class Config:
        from_attributes = True

class DiagnosticCentreBase(BaseModel):
    name: str
    location: str

class DiagnosticCentreCreate(DiagnosticCentreBase):
    pass

class DiagnosticCentreResponse(DiagnosticCentreBase):
    id: int
    tests: List[DiagnosticTestResponse] = []
    class Config:
        from_attributes = True

class BookingCreate(BaseModel):
    test_id: int
    centre_id: int
    appointment_time: datetime

class BookingResponse(BaseModel):
    id: int
    user_id: int
    test_id: int
    centre_id: int
    appointment_time: datetime
    amount: float
    status: BookingStatus
    class Config:
        from_attributes = True

class PaymentRequest(BaseModel):
    booking_id: int

class PaymentResponse(BaseModel):
    status: PaymentStatus
    booking_id: int

class WebhookPayload(BaseModel):
    event_id: str
    booking_id: int
    payment_status: PaymentStatus
