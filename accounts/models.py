"""Custom user models for the travel booking system."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
	"""Manager that enforces unique email addresses."""

	use_in_migrations = True

	def _create_user(self, email, password, **extra_fields):
		if not email:
			raise ValueError("Users must provide an email address")
		email = self.normalize_email(email)
		user = self.model(email=email, username=email, **extra_fields)
		user.set_password(password)
		user.save(using=self._db)
		return user

	def create_user(self, email, password=None, **extra_fields):  # type: ignore[override]
		extra_fields.setdefault('is_staff', False)
		extra_fields.setdefault('is_superuser', False)
		return self._create_user(email, password, **extra_fields)

	def create_superuser(self, email, password=None, **extra_fields):  # type: ignore[override]
		extra_fields.setdefault('is_staff', True)
		extra_fields.setdefault('is_superuser', True)

		if extra_fields.get('is_staff') is not True:
			raise ValueError('Superuser must have is_staff=True.')
		if extra_fields.get('is_superuser') is not True:
			raise ValueError('Superuser must have is_superuser=True.')

		return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
	"""Primary user model leveraging email-based login."""

	username = models.EmailField(_('username'), unique=True)
	email = models.EmailField(_('email address'), unique=True)
	phone_number = models.CharField(
		_('phone number'),
		max_length=20,
		blank=True,
		validators=[RegexValidator(r'^[0-9+() -]{7,}$')],
	)
	marketing_opt_in = models.BooleanField(default=False)
	is_customer = models.BooleanField(default=True)
	email_verified = models.BooleanField(default=False)
	email_verified_at = models.DateTimeField(null=True, blank=True)

	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS: list[str] = []

	objects = UserManager()

	class Meta(AbstractUser.Meta):
		swappable = 'AUTH_USER_MODEL'

	def __str__(self) -> str:  # pragma: no cover - human readable
		return self.get_full_name() or self.email


class CustomerProfile(models.Model):
	"""Extended profile details for customers."""

	user = models.OneToOneField(User, related_name='profile', on_delete=models.CASCADE)
	date_of_birth = models.DateField(null=True, blank=True)
	address_line1 = models.CharField(max_length=255, blank=True)
	address_line2 = models.CharField(max_length=255, blank=True)
	city = models.CharField(max_length=120, blank=True)
	state = models.CharField(max_length=120, blank=True)
	country = models.CharField(max_length=120, blank=True)
	postcode = models.CharField(max_length=20, blank=True)
	emergency_contact_name = models.CharField(max_length=120, blank=True)
	emergency_contact_phone = models.CharField(max_length=20, blank=True)

	def __str__(self) -> str:  # pragma: no cover - human readable
		return f"Profile for {self.user}"
