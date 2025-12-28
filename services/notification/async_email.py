"""
Async email delivery system for WTF notifications.

This module provides asynchronous email delivery with:
- Gmail SMTP with app password support
- Batch processing for high throughput
- Retry logic with exponential backoff
- Rate limiting
- Connection pooling
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Try to import async libraries
try:
    import aiosmtplib

    ASYNC_SMTP_AVAILABLE = True
except ImportError:
    ASYNC_SMTP_AVAILABLE = False
    logging.warning("aiosmtplib not installed. Async email will fall back to sync.")

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Email message data structure."""

    to: str
    subject: str
    html_body: str
    text_body: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    notification_id: Optional[int] = None


@dataclass
class EmailResult:
    """Result of email send attempt."""

    success: bool
    recipient: str
    error: Optional[str] = None
    sent_at: Optional[datetime] = None
    provider: Optional[str] = None


class AsyncEmailProvider(ABC):
    """Abstract base class for async email providers."""

    @abstractmethod
    async def send_email(self, message: EmailMessage) -> EmailResult:
        """Send a single email."""
        pass

    @abstractmethod
    async def send_batch(self, messages: List[EmailMessage]) -> List[EmailResult]:
        """Send multiple emails in a batch."""
        pass

    @abstractmethod
    async def close(self):
        """Close connections and cleanup."""
        pass


