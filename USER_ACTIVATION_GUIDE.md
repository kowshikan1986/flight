# 🚀 USER ACTIVATION GUIDE - Two Methods

## Current Status: Console Email Backend (Active)
✅ Emails will be printed to your terminal/console  
✅ No Gmail setup required for testing

---

## METHOD 1: View Activation Link in Console (Recommended for Testing)

### Step 1: Start the Django Server
```bash
python manage.py runserver
```

### Step 2: Register a New User
1. Go to: http://127.0.0.1:8000/accounts/register/
2. Fill in the registration form
3. Submit the form

### Step 3: Get Activation Link from Console
**Look at the terminal where Django is running!** You'll see output like:

```
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Subject: Confirm your WanderWise account
From: noreply@travel-booking.local
To: user@example.com
Date: Sat, 12 Oct 2025 21:15:30 -0000
Message-ID: <...>

Hi User,

Thanks for creating an account with WanderWise. Before you can sign in, we just need to confirm your email address.

Please click the link below to verify your account:
http://127.0.0.1:8000/accounts/confirm-email/MQ/abc123-xyz789/

If you didn't create this account, you can safely ignore this email.

See you soon,
The WanderWise team
```

### Step 4: Copy and Use the Activation Link
1. **Copy the URL** (the line starting with `http://127.0.0.1:8000/accounts/confirm-email/`)
2. **Paste it in your browser**
3. Your account is now activated! ✅

---

## METHOD 2: Manually Activate Users via Command Line

If you missed the console output or want to quickly activate users:

### List All Unverified Users
```bash
python manage.py activate_users --list-unverified
```

This will show:
```
Found 3 unverified users:
  - user1@example.com (joined: 2025-10-12 20:30:15)
  - user2@example.com (joined: 2025-10-12 20:35:42)
  - test@example.com (joined: 2025-10-12 21:00:10)
```

### Activate One User
```bash
python manage.py activate_users user@example.com
```

### Activate Multiple Users at Once
```bash
python manage.py activate_users user1@example.com user2@example.com user3@example.com
```

Output:
```
✅ Activated: user1@example.com
✅ Activated: user2@example.com
✅ Activated: user3@example.com

🎉 Successfully activated 3 user(s)!
```

---

## 🔧 TROUBLESHOOTING

### Problem: Can't see email in console
**Solution**: Make sure you're looking at the terminal window where `python manage.py runserver` is running

### Problem: Console output scrolled away
**Solution**: 
1. Use Method 2 to list users: `python manage.py activate_users --list-unverified`
2. Manually activate them: `python manage.py activate_users email@example.com`

### Problem: Want to resend activation email
**Solution**:
1. Go to: http://127.0.0.1:8000/accounts/resend-confirmation/
2. Enter the user's email
3. Check the console for the new activation link

---

## 📧 SWITCHING TO REAL EMAIL (Gmail Setup)

When you're ready to send real emails to users:

### Step 1: Generate Gmail App Password
1. Go to: https://myaccount.google.com/apppasswords
2. Sign in with: kowshikans@gmail.com
3. Enable 2-Step Verification if needed
4. Generate an App Password
5. Copy the 16-character password

### Step 2: Update .env File
1. Open: `d:\new_pro\hotel\.env`
2. Find line 13, comment it out:
   ```
   # EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
   ```
3. Find lines 15-22, uncomment them:
   ```
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=true
   EMAIL_HOST_USER=kowshikans@gmail.com
   EMAIL_HOST_PASSWORD=your_16_char_app_password_here
   DEFAULT_FROM_EMAIL=WanderWise <kowshikans@gmail.com>
   ```
4. Replace `your_16_char_app_password_here` with your actual App Password
5. Save the file

### Step 3: Restart Django Server
```bash
# Press CTRL+C to stop the server
python manage.py runserver
```

### Step 4: Test Real Email
```bash
python test_email.py
```

You should see:
```
✅ SUCCESS! Test email sent to kowshikans@gmail.com
```

---

## 🎯 QUICK COMMAND REFERENCE

```bash
# Start server
python manage.py runserver

# List unverified users
python manage.py activate_users --list-unverified

# Activate a user
python manage.py activate_users user@example.com

# Test email configuration
python test_email.py
```

---

## ✅ RECOMMENDED WORKFLOW FOR NOW

1. Keep console email backend (current setup)
2. Register users normally through the website
3. Check the console for activation links
4. Copy/paste the activation link to activate accounts

OR

1. Register users normally
2. Run: `python manage.py activate_users --list-unverified`
3. Run: `python manage.py activate_users user@example.com`

**This way users can log in immediately without email setup!** 🚀
