# Email Configuration Guide for WanderWise Hotel Booking System

## Problem
Users are not receiving email confirmation after registration, which prevents them from logging in.

## Root Cause
The application is using Django's console email backend by default, which only prints emails to the console instead of actually sending them.

## Solutions

### 1. Development Setup (Console Backend)
For development and testing, emails will be printed to the console where you run the Django server.

**Configuration in .env file:**
```
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

**To test:**
1. Start the Django development server: `python manage.py runserver`
2. Register a new user
3. Check the console/terminal where the server is running
4. You'll see the email content printed there
5. Copy the confirmation URL and paste it in your browser

### 2. Production Setup with Gmail

**Step 1: Enable 2-Factor Authentication on Gmail**
1. Go to your Google Account settings
2. Enable 2-Factor Authentication

**Step 2: Generate App Password**
1. Go to Google Account → Security → 2-Step Verification → App passwords
2. Create an app password for "Django Application"
3. Copy the 16-character password

**Step 3: Update .env file:**
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-16-character-app-password
DEFAULT_FROM_EMAIL=WanderWise <your-email@gmail.com>
```

### 3. Production Setup with SendGrid

**Step 1: Create SendGrid Account**
1. Sign up at https://sendgrid.com
2. Verify your sender identity
3. Generate an API key

**Step 2: Update .env file:**
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your-sendgrid-api-key
DEFAULT_FROM_EMAIL=WanderWise <noreply@yourdomain.com>
```

### 3b. Production Setup on Azure App Service

If you're deploying to Azure App Service, configure the environment variables above through the App Service settings so the production settings file can load them at boot.

**Option A: Azure Portal**
1. Navigate to your App Service → **Settings** → **Configuration** → **Application settings**.
2. Add each key/value pair (for example `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`).
3. Select **Save** and allow the app to restart so the new settings take effect.

**Option B: Azure CLI**
```bash
az webapp config appsettings set \
   --resource-group <your-resource-group> \
   --name <your-app-service-name> \
   --settings \
      EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend" \
      EMAIL_HOST="smtp.sendgrid.net" \
      EMAIL_PORT="587" \
      EMAIL_USE_TLS="true" \
      EMAIL_HOST_USER="apikey" \
      EMAIL_HOST_PASSWORD="<sendgrid-api-key>" \
      DEFAULT_FROM_EMAIL="WanderWise <noreply@yourdomain.com>"
```

> **Important:** The production settings raise an error if the console email backend is used or if SMTP credentials are missing. Double-check your App Service configuration before deploying.

### 4. File-based Backend (Testing)
For testing without actual email sending:

```
EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend
EMAIL_FILE_PATH=emails/
```

This will save emails as files in the `emails/` directory.

## Testing the Email System

### Method 1: Using Django Shell
```python
python manage.py shell
```

```python
from django.core.mail import send_mail
from django.conf import settings

# Test basic email sending
send_mail(
    'Test Subject',
    'Test message.',
    settings.DEFAULT_FROM_EMAIL,
    ['recipient@example.com'],
    fail_silently=False,
)
```

### Method 2: Using the Registration Flow
1. Register a new user with a real email address
2. Check your email inbox (and spam folder)
3. Click the confirmation link

### Method 3: Using the Resend Confirmation Feature
1. Go to the login page
2. Click "Resend confirmation" link
3. Enter your email address
4. Check your inbox

## Troubleshooting

### Common Issues:

1. **Gmail "Less secure app access" error**
   - Solution: Use App Passwords instead of your regular Gmail password

2. **Emails going to spam folder**
   - Solution: Set up proper SPF/DKIM records for your domain
   - Use a reputable email service like SendGrid

3. **Connection timeout errors**
   - Check firewall settings
   - Verify EMAIL_HOST and EMAIL_PORT settings
   - Ensure EMAIL_USE_TLS is set correctly

4. **Authentication failed**
   - Double-check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
   - For Gmail, ensure you're using App Password, not regular password

### Testing Commands:

```bash
# Check if emails are being sent (look for any error messages)
python manage.py shell -c "
from accounts.services import send_email_confirmation
from accounts.models import User
from django.test import RequestFactory
user = User.objects.first()
request = RequestFactory().get('/')
request.META['HTTP_HOST'] = 'localhost:8000'
send_email_confirmation(request, user)
"

# Check Django configuration
python manage.py shell -c "
from django.conf import settings
print('EMAIL_BACKEND:', settings.EMAIL_BACKEND)
print('EMAIL_HOST:', settings.EMAIL_HOST)
print('EMAIL_PORT:', settings.EMAIL_PORT)
print('DEFAULT_FROM_EMAIL:', settings.DEFAULT_FROM_EMAIL)
"
```

## Security Notes

1. **Never commit .env file to version control**
2. **Use environment variables in production**
3. **Use App Passwords for Gmail, not your regular password**
4. **Consider using dedicated email services for production**
5. **Set up proper DNS records (SPF, DKIM, DMARC) for your domain**

## Next Steps

1. Choose your email configuration method
2. Update the .env file with your settings
3. Restart the Django server
4. Test the email functionality
5. Monitor email delivery and troubleshoot as needed