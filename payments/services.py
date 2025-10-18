"""Payment provider abstractions."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Payment

logger = logging.getLogger(__name__)


@dataclass
class PaymentResult:
    reference: str
    status: str
    is_success: bool
    client_secret: Optional[str]
    provider: str
    metadata: Dict[str, Any]


def _configure_stripe() -> bool:
    api_key = settings.STRIPE_SECRET_KEY
    if not api_key:
        return False
    stripe.api_key = api_key
    return True


def charge_booking(
    *,
    user,
    amount: Decimal,
    currency: str,
    description: str,
    metadata: Dict[str, Any] | None = None,
    payment_token: str | None = None,
) -> PaymentResult:
    metadata = metadata or {}
    cents = int(amount * 100)

    if _configure_stripe():
        try:
            intent = stripe.PaymentIntent.create(
                amount=cents,
                currency=currency,
                description=description,
                payment_method=payment_token,
                confirm=bool(payment_token),
                receipt_email=user.email,
                metadata=metadata,
            )
            return PaymentResult(
                reference=intent.id,
                status=intent.status,
                is_success=intent.status in {'succeeded', 'requires_capture'},
                client_secret=getattr(intent, 'client_secret', None),
                provider='stripe',
                metadata=metadata,
            )
        except stripe.error.AuthenticationError as exc:  # pragma: no cover - external dependency
            logger.warning('Stripe authentication failed, falling back to test provider: %s', exc)
        except stripe.error.StripeError as exc:  # pragma: no cover - external dependency
            logger.exception('Stripe payment failed: %s', exc)
            raise

    return _create_test_payment_result(amount=amount, currency=currency, metadata=metadata)


def _create_test_payment_result(*, amount: Decimal, currency: str, metadata: Dict[str, Any]) -> PaymentResult:
    reference = f'test_{uuid.uuid4().hex[:12]}'
    logger.info('Using test payment provider for amount %s %s', amount, currency)
    return PaymentResult(
        reference=reference,
        status='succeeded',
        is_success=True,
        client_secret=None,
        provider='test',
        metadata=metadata,
    )


def store_payment_record(
    *,
    user,
    content_object,
    amount: Decimal,
    currency: str,
    result: PaymentResult,
) -> Payment:
    with transaction.atomic():
        payment = Payment.objects.create(
            user=user,
            content_object=content_object,
            amount=amount,
            currency=currency,
            status=Payment.Status.SUCCEEDED if result.is_success else Payment.Status.FAILED,
            provider=result.provider,
            provider_reference=result.reference,
            client_secret=result.client_secret or '',
            metadata=result.metadata,
        )
    return payment


def notify_admins(*, subject: str, message: str) -> None:
    User = get_user_model()
    recipients = list(User.objects.filter(is_staff=True, is_active=True).values_list('email', flat=True))
    if not recipients:
        logger.debug('No admin recipients for notification: %s', subject)
        return
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
