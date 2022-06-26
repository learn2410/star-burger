import requests
from django.conf import settings
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone


def fetch_coordinates(address, apikey=settings.YANDEX_KEY):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url, params={
        "geocode": address,
        "apikey": apikey,
        "format": "json",
    })
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']
    if not found_places:
        return None, None
    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat

def add_geocoder_addresses(addresses):
    new_geo_addresses={}
    locations=[]
    for address in addresses:
        lon,lat = fetch_coordinates(address)
        locations.append(Location(address=address,lon=lon,lat=lat))
        new_geo_addresses.update({address:(lon,lat)})
        Location.objects.bulk_create(locations)
    return new_geo_addresses

class Location(models.Model):
    address = models.CharField('Адрес', max_length=100, unique=True)
    lon = models.FloatField('Долгота', null=True)
    lat = models.FloatField('Широта', null=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'Локация'
        verbose_name_plural = 'Локации'

    def __str__(self):
        return f'{self.address}'

