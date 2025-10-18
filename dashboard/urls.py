"""Dashboard URL configuration."""

from django.urls import path

from .views import (
    BookingManagementView,
    FlightPricingListView,
    FlightPricingUpdateView,
    HotelPricingListView,
    HotelRoomTypeUpdateView,
    OverviewView,
)

urlpatterns = [
    path('', OverviewView.as_view(), name='overview'),
    path('hotels/', HotelPricingListView.as_view(), name='hotel-pricing'),
    path('hotels/<int:pk>/', HotelRoomTypeUpdateView.as_view(), name='hotel-pricing-edit'),
    path('flights/', FlightPricingListView.as_view(), name='flight-pricing'),
    path('flights/<int:pk>/', FlightPricingUpdateView.as_view(), name='flight-pricing-edit'),
    path('bookings/', BookingManagementView.as_view(), name='booking-management'),
]
