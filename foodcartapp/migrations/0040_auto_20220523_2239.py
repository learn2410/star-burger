# Generated by Django 3.2 on 2022-05-23 17:39

from django.db import migrations, models
import phonenumber_field.modelfields


class Migration(migrations.Migration):

    dependencies = [
        ('foodcartapp', '0039_basket_order'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='address',
            field=models.CharField(db_index=True, help_text='Москва, 3-я ул. Строителей, д.25', max_length=100, verbose_name='Адрес'),
        ),
        migrations.AlterField(
            model_name='order',
            name='firstname',
            field=models.CharField(db_index=True, help_text='Иван', max_length=50, verbose_name='Имя'),
        ),
        migrations.AlterField(
            model_name='order',
            name='lastname',
            field=models.CharField(db_index=True, help_text='Сусанин', max_length=50, verbose_name='Фамилия'),
        ),
        migrations.AlterField(
            model_name='order',
            name='phonenumber',
            field=phonenumber_field.modelfields.PhoneNumberField(db_index=True, help_text='+7 987 654 3211', max_length=128, region=None, verbose_name='Телефон'),
        ),
    ]