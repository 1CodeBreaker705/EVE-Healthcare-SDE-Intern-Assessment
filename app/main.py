from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from typing import List
import random
import structlog
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from . import models, schemas, auth, database
from .database import engine, get_db
from .worker import process_webhook_task

# Setup Structured Logging
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# Setup Rate Limiter
limiter = Limiter(key_func=get_remote_address)

# Create all tables in DB (in production, use Alembic)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="EVE Healthcare API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirects the root URL to the interactive Swagger UI documentation."""
    return RedirectResponse(url="/docs")

@app.post("/signup", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def signup(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)):
    logger.info("signup_attempt", email=user.email)
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        logger.warning("signup_failed_email_exists", email=user.email)
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info("signup_successful", user_id=new_user.id)
    return new_user

@app.post("/login", response_model=schemas.Token)
@limiter.limit("10/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        logger.warning("login_failed", email=form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth.create_access_token(data={"sub": user.email})
    logger.info("login_successful", user_id=user.id)
    return {"access_token": access_token, "token_type": "bearer"}

# --- Diagnostic Centres & Tests ---
@app.post("/centres", response_model=schemas.DiagnosticCentreResponse)
def create_centre(centre: schemas.DiagnosticCentreCreate, db: Session = Depends(get_db)):
    db_centre = models.DiagnosticCentre(**centre.model_dump())
    db.add(db_centre)
    db.commit()
    db.refresh(db_centre)
    return db_centre

@app.get("/centres", response_model=List[schemas.DiagnosticCentreResponse])
def get_centres(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    # Pagination implemented via skip and limit
    return db.query(models.DiagnosticCentre).offset(skip).limit(limit).all()

@app.post("/centres/{centre_id}/tests", response_model=schemas.DiagnosticTestResponse)
def add_test_to_centre(centre_id: int, test: schemas.DiagnosticTestCreate, db: Session = Depends(get_db)):
    centre = db.query(models.DiagnosticCentre).filter(models.DiagnosticCentre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=404, detail="Centre not found")
    db_test = models.DiagnosticTest(**test.model_dump(), centre_id=centre_id)
    db.add(db_test)
    db.commit()
    db.refresh(db_test)
    return db_test

@app.get("/centres/{centre_id}/tests", response_model=List[schemas.DiagnosticTestResponse])
def get_tests(centre_id: int, skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    # Pagination implemented via skip and limit
    tests = db.query(models.DiagnosticTest).filter(models.DiagnosticTest.centre_id == centre_id).offset(skip).limit(limit).all()
    return tests

# --- Bookings ---
@app.post("/bookings", response_model=schemas.BookingResponse)
def create_booking(booking: schemas.BookingCreate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    test = db.query(models.DiagnosticTest).filter(
        models.DiagnosticTest.id == booking.test_id, 
        models.DiagnosticTest.centre_id == booking.centre_id
    ).first()
    if not test:
        raise HTTPException(status_code=400, detail="Invalid test or centre")
    
    db_booking = models.Booking(
        user_id=current_user.id,
        test_id=booking.test_id,
        centre_id=booking.centre_id,
        appointment_time=booking.appointment_time,
        amount=test.price,
        status=models.BookingStatus.PENDING
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    logger.info("booking_created", user_id=current_user.id, booking_id=db_booking.id)
    return db_booking

@app.get("/bookings", response_model=List[schemas.BookingResponse])
def get_user_bookings(skip: int = 0, limit: int = 10, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    # Pagination implemented via skip and limit
    return db.query(models.Booking).filter(models.Booking.user_id == current_user.id).offset(skip).limit(limit).all()

# --- Simulated Payments ---
@app.post("/payments/", response_model=schemas.PaymentResponse)
def simulate_payment(req: schemas.PaymentRequest, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    booking = db.query(models.Booking).filter(models.Booking.id == req.booking_id, models.Booking.user_id == current_user.id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.status != models.BookingStatus.PENDING:
        raise HTTPException(status_code=400, detail="Booking is not in PENDING state")
    
    is_success = random.choice([True, False])
    payment_status = models.PaymentStatus.SUCCESS if is_success else models.PaymentStatus.FAILED
    
    if is_success:
        booking.status = models.BookingStatus.CONFIRMED
    else:
        booking.status = models.BookingStatus.FAILED
        
    db.commit()
    return {"status": payment_status, "booking_id": booking.id}

@app.post("/payments/webhook/")
@limiter.limit("50/minute")
def payment_webhook(request: Request, payload: schemas.WebhookPayload):
    # Enqueue background task for Celery processing
    logger.info("webhook_received_and_queued", event_id=payload.event_id)
    process_webhook_task.delay({
        "event_id": payload.event_id,
        "booking_id": payload.booking_id,
        "payment_status": payload.payment_status.value
    })
    
    return {"msg": "Webhook received and queued for processing"}
