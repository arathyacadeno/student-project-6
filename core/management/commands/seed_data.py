from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core import ml, tools_logic as tl
from core.models import Activity, Booking, Category, Destination, Hotel, Package, Profile, Review

# name, district, category, climate, emoji, lat, lng, attractions, tags, best, peak, cost, rating, safety, hidden, eco, description
DESTS = [
    ("Alappuzha", "Alappuzha", "Backwaters", "backwater", "🛶", 9.4981, 76.3388,
     "Backwaters, Marari Beach, Pathiramanal Island", "backwaters,houseboat,boating,relaxing,family,beach", "11,12,1,2", "12,1", 3200, 4.7, 90, False, True,
     "Venice of the East: slow houseboat cruises through palm-fringed canals, quiet beaches and island birdwatching."),
    ("Marari Beach", "Alappuzha", "Beach", "beach", "🏖️", 9.6030, 76.3010,
     "Marari Beach, Fishing village walk, Mararikulam sunset point", "beach,peaceful,fishing,relaxing,couple,swimming", "11,12,1,2,3", "12", 2600, 4.4, 88, True, True,
     "An unhurried fishing-village beach with clean sand, coconut groves and far fewer crowds than Kovalam."),
    ("Athirappilly", "Thrissur", "Waterfalls", "waterfall", "💦", 10.2851, 76.5698,
     "Athirappilly Waterfalls, Vazhachal Waterfalls, Sholayar forest drive", "waterfalls,forest,nature,photography,family,trekking", "8,9,10,11", "9,10", 2400, 4.6, 86, False, False,
     "Kerala's largest waterfall, thundering through rainforest next to the Vazhachal falls."),
    ("Vazhachal", "Thrissur", "Waterfalls", "forest", "🌳", 10.2970, 76.5390,
     "Vazhachal Waterfalls, Charpa Falls, Hornbill spotting", "waterfalls,forest,birdwatching,peaceful,nature,trekking", "9,10,11,12,1", "", 1900, 4.3, 84, True, True,
     "A calmer neighbour of Athirappilly, loved by birdwatchers for hornbills and the riverine forest."),
    ("Palakkad", "Palakkad", "Nature & Dams", "plains", "🌾", 10.7867, 76.6548,
     "Malampuzha Dam, Nelliyampathy, Dhoni Waterfalls, Silent Valley", "dam,gardens,hills,nature,trekking,family,waterfalls", "9,10,11,12,1,2", "12", 2100, 4.3, 87, False, False,
     "The gateway to Kerala with Malampuzha's gardens, the Nelliyampathy hills and the Dhoni waterfalls."),
    ("Silent Valley", "Palakkad", "Wildlife", "forest", "🦁", 11.0833, 76.4333,
     "Silent Valley National Park, Sairandhri viewpoint, Kunthipuzha river", "wildlife,rainforest,trekking,nature,peaceful,birdwatching", "12,1,2,3", "", 2300, 4.5, 85, True, True,
     "One of India's last untouched tropical rainforests, with lion-tailed macaques and guided trails."),
    ("Wayanad", "Wayanad", "Hill Station", "hill", "⛰️", 11.6854, 76.1320,
     "Banasura Sagar Dam, Pookode Lake, Edakkal Caves", "hills,trekking,caves,lake,family,nature,adventure", "10,11,12,1,2,3", "12,1", 3000, 4.6, 88, False, True,
     "Misty green hills, spice plantations, Neolithic Edakkal caves and India's largest earthen dam."),
    ("Munnar", "Idukki", "Hill Station", "hill", "🍃", 10.0889, 77.0595,
     "Munnar tea gardens, Eravikulam National Park, Mattupetty Dam", "tea,hills,couple,photography,nature,trekking,peaceful", "9,10,11,12,1,2,3", "12,1,4,5", 3400, 4.8, 90, False, False,
     "Rolling tea estates at 1,600 m, cool mornings and the home of the Neelakurinji bloom."),
    ("Thekkady", "Idukki", "Wildlife", "forest", "🐘", 9.5993, 77.1685,
     "Periyar Tiger Reserve, Spice plantation walk, Kalaripayattu show", "wildlife,boating,spices,family,nature,adventure", "10,11,12,1,2,3", "12,1", 3100, 4.5, 89, False, True,
     "Boat safaris on Periyar lake, elephant sightings and fragrant spice gardens."),
    ("Vagamon", "Idukki", "Hill Station", "hill", "🪂", 9.6860, 76.9040,
     "Pine forest, Meadows, Paragliding point, Kurisumala", "meadows,paragliding,peaceful,hills,couple,adventure,nature", "9,10,11,12,1,2", "", 2200, 4.4, 90, True, True,
     "Rolling meadows, pine forests and paragliding, without Munnar's weekend traffic."),
]
CATS = ["Backwaters", "Beach", "Waterfalls", "Nature & Dams", "Wildlife", "Hill Station"]
REVIEWS = ["Beautiful and peaceful, loved the sunset views. Highly recommended!", "Amazing place but very crowded on weekends.",
           "The roads were difficult and tickets felt overpriced.", "Clean, scenic and the staff were friendly.",
           "Stunning views, perfect for a relaxed family trip.", "A bit boring after two hours, parking was poor."]


