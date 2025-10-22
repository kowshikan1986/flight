from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0002_car_routing_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='carbooking',
            name='contact_number',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name='carbooking',
            name='first_name',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='carbooking',
            name='last_name',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='carbooking',
            name='pickup_time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
