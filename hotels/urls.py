"""URL configuration for hotels module."""

from django.urls import path

from .views import (
    HotelBookingCreateView,
    HotelBookingDetailView,
    HotelBookingListView,
    HotelDetailView,
    HotelSearchView,
)

urlpatterns = [
    path('', HotelSearchView.as_view(), name='search'),
    path('bookings/', HotelBookingListView.as_view(), name='booking-list'),
    path('bookings/<str:reference>/', HotelBookingDetailView.as_view(), name='booking-detail'),
    path('<int:room_type_id>/book/', HotelBookingCreateView.as_view(), name='book'),
    path('<slug:slug>/', HotelDetailView.as_view(), name='detail'),
]
