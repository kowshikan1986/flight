from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0006_flight_return_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='flightseat',
            name='leg',
            field=models.CharField(choices=[('outbound', 'Outbound'), ('return', 'Return')], default='outbound', max_length=8),
        ),
        migrations.AlterUniqueTogether(
            name='flightseat',
            unique_together={('flight', 'leg', 'seat_number')},
        ),
        migrations.AlterModelOptions(
            name='flightseat',
            options={'ordering': ['leg', 'seat_number']},
        ),
    ]
