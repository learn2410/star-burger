# Generated by Django 3.2 on 2022-05-29 03:25

from django.db import migrations
from django.db.models import F,Subquery,OuterRef


class Migration(migrations.Migration):
    def filling_cost(apps, schema_editor):
        Product = apps.get_model('foodcartapp', 'Product')
        Basket = apps.get_model('foodcartapp', 'Basket')
        Basket.objects.update(
            cost=Subquery(Product.objects.filter(id=OuterRef('product_id')).values('price')[:1])
        )

    dependencies = [
        ('foodcartapp', '0042_basket_cost'),
    ]

    operations = [
        migrations.RunPython(filling_cost)
    ]
