from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0004_flightbookingseat_luggage_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='flight',
            name='return_base_price',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=9),
        ),
        migrations.AddField(
            model_name='flight',
            name='return_destination',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='flight',
            name='return_origin',
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
