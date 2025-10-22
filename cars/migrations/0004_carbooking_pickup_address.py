from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0003_carbooking_contact_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='carbooking',
            name='pickup_address',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
