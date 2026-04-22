from django.core.management.base import BaseCommand

from common.admin_roles import bootstrap_admin_groups


class Command(BaseCommand):
    help = "Create and sync the Owner and Attendant admin groups."

    def handle(self, *args, **options):
        role_counts = bootstrap_admin_groups()

        for role_name, permission_count in role_counts.items():
            self.stdout.write(
                self.style.SUCCESS(
                    f"{role_name} group synced with {permission_count} permissions."
                )
            )
