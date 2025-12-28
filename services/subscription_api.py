"""Simple subscription API to manage email subscriptions."""

import os
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.database import (
    add_user,
    deactivate_user,
    get_active_users,
    init_db,
)

app = FastAPI(title="WTF Subscription API")

# Initialize database on startup
init_db()


class EmailSubscription(BaseModel):
    """Single email subscription."""

    email: str


class BulkEmailSubscription(BaseModel):
    """Bulk email subscription."""

    emails: List[str]


def get_subscribers() -> set[str]:
    """Get all active subscribers."""
    return set(get_active_users())


def add_subscriber(email: str) -> bool:
    """Add a subscriber to database."""
    return add_user(email)


def remove_subscriber(email: str) -> bool:
    """Deactivate subscriber in database."""
    return deactivate_user(email)


@app.post("/subscribe", status_code=201)
async def subscribe(subscription: EmailSubscription):
    """Subscribe a single email."""
    if add_subscriber(subscription.email):
        return {
            "message": f"Successfully subscribed {subscription.email}",
            "email": subscription.email,
        }
    else:
        raise HTTPException(status_code=400, detail="Email already subscribed")


@app.post("/subscribe/bulk", status_code=201)
async def subscribe_bulk(subscription: BulkEmailSubscription):
    """Subscribe multiple emails at once."""
    added = []
    already_subscribed = []

    for email in subscription.emails:
        if add_subscriber(email):
            added.append(email)
        else:
            already_subscribed.append(email)

    return {
        "message": f"Subscribed {len(added)} email(s)",
        "added": added,
        "already_subscribed": already_subscribed,
    }


@app.delete("/unsubscribe")
async def unsubscribe(subscription: EmailSubscription):
    """Unsubscribe an email."""
    if remove_subscriber(subscription.email):
        return {"message": f"Successfully unsubscribed {subscription.email}"}
    else:
        raise HTTPException(status_code=404, detail="Email not found")


@app.get("/subscribers")
async def list_subscribers():
    """List all active subscribers."""
    subscribers = get_subscribers()
    return {"count": len(subscribers), "subscribers": sorted(list(subscribers))}


@app.get("/")
async def root():
    """API root endpoint."""
    return {"status": "ok", "service": "WTF Subscription API"}


@app.get("/health")
async def health():
    """Health check endpoint for Docker."""
    try:
        # Test database connection
        subscribers = get_subscribers()
        return {
            "status": "healthy",
            "service": "WTF Subscription API",
            "database": "connected",
            "subscribers": len(subscribers),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
