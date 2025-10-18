"""Flight URLs."""

from django.urls import path

from .views import (
    FlightBookingCreateView,
    FlightBookingDetailView,
    FlightBookingListView,
    FlightBookingPaymentView,
    FlightBookingReviewView,
    FlightDetailView,
    FlightSearchView,
)

urlpatterns = [
    path('', FlightSearchView.as_view(), name='search'),
    path('bookings/', FlightBookingListView.as_view(), name='booking-list'),
    path('bookings/<str:reference>/', FlightBookingDetailView.as_view(), name='booking-detail'),
    path('<int:flight_id>/book/', FlightBookingCreateView.as_view(), name='book'),
    path('<int:flight_id>/book/review/', FlightBookingReviewView.as_view(), name='book-review'),
    path('<int:flight_id>/book/payment/', FlightBookingPaymentView.as_view(), name='book-payment'),
    path('<slug:code>/', FlightDetailView.as_view(), name='detail'),
]
