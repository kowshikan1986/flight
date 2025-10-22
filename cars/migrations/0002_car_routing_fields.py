from django.db import migrations, models


def populate_route_fields(apps, schema_editor):
    Car = apps.get_model('cars', 'Car')
    for car in Car.objects.all():
        if not car.pickup_location:
            car.pickup_location = car.location
        if not car.dropoff_location:
            car.dropoff_location = car.location
        car.save(update_fields=['pickup_location', 'dropoff_location'])


def reverse_populate_route_fields(apps, schema_editor):
    Car = apps.get_model('cars', 'Car')
    for car in Car.objects.all():
        car.pickup_location = ''
        car.dropoff_location = ''
        car.save(update_fields=['pickup_location', 'dropoff_location'])


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='car',
            old_name='price_per_day',
            new_name='price_per_trip',
        ),
        migrations.AddField(
            model_name='car',
            name='default_dropoff_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='car',
            name='default_pickup_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='car',
            name='dropoff_location',
            field=models.CharField(blank=True, default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='car',
            name='pickup_location',
            field=models.CharField(blank=True, default='', max_length=255),
            preserve_default=False,
        ),
        migrations.RunPython(populate_route_fields, reverse_populate_route_fields),
    ]
