import os
import time
import csv
import logging
import smtplib
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict, Optional, Any
from jinja2 import Template
from dotenv import load_dotenv
from functools import wraps
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("notifier")

# Configs from .env
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
CSV_FILE = os.getenv("CSV_FILE", "test_emails.csv")
DEFAULT_ATTACHMENT = os.getenv("DEFAULT_ATTACHMENT", "assignment.docx")
RATE_LIMIT_SEC = float(os.getenv("RATE_LIMIT_SEC", 1.0))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ["1", "true", "yes"]

# Retry decorator
def retry(exceptions=(Exception,), tries=3, delay=1, backoff=2, logger=logger):
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            _tries, _delay = tries, delay
            while _tries > 1:
                try:
                    return f(*args, **kwargs)
                except exceptions as e:
                    logger.warning(f"{e}, Retrying in {_delay} seconds...")
                    time.sleep(_delay)
                    _tries -= 1
                    _delay *= backoff
            return f(*args, **kwargs)
        return f_retry
    return deco_retry

# Abstract notifier
class Notifier(ABC):
    @abstractmethod
    def notify(self, recipient: str, subject: str, body_html: str, attachments: Optional[List[str]] = None, meta: Optional[Dict[str, Any]] = None) -> bool:
        pass

@dataclass
class SMTPNotifier:
    def __init__(self, smtp_server, smtp_port, smtp_user, smtp_password, use_ssl=True, use_starttls=False, timeout=30, dry_run=False):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.use_ssl = use_ssl
        self.use_starttls = use_starttls
        self.timeout = timeout
        self.dry_run = dry_run

    def _build_message(self, recipient, subject, body_html, attachments=None):
        msg = MIMEMultipart()
        msg["From"] = self.smtp_user
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        if attachments:
            for file_path in attachments:
                with open(file_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f'attachment; filename="{file_path}"')
                    msg.attach(part)

        return msg

    def notify(self, recipient, subject, body_html, attachments=None, meta=None):
        msg = self._build_message(recipient, subject, body_html, attachments)
        
        if self.dry_run:
            logging.info(f"[DRY-RUN] Would send email to {recipient} with subject '{subject}'")
            return True

        try:
            # Gmail requires the use of STARTTLS on port 587
            if self.use_ssl:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=self.timeout) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_user, recipient, msg.as_string())
            elif self.use_starttls:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.timeout) as server:
                    server.ehlo()  # Send the initial EHLO command
                    server.starttls()  # Upgrade the connection to secure
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_user, recipient, msg.as_string())
            else:
                raise ValueError("Either use_ssl or use_starttls must be True.")

            logging.info(f"Email sent to {recipient}")
            return True
        except Exception as e:
            logging.error(f"Error sending email: {e}")
            return False

@dataclass
class NotificationManager:
    observers: List[Notifier] = field(default_factory=list)
    rate_limit_seconds: float = 1.0  
    last_sent_time: float = field(default=0.0)

    def register(self, notifier: Notifier):
        logger.debug(f"Registering notifier: {notifier}")
        self.observers.append(notifier)

    def notify_all(self, recipient: str, subject: str, body_html: str, attachments: Optional[List[str]] = None, meta: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        results = {}
        now = time.time()
        elapsed = now - self.last_sent_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        for obs in self.observers:
            try:
                ok = obs.notify(recipient, subject, body_html, attachments, meta)
                results[type(obs).__name__] = ok
            except Exception as e:
                logger.exception(f"Notifier {type(obs).__name__} failed: {e}")
                results[type(obs).__name__] = False
        self.last_sent_time = time.time()
        return results

def render_template(template_str: str, context: Dict[str, Any]) -> str:
    return Template(template_str).render(**context)

def send_emails_from_csv(csv_path: str, manager: NotificationManager, subject_template: str, body_template: str, default_attachments: Optional[List[str]] = None):
    if default_attachments is None:
        default_attachments = []
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            recipient = row.get("email")
            name = row.get("name", "")
            attachment = row.get("attachment") or None
            attachments = [attachment] if attachment else default_attachments
            subject = render_template(subject_template, {"name": name, **row})
            body_html = render_template(body_template, {"name": name, **row})
            logger.info(f"Queueing send to: {recipient}")
            manager.notify_all(recipient, subject, body_html, attachments, meta=row)
            time.sleep(0.5)

if __name__ == "__main__":
    logger.info("Starting Notification System...")

    smtp_notifier = SMTPNotifier(
        smtp_server=SMTP_SERVER,
        smtp_port=SMTP_PORT,
        smtp_user=SMTP_USER,
        smtp_password=SMTP_PASSWORD,
        use_ssl=True,
        dry_run=DRY_RUN
    )

    manager = NotificationManager(rate_limit_seconds=RATE_LIMIT_SEC)
    manager.register(smtp_notifier)

    subj_tpl = "Invitation to Showcase Your Creativity, {{ name or 'Candidate' }}"
    body_tpl = """
    <html><body>
      <p>Hello {{ name or 'Candidate' }},</p>
      <p>Congratulations — please find the assessment attached. You have 7 days to complete it.</p>
      <p>Warm regards,<br/>Elitecode Hiring Team</p>
    </body></html>
    """

    send_emails_from_csv(CSV_FILE, manager, subj_tpl, body_tpl, default_attachments=[DEFAULT_ATTACHMENT])
    logger.info("All emails queued for sending!")
