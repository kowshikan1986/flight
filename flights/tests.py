from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import AvailabilityError

from .forms import FlightPassengerDetailsForm, FlightPaymentForm
from .models import Flight, FlightBookingSeat
from .services import create_booking


class FlightPassengerDetailsFormTests(TestCase):
	def setUp(self) -> None:
		departure = timezone.now() + timedelta(days=1)
		arrival = departure + timedelta(hours=2)
		self.flight = Flight.objects.create(
			code='WW100',
			origin='Origin City',
			destination='Destination City',
			departure_time=departure,
			arrival_time=arrival,
			base_price=Decimal('100.00'),
		)
		self.available_seats = list(self.flight.seats.order_by('seat_number')[:3])

	def test_requires_passenger_details_when_multiple_passengers(self) -> None:
		form = FlightPassengerDetailsForm(
			data={
				'flight_id': self.flight.id,
				'passenger_count': 2,
				'contact_email': 'lead@example.com',
				'notify_admin': True,
				'passenger_0_date_of_birth': '1990-01-01',
				'passenger_1_date_of_birth': '1992-02-02',
				'passenger_0_main_luggage_weight': '15',
				'passenger_0_hand_luggage_weight': '5',
				'passenger_1_main_luggage_weight': '18',
				'passenger_1_hand_luggage_weight': '5',
			},
			flight=self.flight,
			passenger_count=2,
		)
		self.assertFalse(form.is_valid())
		self.assertIn('Please complete all passenger details.', form.errors['__all__'])

	def test_form_valid_with_complete_passenger_details(self) -> None:
		form = FlightPassengerDetailsForm(
			data={
				'flight_id': self.flight.id,
				'passenger_count': 2,
				'contact_email': 'lead@example.com',
				'notify_admin': True,
				'passenger_0_first_name': 'Jordan',
				'passenger_0_last_name': 'Doe',
				'passenger_0_contact_number': '+123456789',
				'passenger_0_date_of_birth': '1990-01-01',
				'passenger_0_main_luggage_weight': '37.5',
				'passenger_0_hand_luggage_weight': '6.5',
				'passenger_1_first_name': 'Casey',
				'passenger_1_last_name': 'Smith',
				'passenger_1_contact_number': '+987654321',
				'passenger_1_date_of_birth': '1992-02-02',
				'passenger_1_main_luggage_weight': '28',
				'passenger_1_hand_luggage_weight': '5',
			},
			flight=self.flight,
			passenger_count=2,
		)
		self.assertTrue(form.is_valid())
		details = form.get_passenger_details()
		self.assertEqual(len(details), 2)
		self.assertEqual(details[0]['main_luggage_weight'], '37.50')
		self.assertEqual(details[0]['luggage_fee'], '0.00')

	def test_errors_when_insufficient_seats(self) -> None:
		self.flight.seats.update(is_reserved=True)
		form = FlightPassengerDetailsForm(
			data={
				'flight_id': self.flight.id,
				'passenger_count': 2,
				'contact_email': 'lead@example.com',
				'notify_admin': True,
				'passenger_0_first_name': 'Jordan',
				'passenger_0_last_name': 'Doe',
				'passenger_0_date_of_birth': '1990-01-01',
				'passenger_0_main_luggage_weight': '20',
				'passenger_0_hand_luggage_weight': '5',
				'passenger_1_first_name': 'Casey',
				'passenger_1_last_name': 'Smith',
				'passenger_1_date_of_birth': '1992-02-02',
				'passenger_1_main_luggage_weight': '22',
				'passenger_1_hand_luggage_weight': '5',
			},
			flight=self.flight,
			passenger_count=2,
		)
		self.assertFalse(form.is_valid())
		self.assertIn('Only 0 seat(s) remaining', form.errors['__all__'][0])

	def test_rejects_future_date_of_birth(self) -> None:
		future_date = (timezone.now() + timedelta(days=10)).date().isoformat()
		form = FlightPassengerDetailsForm(
			data={
				'flight_id': self.flight.id,
				'passenger_count': 1,
				'contact_email': 'lead@example.com',
				'notify_admin': True,
				'passenger_0_first_name': 'Jamie',
				'passenger_0_last_name': 'Sky',
				'passenger_0_contact_number': '+111222333',
				'passenger_0_date_of_birth': future_date,
				'passenger_0_main_luggage_weight': '18',
				'passenger_0_hand_luggage_weight': '5',
			},
			flight=self.flight,
			passenger_count=1,
		)
		self.assertFalse(form.is_valid())
		self.assertIn('Date of birth cannot be in the future.', form.errors['passenger_0_date_of_birth'])

	def test_hand_luggage_limit_enforced(self) -> None:
		form = FlightPassengerDetailsForm(
			data={
				'flight_id': self.flight.id,
				'passenger_count': 1,
				'contact_email': 'lead@example.com',
				'notify_admin': True,
				'passenger_0_first_name': 'River',
				'passenger_0_last_name': 'Stone',
				'passenger_0_contact_number': '+111222333',
				'passenger_0_date_of_birth': '1990-01-01',
				'passenger_0_main_luggage_weight': '20',
				'passenger_0_hand_luggage_weight': '8',
			},
			flight=self.flight,
			passenger_count=1,
		)
		self.assertFalse(form.is_valid())
		self.assertIn('Hand luggage cannot exceed 7 kg.', form.errors['passenger_0_hand_luggage_weight'])

	def test_overweight_checked_luggage_computes_fee(self) -> None:
		form = FlightPassengerDetailsForm(
			data={
				'flight_id': self.flight.id,
				'passenger_count': 1,
				'contact_email': 'lead@example.com',
				'notify_admin': True,
				'passenger_0_first_name': 'Taylor',
				'passenger_0_last_name': 'Sky',
				'passenger_0_contact_number': '+111222333',
				'passenger_0_date_of_birth': '1990-01-01',
				'passenger_0_main_luggage_weight': '41.2',
				'passenger_0_hand_luggage_weight': '5',
			},
			flight=self.flight,
			passenger_count=1,
		)
		self.assertTrue(form.is_valid())
		luggage_fee = form.get_passenger_details()[0]['luggage_fee']
		self.assertEqual(luggage_fee, '40.00')


