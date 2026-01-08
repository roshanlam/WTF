#!/usr/bin/env python3
"""
Test email sending functionality.

Usage:
    python scripts/test_email.py recipient@example.com
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from services.notification.async_email import create_email_provider, EmailMessage

# Load environment variables
load_dotenv()


async def test_email_send(recipient: str):
    """Test sending an email."""
    print("=" * 60)
    print("Testing Email Send")
    print("=" * 60)

    # Get SMTP configuration
    smtp_config = {
        "host": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "465")),
        "username": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "use_ssl": os.getenv("USE_SSL", "true").lower() == "true",
        "use_tls": os.getenv("USE_STARTTLS", "false").lower() == "true",
    }

    print(f"SMTP Server: {smtp_config['host']}:{smtp_config['port']}")
    print(f"SMTP User: {smtp_config['username']}")
    print(f"Use SSL: {smtp_config['use_ssl']}")
    print(f"Recipient: {recipient}")
    print()

    # Check credentials
    if not smtp_config["username"] or not smtp_config["password"]:
        print("❌ ERROR: SMTP_USER or SMTP_PASSWORD not set in .env file")
        print("Please configure your Gmail credentials.")
        return False

    # Create email provider
    print("Creating email provider...")
    try:
        provider = create_email_provider(**smtp_config)
        print("✅ Email provider created successfully")
    except Exception as e:
        print(f"❌ Failed to create email provider: {e}")
        return False

    # Create test email
    test_message = EmailMessage(
        to=recipient,
        subject="🧪 WTF Email Test",
        html_body="""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #4CAF50; color: white; padding: 20px; text-align: center;">
                <h2>✅ Email Test Successful!</h2>
            </div>
            <div style="padding: 20px;">
                <p>This is a test email from the WTF Free Food Detection System.</p>
                <p>If you're reading this, email sending is working correctly!</p>
                <hr>
                <p style="color: #666; font-size: 12px;">
                    Sent from: {sender}
                </p>
            </div>
        </body>
        </html>
        """.format(sender=smtp_config["username"]),
        text_body="This is a test email from WTF. Email is working!",
    )

    # Send test email
    print("\nSending test email...")
    try:
        result = await provider.send_email(test_message)

        if result.success:
            print(f"✅ Email sent successfully to {recipient}")
            print(f"   Sent at: {result.sent_at}")
            print(f"   Provider: {result.provider}")
            return True
        else:
            print(f"❌ Failed to send email to {recipient}")
            print(f"   Error: {result.error}")
            return False

    except Exception as e:
        print(f"❌ Exception while sending email: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Cleanup
        await provider.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_email.py recipient@example.com")
        print("\nExample:")
        print("  python scripts/test_email.py elitecodehiring@gmail.com")
        sys.exit(1)

    recipient = sys.argv[1]

    # Run async test
    success = asyncio.run(test_email_send(recipient))

    print("\n" + "=" * 60)
    if success:
        print("✅ Email test PASSED")
        print("Your email configuration is working correctly!")
    else:
        print("❌ Email test FAILED")
        print("Please check your SMTP configuration in .env file")
        print("\nCommon issues:")
        print("1. Wrong Gmail app password")
        print("2. 2-Step Verification not enabled on Google account")
        print("3. App password not generated")
        print("\nGet app password: https://myaccount.google.com/apppasswords")
    print("=" * 60)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
