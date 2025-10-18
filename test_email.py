#!/usr/bin/env python
"""Quick test script to verify email configuration."""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_booking.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def test_email():
    """Send a test email to verify configuration."""
    print("=" * 60)
    print("TESTING EMAIL CONFIGURATION")
    print("=" * 60)
    print(f"Email Backend: {settings.EMAIL_BACKEND}")
    print(f"Email Host: {settings.EMAIL_HOST}")
    print(f"Email Port: {settings.EMAIL_PORT}")
    print(f"Email User: {settings.EMAIL_HOST_USER}")
    print(f"Default From: {settings.DEFAULT_FROM_EMAIL}")
    print(f"Use TLS: {settings.EMAIL_USE_TLS}")
    print("=" * 60)
    
    # Check if password is set
    if not settings.EMAIL_HOST_PASSWORD or settings.EMAIL_HOST_PASSWORD == "REPLACE_WITH_YOUR_16_CHAR_APP_PASSWORD":
        print("\n❌ ERROR: You need to set your Gmail App Password!")
        print("\nSteps to fix:")
        print("1. Go to: https://myaccount.google.com/apppasswords")
        print("2. Generate a new App Password")
        print("3. Update EMAIL_HOST_PASSWORD in .env file")
        print("4. Run this test again")
        return False
    
    try:
        print("\n📧 Sending test email...")
        send_mail(
            subject='WanderWise - Email Configuration Test',
            message='This is a test email from your WanderWise hotel booking system. If you receive this, your email configuration is working correctly!',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.EMAIL_HOST_USER],
            fail_silently=False,
        )
        print(f"✅ SUCCESS! Test email sent to {settings.EMAIL_HOST_USER}")
        print("\nCheck your inbox (and spam folder) for the test email.")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: Failed to send email")
        print(f"Error details: {str(e)}")
        print("\nCommon issues:")
        print("1. Make sure you're using an App Password, not your Gmail password")
        print("2. Enable 2-Step Verification in your Google Account")
        print("3. Check if 'Less secure app access' is blocking the connection")
        print("4. Verify your Gmail address is correct")
        return False

if __name__ == '__main__':
    test_email()
