from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class PaymentStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class DiagnosticCentre(Base):
    __tablename__ = "diagnostic_centres"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    location = Column(String)
    tests = relationship("DiagnosticTest", back_populates="centre")
    bookings = relationship("Booking", back_populates="centre")

class DiagnosticTest(Base):
    __tablename__ = "diagnostic_tests"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)
    centre_id = Column(Integer, ForeignKey("diagnostic_centres.id"))
    centre = relationship("DiagnosticCentre", back_populates="tests")
    bookings = relationship("Booking", back_populates="test")

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    test_id = Column(Integer, ForeignKey("diagnostic_tests.id"))
    centre_id = Column(Integer, ForeignKey("diagnostic_centres.id"))
    appointment_time = Column(DateTime)
    amount = Column(Float)
    status = Column(SAEnum(BookingStatus), default=BookingStatus.PENDING)

    user = relationship("User")
    test = relationship("DiagnosticTest", back_populates="bookings")
    centre = relationship("DiagnosticCentre", back_populates="bookings")

class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"
    event_id = Column(String, primary_key=True, index=True)
    processed_at = Column(DateTime, default=datetime.utcnow)
