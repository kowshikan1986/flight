from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='flightbookingseat',
            name='passenger_contact_number',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='flightbookingseat',
            name='passenger_date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='flightbookingseat',
            name='passenger_first_name',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='flightbookingseat',
            name='passenger_last_name',
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
