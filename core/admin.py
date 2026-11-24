from django.contrib import admin
from .models import Activity, Booking, Category, Destination, Hotel, Itinerary, Package, Profile, Review

for m in (Category, Destination, Hotel, Activity, Package, Profile, Booking, Itinerary, Review):
    admin.site.register(m)
