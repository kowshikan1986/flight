from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0005_flight_return_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='flight',
            name='return_code',
            field=models.CharField(blank=True, max_length=10),
        ),
    ]
