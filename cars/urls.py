"""Car rental URLs."""

from django.urls import path

from .views import (
    CarBookingCreateView,
    CarBookingDetailView,
    CarBookingListView,
    CarBookingPaymentView,
    CarBookingReviewView,
    CarDetailView,
    CarSearchView,
)

urlpatterns = [
    path('', CarSearchView.as_view(), name='search'),
    path('bookings/', CarBookingListView.as_view(), name='booking-list'),
    path('bookings/<str:reference>/', CarBookingDetailView.as_view(), name='booking-detail'),
    path('<int:car_id>/book/', CarBookingCreateView.as_view(), name='book'),
    path('<int:car_id>/book/review/', CarBookingReviewView.as_view(), name='book-review'),
    path('<int:car_id>/book/payment/', CarBookingPaymentView.as_view(), name='book-payment'),
    path('<int:pk>/', CarDetailView.as_view(), name='detail'),
]
