#!/usr/bin/env python3
"""
Test batch email sending functionality.

Usage:
    python scripts/test_batch_email.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from services.notification.async_email import (
    create_email_provider,
    BatchEmailProcessor,
    EmailMessage,
)

# Load environment variables
load_dotenv()


async def test_batch_email():
    """Test batch email sending."""
    print("=" * 60)
    print("Testing Batch Email Send")
    print("=" * 60)

    # Get configuration
    email_config = {
        "host": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "465")),
        "username": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "use_ssl": os.getenv("USE_SSL", "true").lower() == "true",
        "use_tls": os.getenv("USE_STARTTLS", "false").lower() == "true",
    }

    batch_config = {
        "batch_size": int(os.getenv("EMAIL_BATCH_SIZE", "100")),
        "max_concurrent_batches": int(os.getenv("EMAIL_MAX_CONCURRENT_BATCHES", "10")),
        "rate_limit_per_second": float(
            os.getenv("EMAIL_RATE_LIMIT_PER_SECOND", "10.0")
        ),
        "max_retries": int(os.getenv("EMAIL_MAX_RETRIES", "3")),
    }

    # Get recipients from environment
    recipients_str = os.getenv("NOTIFICATION_RECIPIENTS", "")
    recipients = [
        r.strip().strip("'\"") for r in recipients_str.split(",") if r.strip()
    ]

    if not recipients:
        print("❌ No recipients found in NOTIFICATION_RECIPIENTS")
        return False

    print(f"Recipients: {recipients}")
    print(f"Batch Size: {batch_config['batch_size']}")
    print(f"Rate Limit: {batch_config['rate_limit_per_second']} emails/sec")
    print()

    # Create provider and batch processor
    try:
        provider = create_email_provider(**email_config)
        processor = BatchEmailProcessor(provider, **batch_config)
        print("✅ Email provider and batch processor created")
    except Exception as e:
        print(f"❌ Failed to create email system: {e}")
        return False

    # Create test messages
    messages = []
    for recipient in recipients:
        messages.append(
            EmailMessage(
                to=recipient,
                subject="🧪 WTF Batch Email Test",
                html_body=f"""
                <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background-color: #667eea; color: white; padding: 20px; text-align: center;">
                        <h2>✅ Batch Email Test</h2>
                    </div>
                    <div style="padding: 20px;">
                        <p>Hi there!</p>
                        <p>This is a test email sent via the <strong>WTF notification system</strong> using batch processing.</p>
                        <div style="background-color: #f0f4ff; padding: 15px; border-radius: 5px; margin: 15px 0;">
                            <p style="margin: 5px 0;"><strong>📧 Recipient:</strong> {recipient}</p>
                            <p style="margin: 5px 0;"><strong>🔧 Batch Size:</strong> {batch_config['batch_size']} emails</p>
                            <p style="margin: 5px 0;"><strong>⚡ Rate Limit:</strong> {batch_config['rate_limit_per_second']} emails/sec</p>
                        </div>
                        <p>If you're reading this, the notification system is working correctly! 🎉</p>
                        <hr>
                        <p style="color: #666; font-size: 12px;">
                            Sent from: {email_config['username']}
                        </p>
                    </div>
                </body>
                </html>
                """,
            )
        )

    print(f"\nSending {len(messages)} test emails...")
    print("-" * 60)

    # Send batch
    try:
        results = await processor.send_all(messages)

        # Count results
        success_count = sum(1 for r in results if r.success)
        failed_count = len(results) - success_count

        print("-" * 60)
        print("\n✅ Batch send complete!")
        print(f"   Total: {len(results)} emails")
        print(f"   Sent: {success_count}")
        print(f"   Failed: {failed_count}")

        # Show individual results
        if failed_count > 0:
            print("\nFailed emails:")
            for result in results:
                if not result.success:
                    print(f"   ❌ {result.recipient}: {result.error}")

        return failed_count == 0

    except Exception as e:
        print(f"❌ Exception during batch send: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        await processor.close()


def main():
    print("\n" + "=" * 60)
    print("WTF Notification System - Batch Email Test")
    print("=" * 60 + "\n")

    success = asyncio.run(test_batch_email())

    print("\n" + "=" * 60)
    if success:
        print("✅ Batch email test PASSED")
        print("The notification system is ready for production!")
    else:
        print("❌ Batch email test FAILED")
        print("Please check the errors above")
    print("=" * 60 + "\n")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
