from django.db import migrations, models


def enforce_seat_capacity(apps, schema_editor):
    Flight = apps.get_model('flights', 'Flight')
    Flight.objects.exclude(seat_capacity=7).update(seat_capacity=7)


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0002_flightbookingseat_passenger_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flight',
            name='seat_capacity',
            field=models.PositiveIntegerField(default=7),
        ),
        migrations.RunPython(enforce_seat_capacity, migrations.RunPython.noop),
    ]
