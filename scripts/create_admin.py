"""Utility script to ensure an admin user exists."""

from __future__ import annotations

from django.contrib.auth import get_user_model


def ensure_admin(email: str, password: str) -> None:
    User = get_user_model()
    user, created = User.objects.update_or_create(
        email=email,
        defaults={
            "username": email,
            "first_name": "Admin",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    user.set_password(password)
    user.save()
    action = "created" if created else "updated"
    print(f"Admin user {action}: {email}")


def run() -> None:
    ensure_admin("admin@example.com", "AdminPass123!")


if __name__ == "__main__":
    run()
