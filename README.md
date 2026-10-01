# EVE Healthcare Backend Service
**SDE Intern — Backend Engineering Assignment**

## Overview
This repository contains a robust, production-ready backend service designed for diagnostic test bookings and simulated payment processing. The system is built leveraging a modern, asynchronous microservices architecture utilizing FastAPI, PostgreSQL, Redis, and Celery.

The implementation strictly adheres to all core assignment requirements while comprehensively fulfilling every optional bonus objective, including container orchestration, background task processing, rate limiting, and structured logging.

---

## 🏗 System Architecture

The application is fully containerized and orchestrated via Docker Compose, bridging 4 isolated components on a private virtual network:

1. **Web Server (`web`)**: A high-performance FastAPI instance running on Uvicorn.
2. **Database (`db`)**: PostgreSQL 15, managed via SQLAlchemy ORM.
3. **Message Broker (`redis`)**: In-memory data store for queuing background tasks.
4. **Background Worker (`worker`)**: Celery daemon dedicated to asynchronously processing webhooks and performing heavy database updates.

---

## ✨ Features Implemented

### Core Requirements
*   **Authentication**: Complete JWT-based OAuth2 implementation utilizing `passlib` for bcrypt hashing and Pydantic for strict request validation.
*   **Diagnostic Centres & Tests**: Comprehensive REST APIs to create and retrieve diagnostic centers and relational diagnostic tests.
*   **Booking System**: Secure, authenticated endpoints to process user bookings. Crucially, the system calculates booking `amount` server-side via relational database queries to prevent client-side manipulation.
*   **Simulated Payment Service**: A functional mock endpoint (`POST /payments/`) resolving transactions randomly to `SUCCESS` or `FAILED`.
*   **Webhook Endpoints**: `POST /payments/webhook/` handles incoming payment status updates.
*   **Idempotency & Edge Cases**: Webhooks are fully idempotent. The system verifies incoming `event_id` payloads against a `processed_webhooks` ledger to block duplicate processing. Invalid requests, unauthorized access, and invalid relationships are met with standardized HTTP error codes (400, 401, 404, 422).

### Advanced Implementations (Bonus Objectives)
*   ✅ **Docker & Docker Compose**: 4-container orchestrated deployment featuring native Docker Healthchecks to gracefully handle startup race conditions.
*   ✅ **Celery & Redis**: Webhook processing is completely offloaded to a background Celery worker. If the PostgreSQL database experiences downtime during a webhook event, Celery catches the exception and executes an automated retry sequence using exponential backoff.
*   ✅ **Swagger/OpenAPI**: Interactive API documentation automatically exposed at `/docs`.
*   ✅ **Unit & Integration Tests**: Comprehensive `pytest` suite mapping directly to the 6 core requirements.
*   ✅ **Structured Logging**: Implemented via `structlog` to output machine-readable JSON logs for advanced monitoring.
*   ✅ **Rate Limiting**: Integrated `slowapi` to protect authentication and webhook routes from DDoS or brute-force attacks (e.g., 10 requests/minute).
*   ✅ **Pagination**: Cursor-based pagination (`skip`, `limit`) applied to all list-based `GET` endpoints to prevent memory exhaustion on large database reads.

---

## 🚀 Running the Project