@override_settings(STRIPE_SECRET_KEY='sk_test_required', STRIPE_PUBLISHABLE_KEY='pk_test_required')
class FlightPaymentFormTests(TestCase):
	def setUp(self) -> None:
		self.payment_data = {
			'cardholder_first_name': 'Jordan',
			'cardholder_last_name': 'Doe',
			'cardholder_address_line1': '123 Market Street',
			'cardholder_address_line2': 'Unit 5',
			'cardholder_address_city': 'Metropolis',
			'cardholder_address_state': 'CA',
			'cardholder_address_postal_code': '94105',
			'cardholder_address_country': 'US',
		}

	def test_requires_payment_token_when_card_processing_enabled(self) -> None:
		form = FlightPaymentForm(data={**self.payment_data})
		self.assertFalse(form.is_valid())
		self.assertIn(
			'Payment authorization is required before we can confirm your booking.',
			form.errors['payment_token'][0],
		)

	def test_requires_billing_details_when_card_processing_enabled(self) -> None:
		invalid_data = self.payment_data.copy()
		invalid_data['cardholder_first_name'] = ''
		form = FlightPaymentForm(data={**invalid_data, 'payment_token': 'pm_test_token'})
		self.assertFalse(form.is_valid())
		self.assertIn('Cardholder first name is required for card payments.', form.errors['cardholder_first_name'][0])

	def test_valid_payment_form(self) -> None:
		form = FlightPaymentForm(data={**self.payment_data, 'payment_token': 'pm_test_token'})
		self.assertTrue(form.is_valid())
		billing = form.get_billing_details()
		self.assertEqual(billing['country'], 'US')


