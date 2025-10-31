import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
MQ_STREAM = os.getenv("MQ_STREAM", "events.free-food")
