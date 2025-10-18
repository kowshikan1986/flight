from django.apps import AppConfig


class FlightsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'flights'

    def ready(self) -> None:  # pragma: no cover - side effects only
        from . import signals  # noqa: F401
