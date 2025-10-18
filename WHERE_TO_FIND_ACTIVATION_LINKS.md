# 👀 WHERE TO FIND ACTIVATION LINKS

## ✅ The Email System IS Working!

I just tested it and the activation emails **ARE** being printed to the console. Here's how to find them:

---

## 🎯 STEP BY STEP: How to See Activation Links

### Step 1: Make Sure Django Server is Running
Open a terminal and run:
```bash
python manage.py runserver
```

**IMPORTANT:** Keep this terminal window visible! This is where activation links appear.

### Step 2: Register a New User
1. Go to: http://127.0.0.1:8000/accounts/register/
2. Fill out the registration form
3. Click "Create Account"

### Step 3: Look at the Django Server Terminal
**Immediately after registration**, look at the terminal where `python manage.py runserver` is running.

You'll see output like this:
```
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Subject: Confirm your WanderWise account
From: noreply@travel-booking.local
To: newuser@example.com

Hi User,

Please click the link below to verify your account:
http://localhost:8000/accounts/confirm-email/MTE/abc123-xyz789/

If you didn't create this account, you can safely ignore this email.
```

### Step 4: Copy the Activation URL
Look for the line that starts with:
```
http://localhost:8000/accounts/confirm-email/
```

Copy this entire URL and paste it in your browser!

---

## 🔧 TROUBLESHOOTING

### Problem: "I don't see any email output"

**Check These:**

1. **Are you looking at the RIGHT terminal?**
   - The email appears in the terminal running `python manage.py runserver`
   - NOT in a different terminal window

2. **Did the output scroll away?**
   - If you missed it, use the manual activation method:
   ```bash
   python manage.py activate_users --list-unverified
   python manage.py activate_users user@example.com
   ```

3. **Is the console backend active?**
   - Run this to check:
   ```bash
   python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'travel_booking.settings'); import django; django.setup(); from django.conf import settings; print('Email Backend:', settings.EMAIL_BACKEND)"
   ```
   - Should show: `Email Backend: django.core.mail.backends.console.EmailBackend`

### Problem: "Registration doesn't trigger email"

**Debug steps:**
1. Check Django server terminal for errors
2. Try the test script: `python test_registration_flow.py`
3. If test script works but registration doesn't, there may be an error in the registration view

---

## 📋 QUICK TEST (Proven Working!)

Run this to see how it looks:
```bash
python test_registration_flow.py
```

This creates a test user and shows you exactly what the activation email looks like in the console.

**Sample output shows the activation link:**
```
http://localhost:8000/accounts/confirm-email/MTE/cxkws3-1d16cda3a73ffd25f7d33b14a1bdb460/
```

---

## 💡 ALTERNATIVE: Use Manual Activation (Easier!)

If you keep missing the console output, just use the manual command:

```bash
# See who needs activation
python manage.py activate_users --list-unverified

# Activate them
python manage.py activate_users user@example.com
```

This is actually faster than copying URLs from the console!

---

## 🎯 SUMMARY

✅ **Email system is working correctly**  
✅ **Activation links ARE being generated**  
✅ **You just need to look in the Django server terminal**  
✅ **Manual activation command works as backup**  

**The issue is not with the code - it's about knowing WHERE to look for the output!**