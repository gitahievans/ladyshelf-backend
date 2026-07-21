from django.core.management.base import BaseCommand

from admin_portal.image_generation.services import process_next_generation


class Command(BaseCommand):
    help = "Processes queued AI product image generations asynchronously."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1)

    def handle(self, *args, **options):
        limit = max(0, options["limit"])
        processed = 0
        while processed < limit and process_next_generation():
            processed += 1
        self.stdout.write(self.style.SUCCESS(f"Processed {processed} product image generation(s)."))
