"""URL routes for account management."""

from django.urls import path

from .views import (
    AccountOverviewView,
    ConfirmEmailView,
    ProfileView,
    RegisterView,
    ResendConfirmationView,
    UserLoginView,
    UserLogoutView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('overview/', AccountOverviewView.as_view(), name='overview'),
    path('confirm-email/<uidb64>/<token>/', ConfirmEmailView.as_view(), name='confirm_email'),
    path('resend-confirmation/', ResendConfirmationView.as_view(), name='resend_confirmation'),
]
