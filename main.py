import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column
from sqlalchemy import String, DateTime

DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine) if engine else None
Base = declarative_base()


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    item: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), default="processing")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


SEED_ORDERS = [
    {"item": "Laptop stand", "status": "shipped"},
    {"item": "Mechanical keyboard", "status": "processing"},
    {"item": "Monitor arm", "status": "processing"},
]


def seed_if_empty():
    if engine is None:
        return
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if session.query(Order).count() == 0:
            session.add_all(Order(**o) for o in SEED_ORDERS)
            session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_if_empty()
    yield


app = FastAPI(title="Grads Foundry — Orders Service", lifespan=lifespan)


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


@app.get("/api/orders")
def list_orders():
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not configured (DATABASE_URL not set)")
    with SessionLocal() as session:
        orders = session.query(Order).order_by(Order.id).all()
        return [
            {"id": o.id, "item": o.item, "status": o.status, "created_at": o.created_at.isoformat()}
            for o in orders
        ]


@app.get("/api/orders/{order_id}")
def get_order(order_id: int):
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not configured (DATABASE_URL not set)")
    with SessionLocal() as session:
        order = session.get(Order, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        return {
            "id": order.id,
            "item": order.item,
            "status": order.status,
            "created_at": order.created_at.isoformat(),
        }


# --- Sprint 1 ticket lands here ---
# Add order attachments: POST /api/orders/{id}/attachments (upload a file to
# S3), GET /api/orders/{id}/attachments (a presigned download URL). See
# infra/DESIGN.md for the S3 bucket/prefix this should use and the IAM
# permission the student's deploy role already has for it.
