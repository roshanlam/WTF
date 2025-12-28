"""SQLite database for WTF (Where's The Food) system."""

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from redis import Redis

DB_PATH = os.getenv("DATABASE_PATH", "wtf.db")
CACHE_TTL = int(os.getenv("CACHE_ACTIVE_USERS_TTL", "300"))  # 5 minutes default
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Thread-local storage for database connections (simple connection pool)
_thread_local = threading.local()

# Redis client for caching (lazy initialization)
_redis_client: Optional[Redis] = None


def _get_redis() -> Optional[Redis]:
    """Get Redis client for caching with connection pooling."""
    global _redis_client
    if _redis_client is None:
        try:
            # Import here to avoid circular dependency
            from services.mq import get_redis_pool

            _redis_client = Redis(connection_pool=get_redis_pool())
            # Test connection
            _redis_client.ping()
            print("✅ Redis caching enabled with connection pooling")
        except Exception as e:
            print(f"⚠️  Redis caching unavailable: {e}")
            return None
    return _redis_client


def get_connection():
    """Get a database connection with basic thread-local pooling."""
    # Use thread-local connection if available
    if not hasattr(_thread_local, "connection") or _thread_local.connection is None:
        _thread_local.connection = sqlite3.connect(
            DB_PATH,
            check_same_thread=False,  # Allow connection sharing in same thread
            timeout=30.0,  # 30 second timeout for locks
        )
        _thread_local.connection.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        _thread_local.connection.execute("PRAGMA journal_mode=WAL")
        print(
            f"✅ Created new DB connection for thread {threading.current_thread().name}"
        )
    return _thread_local.connection


@contextmanager
def db_transaction():
    """Context manager for database transactions with automatic commit/rollback."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    """Initialize the database with tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            event_date TEXT NOT NULL,
            source TEXT,
            source_id TEXT,
            has_free_food INTEGER DEFAULT 0,
            confidence_score REAL,
            classification_timestamp TEXT,
            organizer TEXT,
            category TEXT,
            notified INTEGER DEFAULT 0,
            notification_timestamp TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create index on event_date for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_event_date ON events(event_date)
    """)

    # Create index on has_free_food for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_has_free_food ON events(has_free_food)
    """)

    conn.commit()
    conn.close()
    print(f"✅ Database initialized at {DB_PATH}")


# User operations
def add_user(email: str) -> bool:
    """Add a user subscription."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (email) VALUES (?)", (email,))
        conn.commit()
        conn.close()
        # Invalidate cache when user list changes
        invalidate_users_cache()
        return True
    except sqlite3.IntegrityError:
        return False


def get_user(email: str) -> Optional[dict]:
    """Get user by email."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, email, active, created_at FROM users WHERE email = ?", (email,)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "email": row["email"],
            "active": bool(row["active"]),
            "created_at": row["created_at"],
        }
    return None


def get_active_users() -> list[str]:
    """Get all active user emails with Redis caching."""
    cache_key = "active_users_cache"
    redis = _get_redis()

    # Try to get from cache first
    if redis:
        try:
            cached = redis.get(cache_key)
            if cached:
                print(
                    f"✅ Cache HIT: Loaded {len(json.loads(cached))} users from Redis cache"
                )
                return json.loads(cached)
        except Exception as e:
            print(f"⚠️  Cache read error: {e}")

    # Cache miss or Redis unavailable - query database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE active = 1")
    emails = [row["email"] for row in cursor.fetchall()]
    conn.close()

    # Update cache
    if redis and emails:
        try:
            redis.setex(cache_key, CACHE_TTL, json.dumps(emails))
            print(
                f"✅ Cache MISS: Loaded {len(emails)} users from DB and cached for {CACHE_TTL}s"
            )
        except Exception as e:
            print(f"⚠️  Cache write error: {e}")

    return emails


def invalidate_users_cache():
    """Invalidate the active users cache."""
    redis = _get_redis()
    if redis:
        try:
            redis.delete("active_users_cache")
            print("✅ Active users cache invalidated")
        except Exception as e:
            print(f"⚠️  Cache invalidation error: {e}")


def deactivate_user(email: str) -> bool:
    """Deactivate a user subscription."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET active = 0 WHERE email = ?", (email,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    # Invalidate cache when user list changes
    if affected > 0:
        invalidate_users_cache()
    return affected > 0


# Event operations
def add_event(
    title: str,
    description: str,
    location: str,
    event_date: str,
    source: Optional[str] = None,
    source_id: Optional[str] = None,
    organizer: Optional[str] = None,
    category: Optional[str] = None,
    has_free_food: bool = False,
    confidence_score: Optional[float] = None,
) -> int:
    """Add an event to the database."""
    conn = get_connection()
    cursor = conn.cursor()

    classification_timestamp = (
        datetime.utcnow().isoformat() if confidence_score is not None else None
    )

    cursor.execute(
        """
        INSERT INTO events (
            title, description, location, event_date, source, source_id,
            organizer, category, has_free_food, confidence_score, classification_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            title,
            description,
            location,
            event_date,
            source,
            source_id,
            organizer,
            category,
            int(has_free_food),
            confidence_score,
            classification_timestamp,
        ),
    )

    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id


def get_event(event_id: int) -> Optional[dict]:
    """Get event by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def get_events(
    limit: int = 100,
    has_free_food: Optional[bool] = None,
    notified: Optional[bool] = None,
) -> list[dict]:
    """Get events with optional filters."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM events WHERE 1=1"
    params = []

    if has_free_food is not None:
        query += " AND has_free_food = ?"
        params.append(int(has_free_food))

    if notified is not None:
        query += " AND notified = ?"
        params.append(int(notified))

    query += " ORDER BY event_date DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return events


def update_event_classification(
    event_id: int, has_free_food: bool, confidence_score: float
) -> bool:
    """Update event classification from LLM."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE events
        SET has_free_food = ?,
            confidence_score = ?,
            classification_timestamp = ?
        WHERE id = ?
    """,
        (int(has_free_food), confidence_score, datetime.utcnow().isoformat(), event_id),
    )

    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def mark_event_notified(event_id: int) -> bool:
    """Mark an event as notified."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE events
        SET notified = 1,
            notification_timestamp = ?
        WHERE id = ?
    """,
        (datetime.utcnow().isoformat(), event_id),
    )

    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_similar_events(description: str, limit: int = 5) -> list[dict]:
    """Get similar events for LLM context (simple keyword matching)."""
    conn = get_connection()
    cursor = conn.cursor()

    # Simple keyword search - extract key terms
    keywords = [
        word.lower()
        for word in description.split()
        if len(word) > 3 and word.lower() not in ["free", "food", "pizza", "lunch"]
    ]

    if not keywords:
        keywords = ["event"]

    # Search for events with similar keywords
    query = """
        SELECT * FROM events
        WHERE has_free_food = 1
        AND (
    """
    conditions = []
    params: list[object] = []

    for keyword in keywords[:3]:  # Use first 3 keywords
        conditions.append("description LIKE ? OR title LIKE ?")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    query += " OR ".join(conditions)
    query += ") ORDER BY classification_timestamp DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return events


def get_stats() -> dict:
    """Get database statistics."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM events")
    total_events = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM events WHERE has_free_food = 1")
    food_events = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM users WHERE active = 1")
    active_users = cursor.fetchone()["total"]

    conn.close()

    return {
        "total_events": total_events,
        "food_events": food_events,
        "active_users": active_users,
    }
