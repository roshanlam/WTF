from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class FreeFoodEvent(BaseModel):
    schema_version: str = "1.0.0"
    event_id: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    source: str
    llm_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    reason: Optional[str] = None
    type: str = "FREE_FOOD_EVENT"
    published_at: datetime
    retries: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