### Option A: Production Environment (Docker)
**Prerequisites:** Ensure [Docker](https://www.docker.com/) and Docker Compose are installed on your machine.

1. **Start the orchestrated environment:**
   ```bash
   docker-compose up --build
   ```
2. **Access the Application:** Once all healthchecks pass, the API is available at `http://localhost:8000/docs`.

*(Architecture Note: In Docker, Celery runs **asynchronously**. The server instantly queues the webhook payload in Redis and returns a 200 OK without blocking, allowing the server to handle massive traffic volume while the database updates in the background.)*

### Option B: Local Development Mode (No Docker)
If you do not have Docker installed, you can run the application natively using the included override script.

1. **Install dependencies and run the script:**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements-local.txt
   python run_local.py   ```
2. **Access the Application:** The API is available at `http://127.0.0.1:8000/docs`.

*(Architecture Note: `run_local.py` dynamically overrides the database to a local SQLite file and forces Celery to run **synchronously** via `task_always_eager=True`. This intentionally blocks the server while the webhook processes so developers can instantly verify database updates without needing to configure a local Redis queue.)*

---

## 📡 API Endpoints & Example Requests
*(Note: Interactive example requests and JSON payload schemas are automatically generated and testable via the Swagger UI at http://127.0.0.1:8000/docs)*

**Authentication (Rate Limited: 10/min)**
* `POST /signup` - Registers a new user and securely hashes their password.
* `POST /login` - Authenticates a user and returns a JWT access token.

**Diagnostic Centres & Tests**
* `POST /centres` - Creates a new diagnostic centre.
* `GET /centres` - Retrieves a paginated list of all diagnostic centres.
* `POST /centres/{centre_id}/tests` - Adds a specific diagnostic test (and its price) to a centre.
* `GET /centres/{centre_id}/tests` - Retrieves a paginated list of tests for a specific centre.

**Booking System**
* `POST /bookings` - *(Requires Auth)* Books an appointment. Automatically validates the test/centre relationship and fetches the correct test price to prevent client-side manipulation.
* `GET /bookings` - *(Requires Auth)* Retrieves a paginated list of the current user's bookings.

**Payments & Webhooks**
* `POST /payments/` - *(Requires Auth)* Mock payment gateway. Simulates a transaction and randomly returns `SUCCESS` or `FAILED`.
* `POST /payments/webhook/` - *(Rate Limited: 50/min)* The webhook listener. Receives status payloads, queues them in Redis, and processes them idempotently in the background via Celery.

---

## 🧪 Running the Test Suite
The automated test suite evaluates authentication, relational logic, simulated payments, and webhook idempotency. The test environment automatically mocks the database to use an isolated SQLite memory instance and configures Celery to execute synchronously, ensuring zero cross-contamination with the production PostgreSQL database.

**Option A: Running with Docker (Recommended)**
```bash
docker-compose run web pytest tests/
```

**Option B: Running Locally (Without Docker)**
If you prefer to run the tests natively on your local machine without Docker:
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements-local.txt
python -m pytest tests/
```


## 🗄️ Database & Schema Design
The application uses a relational database (PostgreSQL) modeled with SQLAlchemy:
* **User**: Stores patient credentials (hashed passwords) and email.
* **DiagnosticCentre**: Represents clinic locations.
* **DiagnosticTest**: Represents tests offered (Many-to-One relationship with Centre).
* **Booking**: The core transactional table linking a User, DiagnosticCentre, and DiagnosticTest. Tracks the computed amount, appointment_time, and status.
* **ProcessedWebhook**: A ledger tracking event_ids used exclusively to guarantee webhook idempotency.

## Important Assumptions
* **Server-Side Pricing**: The client does not send the amount during a booking request. The server automatically computes the total by querying the database to prevent client-side price manipulation.
* **Idempotency Keys**: We assume the external payment provider sends a globally unique event_id with every webhook payload.
* **Timezones**: All appointment times are assumed to be handled in UTC.

## Future Improvements (With More Time)
* **Real Payment Integration**: Swap the mock /payments/ endpoint with a real Stripe or Razorpay SDK.
* **Role-Based Access Control (RBAC)**: Implement strict JWT scopes to separate Admin users (who create centres/tests) from Patient users (who book appointments).
* **Availability Scheduling**: Implement strict time-slot concurrency checking so two patients cannot book the exact same slot.
* **Email Notifications**: Expand the Celery worker to dispatch real confirmation emails (e.g., via SendGrid) when a payment webhook is successfully processed.
