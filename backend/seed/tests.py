from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from planting.models import ProduceListing


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_includes_repeat_safe_marketplace_listings(self):
        call_command("seed_demo", stdout=StringIO())

        listings = ProduceListing.objects.filter(description__startswith="[DEMO]")
        self.assertEqual(listings.count(), 3)
        self.assertEqual(
            listings.filter(status=ProduceListing.Statuses.AVAILABLE).count(), 3
        )
        self.assertTrue(listings.filter(farmer__user__phone="+254700000005").exists())

        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(listings.count(), 3)
