from django.test import TestCase

from .models import Project, ProjectEmployee


class ProjectModelTests(TestCase):
    """
    Model/serializer-level tests that don't require auth to be wired up
    yet (the users/auth app is still in progress). Once login exists,
    add ProjectAPITests using APIClient + force_authenticate.
    """

    def test_str_representation(self):
        project = Project(code="HVR-2024-018", name="Harbor View Residences")
        self.assertEqual(str(project), "HVR-2024-018 — Harbor View Residences")

    def test_default_status_is_planning(self):
        project = Project(
            code="TST-001",
            name="Test Project",
            project_type=Project.TYPE_WHOLE_BUILDING,
            start_date="2026-09-01",
            contract_value=1000000,
        )
        self.assertEqual(project.status, Project.STATUS_PLANNING)

    def test_allowed_transitions_from_planning(self):
        allowed = Project.ALLOWED_TRANSITIONS[Project.STATUS_PLANNING]
        self.assertIn(Project.STATUS_ACTIVE, allowed)
        self.assertIn(Project.STATUS_CANCELLED, allowed)
        self.assertNotIn(Project.STATUS_COMPLETED, allowed)

    def test_completed_is_a_final_status(self):
        self.assertEqual(Project.ALLOWED_TRANSITIONS[Project.STATUS_COMPLETED], set())


class ProjectSerializerStatusTransitionTests(TestCase):
    def test_rejects_invalid_transition(self):
        from .serializers import ProjectSerializer

        instance = Project(status=Project.STATUS_COMPLETED)
        serializer = ProjectSerializer(instance=instance, data={}, partial=True)
        serializer.instance = instance
        with self.assertRaises(Exception):
            serializer.run_validation({"status": Project.STATUS_ACTIVE})

    def test_allows_same_status(self):
        from .serializers import ProjectSerializer

        instance = Project(status=Project.STATUS_ACTIVE)
        serializer = ProjectSerializer()
        serializer.instance = instance
        result = serializer.validate_status(Project.STATUS_ACTIVE)
        self.assertEqual(result, Project.STATUS_ACTIVE)