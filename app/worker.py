from celery import Celery
import structlog
from .config import settings
from .database import SessionLocal
from . import models

logger = structlog.get_logger()
celery = Celery(__name__, broker=settings.REDIS_URL)

@celery.task(name="process_webhook", bind=True, max_retries=3)
def process_webhook_task(self, payload_dict):
    """
    Background job to process webhooks. 
    Includes built-in retries using Celery if the DB is unavailable.
    """
    db = SessionLocal()
    event_id = payload_dict["event_id"]
    try:
        logger.info("processing_webhook_started", event_id=event_id)
        
        # 1. Idempotency Check
        processed = db.query(models.ProcessedWebhook).filter(models.ProcessedWebhook.event_id == event_id).first()
        if processed:
            logger.info("webhook_already_processed", event_id=event_id)
            return "Already processed"

        # 2. Retrieve Booking
        booking = db.query(models.Booking).filter(models.Booking.id == payload_dict["booking_id"]).first()
        if not booking:
            logger.error("webhook_booking_not_found", event_id=event_id, booking_id=payload_dict["booking_id"])
            return "Booking not found"

        # 3. Process Status Update
        if payload_dict["payment_status"] == models.PaymentStatus.SUCCESS.value:
            booking.status = models.BookingStatus.CONFIRMED
        elif payload_dict["payment_status"] == models.PaymentStatus.FAILED.value:
            booking.status = models.BookingStatus.FAILED
        
        # 4. Mark Event as Processed
        db_event = models.ProcessedWebhook(event_id=event_id)
        db.add(db_event)
        
        db.commit()
        logger.info("webhook_processed_successfully", event_id=event_id, booking_id=booking.id, status=booking.status)
        return "Success"
        
    except Exception as exc:
        db.rollback()
        logger.error("webhook_processing_failed", event_id=event_id, error=str(exc))
        # Exponential backoff retry: 2s, 4s, 8s
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    finally:
        db.close()
