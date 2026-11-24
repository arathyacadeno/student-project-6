from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import Activity, Booking, Category, Destination, Hotel, Itinerary, Package, Review


class Command(BaseCommand):
    help = "Remove all demo/sample data: bookings, reviews, demo customers, destinations, hotels, and activities."

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-categories",
            action="store_true",
            help="Also delete categories (by default categories are kept).",
        )

    def handle(self, *args, **options):
        # 1. Bookings & Itineraries
        b_count, _ = Booking.objects.all().delete()
        it_count, _ = Itinerary.objects.all().delete()
        self.stdout.write(f"Deleted {b_count} bookings and {it_count} itineraries.")

        # 2. Reviews
        r_count, _ = Review.objects.all().delete()
        self.stdout.write(f"Deleted {r_count} reviews.")

        # 3. Non-staff demo users
        u_count, _ = User.objects.filter(is_staff=False).delete()
        self.stdout.write(f"Deleted {u_count} non-staff users (and their profiles).")

        # 4. Destinations (cascades to hotels, activities, packages)
        d_count, _ = Destination.objects.all().delete()
        self.stdout.write(f"Deleted {d_count} destinations (and all associated hotels, activities, packages).")

        # 5. Optional categories
        if options.get("include_categories"):
            c_count, _ = Category.objects.all().delete()
            self.stdout.write(f"Deleted {c_count} categories.")

        # 6. Clean stale ML model file if destination count is less than 3
        if Destination.objects.count() < 3 and settings.ML_MODEL_PATH.exists():
            try:
                settings.ML_MODEL_PATH.unlink()
                self.stdout.write("Removed stale ML model bundle.")
            except Exception:
                pass

        self.stdout.write(self.style.SUCCESS("All demo data removed successfully."))