class FlightBookingServiceTests(TestCase):
	def setUp(self) -> None:
		User = get_user_model()
		self.user = User.objects.create_user(email='traveler@example.com', password='password123')
		departure = timezone.now() + timedelta(days=1)
		arrival = departure + timedelta(hours=2)
		self.flight = Flight.objects.create(
			code='WW200',
			origin='City A',
			destination='City B',
			departure_time=departure,
			arrival_time=arrival,
			base_price=Decimal('150.00'),
		)
		self.seats = list(self.flight.seats.order_by('seat_number')[:3])

	def test_passenger_details_are_persisted_per_seat(self) -> None:
		passengers = [
			{
				'first_name': 'Alex',
				'last_name': 'Rivera',
				'contact_number': '+1234567890',
				'date_of_birth': date(1992, 5, 17),
				'main_luggage_weight': Decimal('45'),
				'hand_luggage_weight': Decimal('6'),
			},
			{
				'first_name': 'Jamie',
				'last_name': 'Lee',
				'contact_number': '+1987654321',
				'date_of_birth': date(1995, 9, 10),
				'main_luggage_weight': Decimal('38'),
				'hand_luggage_weight': Decimal('5'),
			},
		]

		booking = create_booking(
			user=self.user,
			flight=self.flight,
			contact_email='lead@example.com',
			notify_admin=False,
			payment_token=None,
			passenger_count=2,
			passenger_details=passengers,
		)

		assigned_seats = list(booking.seats.order_by('seat_number'))
		self.assertEqual([seat.id for seat in assigned_seats], [seat.id for seat in self.seats[:2]])
		for seat, passenger in zip(assigned_seats, passengers, strict=True):
			booking_seat = FlightBookingSeat.objects.get(booking=booking, seat=seat)
			self.assertEqual(booking_seat.passenger_first_name, passenger['first_name'])
			self.assertEqual(booking_seat.passenger_last_name, passenger['last_name'])
			self.assertEqual(booking_seat.passenger_contact_number, passenger['contact_number'])
			self.assertEqual(booking_seat.passenger_date_of_birth, passenger['date_of_birth'])
			self.assertEqual(booking_seat.main_luggage_weight, passenger['main_luggage_weight'].quantize(Decimal('0.01')))
			self.assertEqual(booking_seat.hand_luggage_weight, passenger['hand_luggage_weight'].quantize(Decimal('0.01')))
			if passenger['main_luggage_weight'] > Decimal('40'):
				self.assertGreater(booking_seat.luggage_fee, Decimal('0.00'))
			else:
				self.assertEqual(booking_seat.luggage_fee, Decimal('0.00'))

	def test_passenger_detail_length_must_match_seats(self) -> None:
		with self.assertRaises(AvailabilityError):
			create_booking(
				user=self.user,
				flight=self.flight,
				contact_email='lead@example.com',
				notify_admin=False,
				payment_token=None,
				passenger_count=2,
				passenger_details=[{'first_name': 'Only', 'last_name': 'One', 'date_of_birth': date(1990, 1, 1)}],
			)

	def test_error_when_not_enough_seats(self) -> None:
		self.flight.seats.update(is_reserved=True)
		with self.assertRaises(AvailabilityError):
			create_booking(
				user=self.user,
				flight=self.flight,
				contact_email='lead@example.com',
				notify_admin=False,
				payment_token=None,
				passenger_count=2,
				passenger_details=[
					{'first_name': 'Taylor', 'last_name': 'Sky', 'date_of_birth': date(1990, 1, 1)},
					{'first_name': 'Morgan', 'last_name': 'Cloud', 'date_of_birth': date(1992, 2, 2)},
				],
			)

	def test_create_booking_rejects_future_birth_date(self) -> None:
		future_dob = date.today() + timedelta(days=5)
		with self.assertRaises(AvailabilityError):
			create_booking(
				user=self.user,
				flight=self.flight,
				contact_email='lead@example.com',
				notify_admin=False,
				payment_token=None,
				passenger_count=1,
				passenger_details=[
					{
						'first_name': 'Taylor',
						'last_name': 'Sky',
						'contact_number': '+100200300',
						'date_of_birth': future_dob,
					},
				],
			)

	def test_create_booking_rejects_excess_hand_luggage(self) -> None:
		with self.assertRaises(AvailabilityError):
			create_booking(
				user=self.user,
				flight=self.flight,
				contact_email='lead@example.com',
				notify_admin=False,
				payment_token=None,
				passenger_count=1,
				passenger_details=[
					{
						'first_name': 'Alex',
						'last_name': 'River',
						'contact_number': '+100200300',
						'date_of_birth': date(1990, 1, 1),
						'main_luggage_weight': Decimal('20'),
						'hand_luggage_weight': Decimal('8'),
					},
				],
			)

	def test_create_booking_applies_luggage_surcharge(self) -> None:
		passengers = [
			{
				'first_name': 'Morgan',
				'last_name': 'Cloud',
				'contact_number': '+100200300',
				'date_of_birth': date(1990, 1, 1),
				'main_luggage_weight': Decimal('42.3'),
				'hand_luggage_weight': Decimal('6'),
			},
		]

		booking = create_booking(
			user=self.user,
			flight=self.flight,
			contact_email='lead@example.com',
			notify_admin=False,
			payment_token=None,
			passenger_count=1,
			passenger_details=passengers,
		)

		base_total = sum((self.flight.base_price * seat.price_modifier for seat in self.seats[:1]), Decimal('0.00')).quantize(Decimal('0.01'))
		expected_surcharge = Decimal('60.00')
		self.assertEqual(booking.total_price, base_total + expected_surcharge)
		booking_seat = FlightBookingSeat.objects.get(booking=booking)
		self.assertEqual(booking_seat.luggage_fee, expected_surcharge)
