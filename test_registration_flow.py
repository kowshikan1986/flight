"""Test user registration and email confirmation flow."""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_booking.settings')
django.setup()

from django.test import RequestFactory
from accounts.models import User
from accounts.services import send_email_confirmation


def test_registration_email_flow():
    """Test the complete registration email flow."""
    print("=" * 60)
    print("TESTING USER REGISTRATION EMAIL FLOW")
    print("=" * 60)
    
    # Create a test user (simulating registration)
    email = "testuser@example.com"
    
    # Check if user already exists
    if User.objects.filter(email=email).exists():
        print(f"Deleting existing user: {email}")
        User.objects.filter(email=email).delete()
    
    # Create user (like the registration form does)
    user = User.objects.create_user(
        email=email,
        password="testpass123",
        first_name="Test",
        last_name="User",
        email_verified=False
    )
    
    print(f"✅ Created user: {user.email}")
    print(f"   - Email verified: {user.email_verified}")
    print(f"   - Is active: {user.is_active}")
    
    # Create a mock request (needed for building absolute URLs)
    request_factory = RequestFactory()
    request = request_factory.get('/')
    request.META['HTTP_HOST'] = 'localhost:8000'
    
    print("\n📧 Sending confirmation email...")
    print("👀 WATCH THE OUTPUT BELOW - THIS IS YOUR ACTIVATION EMAIL:")
    print("=" * 60)
    
    # Send the confirmation email
    try:
        send_email_confirmation(request, user)
        print("=" * 60)
        print("✅ SUCCESS! Email sent to console.")
        print(f"👆 The activation link is in the email content above!")
        print(f"   Look for a line starting with: http://localhost:8000/accounts/confirm-email/")
        
    except Exception as e:
        print(f"❌ ERROR sending email: {str(e)}")
    
    # Show user status
    print(f"\n📋 User Status:")
    print(f"   - Email: {user.email}")
    print(f"   - Verified: {user.email_verified}")
    print(f"   - Active: {user.is_active}")
    
    print(f"\n💡 To activate this user manually, run:")
    print(f"   python manage.py activate_users {user.email}")


if __name__ == '__main__':
    test_registration_email_flow()