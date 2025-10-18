from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import User


class RegistrationWorkflowTests(TestCase):

	def test_registration_sends_confirmation_email(self) -> None:
		with self.captureOnCommitCallbacks(execute=True):
			response = self.client.post(
				reverse('accounts:register'),
				{
					'email': 'newuser@example.com',
					'first_name': 'New',
					'last_name': 'User',
					'phone_number': '+123456789',
					'password': 'ComplexPass123',
					'confirm_password': 'ComplexPass123',
				},
			)

		self.assertRedirects(response, reverse('accounts:login'))
		user = User.objects.get(email='newuser@example.com')
		self.assertFalse(user.email_verified)
		self.assertTrue(user.is_active)
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('Confirm your', mail.outbox[0].subject)
		self.assertIn('confirm-email', mail.outbox[0].body)

	def test_email_confirmation_activates_user(self) -> None:
		user = User.objects.create_user(email='pending@example.com', password='ComplexPass123!')
		user.email_verified = False
		user.save(update_fields=['email_verified'])

		uid = urlsafe_base64_encode(force_bytes(user.pk))
		token = default_token_generator.make_token(user)

		response = self.client.get(reverse('accounts:confirm_email', args=[uid, token]))

		self.assertRedirects(response, reverse('accounts:login'))
		user.refresh_from_db()
		self.assertTrue(user.email_verified)
		self.assertTrue(user.is_active)

	def test_resend_confirmation_triggers_email(self) -> None:
		user = User.objects.create_user(email='waiting@example.com', password='Password123!')
		user.email_verified = False
		user.save(update_fields=['email_verified'])

		with self.captureOnCommitCallbacks(execute=True):
			response = self.client.post(
				reverse('accounts:resend_confirmation'),
				{'email': 'waiting@example.com'},
				follow=True,
			)

		self.assertRedirects(response, reverse('accounts:login'))
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('confirm-email', mail.outbox[0].body)

	def test_login_attempt_resends_confirmation_email(self) -> None:
		user = User.objects.create_user(email='fresh@example.com', password='Password123!')
		user.email_verified = False
		user.save(update_fields=['email_verified'])

		with self.captureOnCommitCallbacks(execute=True):
			response = self.client.post(
				reverse('accounts:login'),
				{'username': 'fresh@example.com', 'password': 'Password123!'},
				follow=True,
			)

		self.assertEqual(response.status_code, 200)
		self.assertIn("activation email", response.content.decode())
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('confirm-email', mail.outbox[0].body)
