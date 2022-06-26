from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db.models import Count

class Restaurant(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    address = models.CharField(
        'адрес',
        max_length=100,
        blank=True,
    )
    contact_phone = models.CharField(
        'контактный телефон',
        max_length=50,
        blank=True,
    )

    class Meta:
        verbose_name = 'ресторан'
        verbose_name_plural = 'рестораны'

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available(self):
        products = (
            RestaurantMenuItem.objects
                .filter(availability=True)
                .values_list('product')
        )
        return self.filter(pk__in=products)


class ProductCategory(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    category = models.ForeignKey(
        ProductCategory,
        verbose_name='категория',
        related_name='products',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    price = models.DecimalField(
        'цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    image = models.ImageField(
        'картинка'
    )
    special_status = models.BooleanField(
        'спец.предложение',
        default=False,
        db_index=True,
    )
    description = models.TextField(
        'описание',
        blank=True,
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'

    def __str__(self):
        return self.name


class RestaurantMenuItem(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        related_name='menu_items',
        verbose_name="ресторан",
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='menu_items',
        verbose_name='продукт',
    )
    availability = models.BooleanField(
        'в продаже',
        default=True,
        db_index=True
    )

    class Meta:
        verbose_name = 'пункт меню ресторана'
        verbose_name_plural = 'пункты меню ресторана'
        unique_together = [
            ['restaurant', 'product']
        ]

    def __str__(self):
        return f"{self.restaurant.name} - {self.product.name}"


class Order(models.Model):
    STATUSES = (
        ("START", "принят"),
        ("WORK", "в работе"),
        ("CANCEL", "отменен"),
        ("FINISH", "завершен"),
    )
    PAYMENTS = (
        ("CASH", "наличные"),
        ("ELEСTRON", "безналичные"),
        ("UNDEFINED","-не указано"),
    )
    status = models.CharField("Статус", max_length=10,  db_index=True, choices=STATUSES, default="START")
    restaurant = models.ForeignKey(Restaurant,on_delete=models.CASCADE,related_name='order',
                                   verbose_name='Готовит',blank=True,null=True,default=None)
    payment = models.CharField("Оплата", max_length=10, db_index=True, choices=PAYMENTS, default="UNDEFINED")
    firstname = models.CharField('Имя', max_length=50, db_index=True)
    lastname = models.CharField('Фамилия', max_length=50, db_index=True)
    phonenumber = PhoneNumberField('Телефон', db_index=True)
    address = models.CharField('Адрес', max_length=100, db_index=True)
    comment = models.TextField('Комментарий', blank=True)
    registrated = models.DateTimeField('Время регистрации', default=timezone.now)
    called = models.DateTimeField('Время созвона', null=True, blank=True)
    delivered = models.DateTimeField('Время доставки', null=True, blank=True)

    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'

    def __str__(self):
        return (f'{self.id} ({self.firstname} {self.lastname} тел.{self.phonenumber}, {self.address})')

    def can_cook(self, by_name=False):
        ''' resaurants who can cook ordered products, return tuple of restaurant_id (or restaurant_name)'''
        ordered_products = OrderedProduct.objects.filter(order_id=self.id).values_list('product_id', flat=True)
        return RestaurantMenuItem.objects \
            .values('restaurant') \
            .annotate(xprod=Count('product', product__in=ordered_products, availability=True)) \
            .filter(product__in=ordered_products, availability=True, xprod=len(ordered_products)) \
            .values_list('restaurant__name' if by_name else 'restaurant',flat=True)


class OrderedProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='basket', verbose_name='Заказ')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='food', verbose_name='Продукт')
    quantity = models.PositiveIntegerField(
        verbose_name='Количество',
        validators=[MinValueValidator(1)],
        default=1,
    )
    cost = models.DecimalField(
        'зафиксированная цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        verbose_name = 'в заказе'
        verbose_name_plural = 'в заказе'
        unique_together = [
            ['order', 'product']
        ]

    def __str__(self):
        return f"{self.product.name} - {self.quantity} шт. (заказ № {self.order.pk} )"

    def fix_cost(self):
        self.cost=self.product.price

