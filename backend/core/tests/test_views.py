from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from core.models import User, StoredLibrary, Framework, RequirementNode

class LibraryTreeAPITests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="admin_test@example.com",
            password="Password123!",
            first_name="Admin",
            last_name="Test"
        )
        self.normal_user = User.objects.create_user(
            email="user_test@example.com",
            password="Password123!",
            first_name="User",
            last_name="Test"
        )
        self.stored_lib = StoredLibrary.objects.create(
            name="Test ISO Library",
            urn="urn:custom:test:iso-library",
            version=1,
            hash_checksum="abc123hash",
            content={"framework": {"name": "Test ISO"}}
        )
        self.framework = Framework.objects.create(
            name="Test Framework",
            urn="urn:custom:test:framework"
        )
        self.domain_node = RequirementNode.objects.create(
            framework=self.framework,
            urn="urn:custom:test:domain1",
            name="Domain 1",
            assessable=False
        )
        self.control_node = RequirementNode.objects.create(
            framework=self.framework,
            urn="urn:custom:test:ctrl1",
            parent_urn="urn:custom:test:domain1",
            name="Control 1",
            assessable=True
        )

    def test_stored_library_retrieve_authenticated(self):
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(user=self.normal_user)
        url = f"/api/stored-libraries/{self.stored_lib.id}/"
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("name"), "Test ISO Library")

    def test_stored_library_retrieve_unauthenticated(self):
        client = APIClient(HTTP_HOST="localhost")
        url = f"/api/stored-libraries/{self.stored_lib.id}/"
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_requirement_nodes_tree_authenticated(self):
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(user=self.normal_user)
        url = "/api/requirement-nodes/tree/"
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        self.assertTrue(len(results) > 0)

    def test_requirement_nodes_tree_unauthenticated(self):
        client = APIClient(HTTP_HOST="localhost")
        url = "/api/requirement-nodes/tree/"
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