class AsyncSMTPProvider(AsyncEmailProvider):
    """Async SMTP email provider using aiosmtplib."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: int = 30,
        from_email: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.timeout = timeout
        self.from_email = from_email or username
        self._pool: List[aiosmtplib.SMTP] = []
        self._pool_size = 10
        self._semaphore = asyncio.Semaphore(self._pool_size)

    async def _get_connection(self) -> aiosmtplib.SMTP:
        """Get or create SMTP connection from pool."""
        if not ASYNC_SMTP_AVAILABLE:
            raise ImportError("aiosmtplib is required for async SMTP")

        if self._pool:
            return self._pool.pop()

        # Create new connection
        if self.use_ssl:
            smtp = aiosmtplib.SMTP(
                hostname=self.host, port=self.port, use_tls=True, timeout=self.timeout
            )
        else:
            smtp = aiosmtplib.SMTP(
                hostname=self.host, port=self.port, timeout=self.timeout
            )

        await smtp.connect()

        if self.use_tls and not self.use_ssl:
            await smtp.starttls()

        await smtp.login(self.username, self.password)
        return smtp

    async def _return_connection(self, smtp: aiosmtplib.SMTP):
        """Return connection to pool or close if pool is full."""
        if len(self._pool) < self._pool_size:
            self._pool.append(smtp)
        else:
            try:
                await smtp.quit()
            except Exception:
                pass

    def _build_message(self, message: EmailMessage) -> MIMEMultipart:
        """Build MIME message."""
        msg = MIMEMultipart("alternative")
        msg["From"] = message.from_email or self.from_email
        msg["To"] = message.to
        msg["Subject"] = message.subject

        if message.reply_to:
            msg["Reply-To"] = message.reply_to

        # Add text and HTML parts
        if message.text_body:
            msg.attach(MIMEText(message.text_body, "plain"))

        msg.attach(MIMEText(message.html_body, "html"))

        return msg

    async def send_email(self, message: EmailMessage) -> EmailResult:
        """Send a single email."""
        async with self._semaphore:
            try:
                smtp = await self._get_connection()

                try:
                    msg = self._build_message(message)
                    await smtp.send_message(msg)

                    return EmailResult(
                        success=True,
                        recipient=message.to,
                        sent_at=datetime.utcnow(),
                        provider="smtp",
                    )

                finally:
                    await self._return_connection(smtp)

            except Exception as e:
                logger.error(f"Failed to send email to {message.to}: {e}")
                return EmailResult(
                    success=False, recipient=message.to, error=str(e), provider="smtp"
                )

    async def send_batch(self, messages: List[EmailMessage]) -> List[EmailResult]:
        """Send multiple emails concurrently."""
        tasks = [self.send_email(msg) for msg in messages]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        final_results: List[EmailResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(
                    EmailResult(
                        success=False,
                        recipient=messages[i].to,
                        error=str(result),
                        provider="smtp",
                    )
                )
            elif isinstance(result, EmailResult):
                final_results.append(result)

        return final_results

    async def close(self):
        """Close all connections in pool."""
        for smtp in self._pool:
            try:
                await smtp.quit()
            except Exception:
                pass
        self._pool.clear()


class BatchEmailProcessor:
    """Process emails in batches with rate limiting and retry logic."""

    def __init__(
        self,
        provider: AsyncEmailProvider,
        batch_size: int = 100,
        max_concurrent_batches: int = 10,
        rate_limit_per_second: float = 10.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_multiplier: float = 2.0,
    ):
        self.provider = provider
        self.batch_size = batch_size
        self.max_concurrent_batches = max_concurrent_batches
        self.rate_limit_per_second = rate_limit_per_second
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_multiplier = retry_multiplier

        self._semaphore = asyncio.Semaphore(max_concurrent_batches)
        self._last_send_time = datetime.utcnow()

    async def _rate_limit(self):
        """Apply rate limiting."""
        if self.rate_limit_per_second > 0:
            min_interval = 1.0 / self.rate_limit_per_second
            now = datetime.utcnow()
            elapsed = (now - self._last_send_time).total_seconds()

            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)

            self._last_send_time = datetime.utcnow()

    async def _send_with_retry(
        self, message: EmailMessage, attempt: int = 0
    ) -> EmailResult:
        """Send email with retry logic."""
        result = await self.provider.send_email(message)

        if result.success or attempt >= self.max_retries:
            return result

        # Exponential backoff
        delay = self.retry_delay * (self.retry_multiplier**attempt)
        logger.info(
            f"Retrying {message.to} (attempt {attempt + 1}/{self.max_retries}) "
            f"after {delay:.1f}s"
        )
        await asyncio.sleep(delay)

        return await self._send_with_retry(message, attempt + 1)

    async def _process_batch(self, batch: List[EmailMessage]) -> List[EmailResult]:
        """Process a single batch of emails."""
        async with self._semaphore:
            await self._rate_limit()

            # Send batch with retries
            tasks = [self._send_with_retry(msg) for msg in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle exceptions
            final_results: List[EmailResult] = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    final_results.append(
                        EmailResult(
                            success=False,
                            recipient=batch[i].to,
                            error=str(result),
                            provider="unknown",
                        )
                    )
                elif isinstance(result, EmailResult):
                    final_results.append(result)

            return final_results

    async def send_all(
        self,
        messages: List[EmailMessage],
        on_batch_complete: Optional[
            Callable[[int, int, List[EmailResult]], None]
        ] = None,
    ) -> List[EmailResult]:
        """
        Send all messages in batches.

        Args:
            messages: List of email messages to send
            on_batch_complete: Optional callback called after each batch

        Returns:
            List of email results
        """
        if not messages:
            return []

        # Split into batches
        batches = [
            messages[i : i + self.batch_size]
            for i in range(0, len(messages), self.batch_size)
        ]

        logger.info(
            f"Processing {len(messages)} emails in {len(batches)} batches "
            f"(batch_size={self.batch_size}, "
            f"max_concurrent={self.max_concurrent_batches})"
        )

        all_results = []

        for i, batch in enumerate(batches):
            logger.info(
                f"Processing batch {i + 1}/{len(batches)} ({len(batch)} emails)"
            )

            results = await self._process_batch(batch)
            all_results.extend(results)

            # Call callback
            if on_batch_complete:
                try:
                    on_batch_complete(i + 1, len(batches), results)
                except Exception as e:
                    logger.error(f"Batch callback error: {e}")

            # Log batch stats
            success_count = sum(1 for r in results if r.success)
            logger.info(
                f"Batch {i + 1} complete: {success_count}/{len(results)} successful"
            )

        # Summary
        total_success = sum(1 for r in all_results if r.success)
        total_failed = len(all_results) - total_success

        logger.info(
            f"✓ All batches complete: {total_success} sent, {total_failed} failed"
        )

        return all_results

    async def close(self):
        """Close provider connections."""
        await self.provider.close()


def create_email_provider(**kwargs) -> AsyncEmailProvider:
    """
    Factory function to create Gmail SMTP email provider.

    Args:
        **kwargs: SMTP configuration (host, port, username, password, etc.)

    Returns:
        AsyncSMTPProvider instance configured for Gmail

    Example:
        provider = create_email_provider(
            host='smtp.gmail.com',
            port=465,
            username='your-email@gmail.com',
            password='your-app-password',
            use_ssl=True
        )
    """
    return AsyncSMTPProvider(
        host=kwargs.get("host", os.getenv("SMTP_SERVER", "smtp.gmail.com")),
        port=kwargs.get("port", int(os.getenv("SMTP_PORT", "465"))),
        username=kwargs.get("username", os.getenv("SMTP_USER", "")),
        password=kwargs.get("password", os.getenv("SMTP_PASSWORD", "")),
        use_ssl=kwargs.get("use_ssl", os.getenv("USE_SSL", "true").lower() == "true"),
        use_tls=kwargs.get(
            "use_tls", os.getenv("USE_STARTTLS", "false").lower() == "true"
        ),
        timeout=kwargs.get("timeout", 30),
        from_email=kwargs.get("from_email", os.getenv("SMTP_USER", "")),
    )
