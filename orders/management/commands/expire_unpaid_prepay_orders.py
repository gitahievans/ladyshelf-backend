from django.core.management.base import BaseCommand

from orders.expiry import expire_unpaid_prepay_orders


class Command(BaseCommand):
    help = "Cancels unpaid prepaid orders that passed their payment deadline and restores stock."

    def handle(self, *args, **options):
        expired_count = expire_unpaid_prepay_orders()
        self.stdout.write(
            self.style.SUCCESS(
                f"Expired {expired_count} unpaid prepaid order(s)."
            )
        )
