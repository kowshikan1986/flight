# URGENT: Complete Gmail Email Setup for kowshikans@gmail.com

## Current Status
❌ Email NOT configured - App Password missing

## What You Need To Do NOW

### Step 1: Generate Gmail App Password (5 minutes)

1. **Open this link**: https://myaccount.google.com/apppasswords
   - You'll be asked to sign in to your Google account (kowshikans@gmail.com)

2. **If you see "App passwords" unavailable**:
   - First enable 2-Step Verification: https://myaccount.google.com/signinoptions/two-step-verification
   - Follow the prompts to set up 2-Step Verification
   - Then go back to: https://myaccount.google.com/apppasswords

3. **Generate the App Password**:
   - Click "Select app" → Choose "Mail"
   - Click "Select device" → Choose "Windows Computer" (or "Other")
   - Click "Generate"
   - **COPY the 16-character password** (looks like: abcd efgh ijkl mnop)
   - ⚠️ You won't be able to see this password again!

### Step 2: Update the .env File (1 minute)

1. Open the file: `d:\new_pro\hotel\.env`
2. Find this line:
   ```
   EMAIL_HOST_PASSWORD=REPLACE_WITH_YOUR_16_CHAR_APP_PASSWORD
   ```
3. Replace `REPLACE_WITH_YOUR_16_CHAR_APP_PASSWORD` with your App Password
4. **Remove all spaces** from the App Password
5. It should look like:
   ```
   EMAIL_HOST_PASSWORD=abcdefghijklmnop
   ```
6. **SAVE the file**

### Step 3: Restart Django Server (30 seconds)

1. In your terminal, press `CTRL+C` to stop the server
2. Run: `python manage.py runserver`

### Step 4: Test Email Configuration (1 minute)

Run the test script:
```bash
python test_email.py
```

If successful, you'll see:
```
✅ SUCCESS! Test email sent to kowshikans@gmail.com
```

Check your inbox (and spam folder) for the test email.

### Step 5: Test User Registration

1. Go to: http://127.0.0.1:8000/accounts/register/
2. Register a new user with YOUR email: kowshikans@gmail.com
3. Check your email for the confirmation link
4. Click the link to verify your account
5. Try logging in

---

## Troubleshooting

### Problem: "Username or password not accepted"
**Solution**: Make sure you're using the App Password, NOT your regular Gmail password

### Problem: "App passwords unavailable"
**Solution**: You need to enable 2-Step Verification first
- Go to: https://myaccount.google.com/signinoptions/two-step-verification

### Problem: Still not receiving emails
1. Check your spam/junk folder
2. Make sure you saved the .env file after updating
3. Make sure you restarted the Django server
4. Run the test script again: `python test_email.py`

### Problem: Test script shows error
Post the error message, and I'll help you fix it

---

## Quick Command Reference

```bash
# Test email configuration
python test_email.py

# Restart Django server
# Press CTRL+C first, then:
python manage.py runserver

# Check current email settings
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_booking.settings'); import django; django.setup(); from django.conf import settings; print('Backend:', settings.EMAIL_BACKEND); print('User:', settings.EMAIL_HOST_USER); print('Password set:', bool(settings.EMAIL_HOST_PASSWORD))"
```

---

## Current Configuration (as of now)

✅ Email Backend: SMTP (Gmail)
✅ Email Host: smtp.gmail.com  
✅ Email Port: 587
✅ Email User: kowshikans@gmail.com
❌ Email Password: **NOT SET - YOU NEED TO UPDATE THIS**

---

## After Setup is Complete

Once you've completed the steps above:
1. Test user registration with a real email
2. Check that confirmation emails are being delivered
3. Test the resend confirmation feature
4. Everything should work!

**Need help? Let me know what error you're getting!**
