"""Reusable services supporting the accounts app."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import User


def build_confirmation_url(request, user: User) -> str:
    """Construct an absolute confirmation URL for an email verification token."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    relative_url = reverse("accounts:confirm_email", args=[uid, token])
    return request.build_absolute_uri(relative_url)


def send_email_confirmation(request, user: User) -> None:
    """Send an email prompting the user to confirm their email address."""
    confirmation_url = build_confirmation_url(request, user)
    context = {
        "user": user,
        "confirmation_url": confirmation_url,
        "site_name": getattr(settings, "SITE_NAME", "WanderWise"),
    }
    subject = render_to_string("accounts/email/confirmation_subject.txt", context).strip()
    text_body = render_to_string("accounts/email/confirmation_email.txt", context)
    html_body = render_to_string("accounts/email/confirmation_email.html", context)

    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[user.email],
    )
    if html_body:
        email_message.attach_alternative(html_body, "text/html")
    email_message.send(fail_silently=False)
