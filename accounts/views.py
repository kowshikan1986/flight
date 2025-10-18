"""Views handling account registration and profile management."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django.views.generic import FormView, TemplateView, UpdateView

from .forms import CustomerProfileForm, EmailAuthenticationForm, ResendConfirmationForm, UserRegistrationForm
from .models import CustomerProfile, User
from .services import send_email_confirmation


class RegisterView(FormView):
	template_name = 'accounts/register.html'
	form_class = UserRegistrationForm
	success_url = reverse_lazy('accounts:login')

	def get_profile_form(self) -> CustomerProfileForm:
		if self.request.method == 'POST':
			return CustomerProfileForm(self.request.POST)
		return CustomerProfileForm()

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		context.setdefault('profile_form', self.get_profile_form())
		return context

	def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
		form = self.get_form()
		profile_form = self.get_profile_form()
		if form.is_valid() and profile_form.is_valid():
			return self.forms_valid(form, profile_form)
		return self.forms_invalid(form, profile_form)

	def forms_valid(self, form: UserRegistrationForm, profile_form: CustomerProfileForm) -> HttpResponse:
		with transaction.atomic():
			user = form.save()
			profile, _ = CustomerProfile.objects.get_or_create(user=user)
			for field, value in profile_form.cleaned_data.items():
				setattr(profile, field, value)
			profile.save()
			transaction.on_commit(lambda: send_email_confirmation(self.request, user))
		messages.success(
			self.request,
			"Thanks for signing up! We've sent a confirmation link to your email. Please verify to activate your account.",
		)
		return redirect(self.get_success_url())

	def forms_invalid(self, form: UserRegistrationForm, profile_form: CustomerProfileForm) -> HttpResponse:
		return self.render_to_response(self.get_context_data(form=form, profile_form=profile_form))


class UserLoginView(LoginView):
	template_name = 'accounts/login.html'
	form_class = EmailAuthenticationForm


class UserLogoutView(LogoutView):
	next_page = reverse_lazy('accounts:login')


class ProfileView(LoginRequiredMixin, UpdateView):
	template_name = 'accounts/profile.html'
	model = CustomerProfile
	form_class = CustomerProfileForm
	success_url = reverse_lazy('accounts:profile')

	def get_object(self, queryset=None):  # type: ignore[override]
		profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
		return profile

	def form_valid(self, form: CustomerProfileForm) -> HttpResponse:
		messages.success(self.request, 'Profile updated successfully.')
		return super().form_valid(form)


class AccountOverviewView(LoginRequiredMixin, TemplateView):
	template_name = 'accounts/overview.html'

	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		context = super().get_context_data(**kwargs)
		user: User = self.request.user  # type: ignore[assignment]
		context['bookings'] = {
			'hotel': user.hotelbookings.select_related('room_type__hotel').order_by('-created_at')[:5],
			'flight': user.flightbookings.select_related('flight').order_by('-created_at')[:5],
			'car': user.carbookings.select_related('car').order_by('-created_at')[:5],
		}
		return context


class ConfirmEmailView(View):
	def get(self, request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
		try:
			uid = force_str(urlsafe_base64_decode(uidb64))
			user = User.objects.get(pk=uid)
		except (TypeError, ValueError, OverflowError, User.DoesNotExist, ValidationError):
			user = None

		if user and default_token_generator.check_token(user, token):
			if not user.email_verified:
				user.email_verified = True
				user.is_active = True
				user.email_verified_at = timezone.now()
				user.save(update_fields=['email_verified', 'is_active', 'email_verified_at'])
			messages.success(request, 'Your email has been confirmed. You can now sign in.')
			return redirect('accounts:login')

		messages.error(request, 'The confirmation link is invalid or has expired. Please request a new one.')
		return redirect('accounts:register')


class ResendConfirmationView(FormView):
	template_name = 'accounts/resend_confirmation.html'
	form_class = ResendConfirmationForm
	success_url = reverse_lazy('accounts:login')

	def form_valid(self, form: ResendConfirmationForm) -> HttpResponse:
		user = form.get_user()
		if user:
			transaction.on_commit(lambda: send_email_confirmation(self.request, user))
		messages.success(
			self.request,
			"We've sent you a fresh confirmation link. Please check your inbox and spam folder.",
		)
		return super().form_valid(form)
