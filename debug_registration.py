"""Debug registration flow to see exactly what happens."""

import os
import django
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_booking.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from accounts.models import User

def test_full_registration():
    """Test complete registration flow and capture email output."""
    
    print("🔍 TESTING FULL REGISTRATION FLOW")
    print("=" * 60)
    
    # Delete any existing test user
    test_email = "regtest@example.com"
    User.objects.filter(email=test_email).delete()
    print(f"✅ Cleaned up any existing user: {test_email}")
    
    # Create test client
    client = Client()
    
    # Registration data
    registration_data = {
        'email': test_email,
        'first_name': 'Registration',
        'last_name': 'Test',
        'phone_number': '+1234567890',
        'password': 'TestPass123!',
        'confirm_password': 'TestPass123!',
        'marketing_opt_in': False,
        # Profile form fields (empty but valid)
        'date_of_birth': '',
        'address_line1': '',
        'address_line2': '', 
        'city': '',
        'state': '',
        'country': '',
        'postcode': '',
        'emergency_contact_name': '',
        'emergency_contact_phone': '',
    }
    
    print(f"📝 Registering user with email: {test_email}")
    print("💡 WATCH THE TERMINAL WHERE 'python manage.py runserver' IS RUNNING!")
    print("   The activation email should appear there.")
    print()
    
    # Submit registration
    response = client.post(reverse('accounts:register'), registration_data, follow=True)
    
    print(f"Response status code: {response.status_code}")
    
    if response.status_code == 200:
        # Check if user was created
        try:
            user = User.objects.get(email=test_email)
            print(f"✅ User created: {user.email}")
            print(f"   - Email verified: {user.email_verified}")
            print(f"   - Is active: {user.is_active}")
            
            # Check the final URL
            print(f"   - Final URL: {response.wsgi_request.path}")
            
            # Check if there are any form errors
            if hasattr(response, 'context') and response.context:
                form = response.context.get('form')
                if form and hasattr(form, 'errors') and form.errors:
                    print(f"❌ Form errors: {form.errors}")
                
                profile_form = response.context.get('profile_form')
                if profile_form and hasattr(profile_form, 'errors') and profile_form.errors:
                    print(f"❌ Profile form errors: {profile_form.errors}")
            
            print()
            print("🎯 TO ACTIVATE THIS USER MANUALLY:")
            print(f"   python manage.py activate_users {test_email}")
            
        except User.DoesNotExist:
            print("❌ User was not created - registration failed")
            print("Response content:")
            print(response.content.decode()[:500] + "..." if len(response.content) > 500 else response.content.decode())
    else:
        print(f"❌ Registration failed with status {response.status_code}")
        print("Response content:")
        print(response.content.decode()[:500] + "..." if len(response.content) > 500 else response.content.decode())

if __name__ == '__main__':
    test_full_registration()