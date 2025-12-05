import os
import time
import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict, Optional, Any
from jinja2 import Template


# Logging setup
logger = logging.getLogger(__name__)


class Notifier(ABC):
    """Abstract base class for notification handlers."""

    @abstractmethod
    def notify(
        self,
        recipient: str,
        subject: str,
        body_html: str,
        attachments: Optional[List[str]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send a notification to a recipient.

        Args:
            recipient: Email address of the recipient
            subject: Email subject line
            body_html: HTML body content
            attachments: Optional list of file paths to attach
            meta: Optional metadata dictionary

        Returns:
            True if notification was sent successfully, False otherwise
        """
        pass


class SMTPNotifier(Notifier):
    """SMTP-based email notifier for sending notifications."""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        use_ssl: bool = True,
        use_starttls: bool = False,
        timeout: int = 30,
        dry_run: bool = False,
    ):
        """Initialize SMTP notifier.

        Args:
            smtp_server: SMTP server hostname
            smtp_port: SMTP server port
            smtp_user: SMTP username (typically email address)
            smtp_password: SMTP password
            use_ssl: Use SSL connection (default: True)
            use_starttls: Use STARTTLS for TLS upgrade (default: False)
            timeout: Connection timeout in seconds
            dry_run: If True, log notifications without sending
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.use_ssl = use_ssl
        self.use_starttls = use_starttls
        self.timeout = timeout
        self.dry_run = dry_run

    def _build_message(
        self,
        recipient: str,
        subject: str,
        body_html: str,
        attachments: Optional[List[str]] = None,
    ) -> MIMEMultipart:
        """Build MIME message with optional attachments."""
        msg = MIMEMultipart()
        msg["From"] = self.smtp_user
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        if attachments:
            for file_path in attachments:
                try:
                    with open(file_path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        filename = os.path.basename(file_path)
                        part.add_header(
                            "Content-Disposition",
                            f'attachment; filename="{filename}"',
                        )
                        msg.attach(part)
                except Exception as e:
                    logger.warning(f"Failed to attach file {file_path}: {e}")

        return msg

    def notify(
        self,
        recipient: str,
        subject: str,
        body_html: str,
        attachments: Optional[List[str]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send email notification.

        Args:
            recipient: Email address of the recipient
            subject: Email subject line
            body_html: HTML body content
            attachments: Optional list of file paths to attach
            meta: Optional metadata (not used by SMTP notifier)

        Returns:
            True if email was sent successfully, False otherwise
        """
        msg = self._build_message(recipient, subject, body_html, attachments)

        if self.dry_run:
            logger.info(
                f"[DRY-RUN] Would send email to {recipient} with subject '{subject}'"
            )
            return True

        try:
            if self.use_ssl:
                with smtplib.SMTP_SSL(
                    self.smtp_server, self.smtp_port, timeout=self.timeout
                ) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_user, recipient, msg.as_string())
            elif self.use_starttls:
                with smtplib.SMTP(
                    self.smtp_server, self.smtp_port, timeout=self.timeout
                ) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_user, recipient, msg.as_string())
            else:
                raise ValueError("Either use_ssl or use_starttls must be True.")

            logger.info(f"Email sent successfully to {recipient}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed for {recipient}: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email to {recipient}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email to {recipient}: {e}")
            return False


@dataclass
class NotificationManager:
    """Manager for coordinating multiple notification handlers.

    This class implements the Observer pattern, allowing multiple
    notification handlers to be registered and notified simultaneously.
    """

    observers: List[Notifier] = field(default_factory=list)
    rate_limit_seconds: float = 1.0
    last_sent_time: float = field(default=0.0)

    def register(self, notifier: Notifier) -> None:
        """Register a new notification handler.

        Args:
            notifier: Notifier instance to register
        """
        logger.debug(f"Registering notifier: {type(notifier).__name__}")
        self.observers.append(notifier)

    def notify_all(
        self,
        recipient: str,
        subject: str,
        body_html: str,
        attachments: Optional[List[str]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, bool]:
        """Send notification through all registered handlers.

        Applies rate limiting between notifications and attempts to send
        through all registered notifiers.

        Args:
            recipient: Email address of the recipient
            subject: Email subject line
            body_html: HTML body content
            attachments: Optional list of file paths to attach
            meta: Optional metadata to pass to handlers

        Returns:
            Dictionary mapping notifier names to success status
        """
        results = {}

        # Apply rate limiting
        now = time.time()
        elapsed = now - self.last_sent_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)

        # Notify all observers
        for obs in self.observers:
            notifier_name = type(obs).__name__
            try:
                ok = obs.notify(recipient, subject, body_html, attachments, meta)
                results[notifier_name] = ok
            except Exception as e:
                logger.exception(f"Notifier {notifier_name} failed: {e}")
                results[notifier_name] = False

        self.last_sent_time = time.time()
        return results


def render_template(template_str: str, context: Dict[str, Any]) -> str:
    """Render a Jinja2 template with the given context.

    Args:
        template_str: Template string with Jinja2 syntax
        context: Dictionary of variables to use in template

    Returns:
        Rendered template string
    """
    return Template(template_str).render(**context)
