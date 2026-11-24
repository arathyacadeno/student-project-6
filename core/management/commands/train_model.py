from django.core.management.base import BaseCommand

from core import ml


class Command(BaseCommand):
    help = "Train and save the KNN destination recommender."

    def handle(self, *args, **opts):
        m = ml.train()
        self.stdout.write(self.style.SUCCESS(f"Model saved. {m}"))
