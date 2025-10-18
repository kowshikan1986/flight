"""Forms for account management."""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.core.validators import validate_email
from django.db import transaction

from .models import CustomerProfile, User
from .services import send_email_confirmation


class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    confirm_password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    class Meta:
        model = User
        fields = [
            "email",
            "phone_number",
            "first_name",
            "last_name",
            "marketing_opt_in",
            "password",
        ]

    def clean_email(self) -> str:
        email = self.cleaned_data.get("email", "").strip().lower()
        validate_email(email)
        domain = email.split("@")[-1]
        if "." not in domain:
            raise forms.ValidationError("Email domain must include a valid top-level domain")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

    def save(self, commit: bool = True) -> User:
        user: User = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = user.email
        user.set_password(self.cleaned_data["password"])
        user.email_verified = False
        if commit:
            user.save()
        return user


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        exclude = ("user",)


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Email")

    def confirm_login_allowed(self, user):  # type: ignore[override]
        if not getattr(user, "email_verified", True):
            request = getattr(self, "request", None)

            def _dispatch_confirmation() -> None:
                if request is not None:
                    send_email_confirmation(request, user)

            if transaction.get_connection().in_atomic_block:
                transaction.on_commit(_dispatch_confirmation)
            else:
                _dispatch_confirmation()

            if request is not None:
                messages.info(
                    request,
                    "We just sent you a new activation link. Please check your inbox and spam folder.",
                )

            raise forms.ValidationError(
                "Please confirm your email address before signing in. We've re-sent the activation email.",
                code="email_not_verified",
            )
        return super().confirm_login_allowed(user)


class PasswordlessLoginForm(forms.Form):
    email = forms.EmailField()

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        if email and not User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("No account exists with that email address")
        return cleaned_data

    def authenticate(self):
        email = self.cleaned_data["email"]
        user = authenticate(username=email, password=None)
        return user


class ResendConfirmationForm(forms.Form):
    email = forms.EmailField()

    def clean_email(self) -> str:
        email = self.cleaned_data.get("email", "").strip().lower()
        validate_email(email)
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist as exc:
            raise forms.ValidationError("We couldn't find an account with that email address.") from exc
        if getattr(user, "email_verified", False):
            raise forms.ValidationError("This account is already verified. Try signing in instead.")
        self.user = user
        return email

    def get_user(self) -> User | None:
        return getattr(self, "user", None)