class Command(BaseCommand):
    help = "Load Kerala sample data, demo users and train the recommender."

    def handle(self, *args, **opts):
        cats = {n: Category.objects.get_or_create(name=n)[0] for n in CATS}
        for (name, district, cat, clim, emoji, lat, lng, attr, tags, best, peak, cost, rating, safety, hidden, eco, desc) in DESTS:
            d, _ = Destination.objects.update_or_create(name=name, defaults=dict(
                district=district, category=cats[cat], climate=clim, emoji=emoji, latitude=lat, longitude=lng,
                attractions=attr, tags=tags, best_months=best, peak_months=peak, avg_daily_cost=cost, rating=rating,
                safety_score=safety, is_hidden_gem=hidden, eco_friendly=eco, description=desc))
            if not d.hotels.exists():
                Hotel.objects.bulk_create([
                    Hotel(destination=d, name=f"{name} Homestay", price_per_night=cost // 2, rating=4.1, eco_friendly=True, amenities="Breakfast, Wi-Fi"),
                    Hotel(destination=d, name=f"{name} Residency", price_per_night=cost, rating=4.3, amenities="AC rooms, Restaurant"),
                    Hotel(destination=d, name=f"{name} Heritage Resort", price_per_night=cost * 2, rating=4.7, amenities="Pool, Spa, Guided tours")])
                first = d.attraction_list[0]
                Activity.objects.bulk_create([
                    Activity(destination=d, name=f"Guided visit to {first}", cost=300, duration_hours=3),
                    Activity(destination=d, name="Local food trail", cost=500, duration_hours=2),
                    Activity(destination=d, name=f"Sunset at {d.attraction_list[-1]}", cost=0, duration_hours=1.5)])
                Package.objects.bulk_create([
                    Package(destination=d, title=f"{name} Escape - 3 days", days=3, price=cost * 3 + 1500,
                            description=f"Relaxed 3-day trip covering {', '.join(d.attraction_list[:3])}.",
                            includes="Hotel stay,Breakfast,Local transport,Guide"),
                    Package(destination=d, title=f"{name} Explorer - 5 days", days=5, price=cost * 5 + 2500,
                            description="Longer itinerary with activities and a day for slow exploring.",
                            includes="Hotel stay,All meals,Private cab,Activities")])

        admin, made = User.objects.get_or_create(username="admin", defaults=dict(is_staff=True, is_superuser=True, email="admin@travelmate.ai"))
        if made:
            admin.set_password("admin123")
            admin.save()
        demo = {"demo": ("Waterfalls", "waterfalls, trekking, photography"), "anu": ("Hill Station", "tea, trekking, nature"),
                "ravi": ("Backwaters", "boating, relaxing, family")}
        for uname, (cat, interests) in demo.items():
            u, made = User.objects.get_or_create(username=uname, defaults={"email": f"{uname}@example.com"})
            if made:
                u.set_password("demo12345")
                u.save()
            p, _ = Profile.objects.get_or_create(user=u)
            p.interests = interests
            p.save()
            p.preferred_categories.set([cats[cat]])
        w, a = Destination.objects.get(name="Wayanad"), User.objects.get(username="anu")
        if not Booking.objects.exists():
            for uname in ("demo", "anu"):
                Booking.objects.create(user=User.objects.get(username=uname), destination=w, start_date=date.today() + timedelta(days=20),
                                       end_date=date.today() + timedelta(days=23), travellers=2, budget=25000, total_cost=18000, status="confirmed")
        if not Review.objects.exists():
            for i, text in enumerate(REVIEWS):
                Review.objects.create(destination=Destination.objects.get(name=["Munnar", "Wayanad", "Athirappilly"][i % 3]),
                                      user=a, text=text, rating=4, sentiment=tl.sentiment(text))
        self.stdout.write(self.style.SUCCESS(f"Seeded. Model: {ml.train()}"))
        self.stdout.write("Admin login: admin / admin123    Demo traveller: demo / demo12345")
