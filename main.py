import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column

DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine) if engine else None
Base = declarative_base()

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")  # unset locally -- publish is skipped, not faked


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    balance_cents: Mapped[int] = mapped_column(Integer)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    from_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    to_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def as_dict(self):
        return {
            "id": self.id,
            "from_account_id": self.from_account_id,
            "to_account_id": self.to_account_id,
            "amount_cents": self.amount_cents,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


SEED_ACCOUNTS = [
    {"name": "Aishwarya's Wallet", "balance_cents": 10_000},
    {"name": "Karthik's Wallet", "balance_cents": 5_000},
    {"name": "Merchant: Chai Point", "balance_cents": 0},
]


def seed_if_empty():
    if engine is None:
        return
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if session.query(Account).count() == 0:
            session.add_all(Account(**a) for a in SEED_ACCOUNTS)
            session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_if_empty()
    yield


app = FastAPI(title="Grads Foundry — Payments Service", lifespan=lifespan)


def publish_payment_event(payment: Payment):
    # Best-effort, and deliberately AFTER the transaction has already
    # committed: a notification failing must never be able to undo a
    # payment that already succeeded. If SNS isn't configured (e.g. running
    # locally), this is a no-op, not a fake success.
    if not SNS_TOPIC_ARN:
        return
    try:
        import boto3

        boto3.client("sns").publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps({"event": "payment.completed", "payment": payment.as_dict()}),
        )
    except Exception:
        # Deliberately swallowed -- see the comment above. A real system
        # would log this to CloudWatch for the on-call engineer to notice,
        # not retry-loop inside the request.
        pass


class CreatePayment(BaseModel):
    from_account_id: int
    to_account_id: int
    amount_cents: int = Field(gt=0)


@app.get("/api/health")
def health():
    db_connected = None
    if engine is not None:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_connected = True
        except Exception:
            db_connected = False
    return {"status": "ok", "db_connected": db_connected}


@app.get("/api/accounts/{account_id}")
def get_account(account_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not configured (DATABASE_URL not set)")
    with SessionLocal() as session:
        account = session.get(Account, account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"id": account.id, "name": account.name, "balance_cents": account.balance_cents}


@app.post("/api/payments", status_code=201)
def create_payment(body: CreatePayment, idempotency_key: str = Header(..., alias="Idempotency-Key")):
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not configured (DATABASE_URL not set)")

    if body.from_account_id == body.to_account_id:
        raise HTTPException(status_code=400, detail="from_account_id and to_account_id must differ")

    with SessionLocal() as session:
        # A retried request (same client, same key, e.g. after a timed-out
        # response) must return the ORIGINAL result, never move money twice.
        # This query already opens an implicit transaction on this Session
        # (SQLAlchemy 2.0 "autobegin") -- there is no separate `session.begin()`
        # block below; everything shares that one transaction, committed or
        # rolled back explicitly.
        existing = session.query(Payment).filter_by(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing.as_dict()

        try:
            # Lock both accounts in a fixed order (lowest id first) --
            # without this, two concurrent transfers between the same two
            # accounts in opposite directions can deadlock each other.
            ids_in_order = sorted([body.from_account_id, body.to_account_id])
            locked = {
                a.id: a
                for a in session.query(Account)
                .filter(Account.id.in_(ids_in_order))
                .order_by(Account.id)
                .with_for_update()
                .all()
            }
            sender = locked.get(body.from_account_id)
            receiver = locked.get(body.to_account_id)
            if sender is None or receiver is None:
                raise HTTPException(status_code=404, detail="from_account_id or to_account_id not found")
            if sender.balance_cents < body.amount_cents:
                raise HTTPException(status_code=402, detail="Insufficient funds")

            sender.balance_cents -= body.amount_cents
            receiver.balance_cents += body.amount_cents

            payment = Payment(
                idempotency_key=idempotency_key,
                from_account_id=body.from_account_id,
                to_account_id=body.to_account_id,
                amount_cents=body.amount_cents,
                status="completed",
            )
            session.add(payment)
            session.commit()
        except HTTPException:
            session.rollback()
            raise

        result = payment.as_dict()

    publish_payment_event(payment)  # after commit -- see comment on the function
    return result


@app.get("/api/payments/{payment_id}")
def get_payment(payment_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not configured (DATABASE_URL not set)")
    with SessionLocal() as session:
        payment = session.get(Payment, payment_id)
        if payment is None:
            raise HTTPException(status_code=404, detail="Payment not found")
        return payment.as_dict()


# --- Sprint 1 ticket lands here ---
# Add payment disputes: a customer can dispute a completed payment, attach
# evidence (receipt/screenshot) to it via S3, and track its status
# (open/resolved). POST /api/payments/{id}/disputes to open one with an
# uploaded file; GET to fetch it back with a presigned download URL.
