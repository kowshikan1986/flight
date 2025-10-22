from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0003_alter_flight_seat_capacity'),
    ]

    operations = [
        migrations.AddField(
            model_name='flightbookingseat',
            name='hand_luggage_weight',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=5),
        ),
        migrations.AddField(
            model_name='flightbookingseat',
            name='luggage_fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=7),
        ),
        migrations.AddField(
            model_name='flightbookingseat',
            name='main_luggage_weight',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=5),
        ),
    ]
