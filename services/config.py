import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
MQ_STREAM = os.getenv("MQ_STREAM", "events.free-food")

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
USE_SSL = os.getenv("USE_SSL", "true").lower() in ["1", "true", "yes"]
USE_STARTTLS = os.getenv("USE_STARTTLS", "false").lower() in ["1", "true", "yes"]
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ["1", "true", "yes"]
