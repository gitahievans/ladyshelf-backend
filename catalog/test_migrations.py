from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ProductPublicationMigrationTests(TransactionTestCase):
    migrate_from = [("catalog", "0002_productvariant_image_url")]
    migrate_to = [("catalog", "0003_product_is_published")]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        Product = old_apps.get_model("catalog", "Product")
        self.existing_product_ids = list(Product.objects.values_list("pk", flat=True))

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
        super().tearDown()

    def test_existing_products_are_published_and_new_default_is_false(self):
        Product = self.apps.get_model("catalog", "Product")

        self.assertTrue(self.existing_product_ids)
        self.assertFalse(
            Product.objects.filter(
                pk__in=self.existing_product_ids,
                is_published=False,
            ).exists()
        )
        self.assertFalse(Product._meta.get_field("is_published").default)
