from django.test import TestCase

from .models import Phase, Project, ProjectEmployee


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


class PhaseModelTests(TestCase):
    """Project Planning (Phases) — same managed=False testing constraints
    as ProjectModelTests above: model/serializer logic only, no DB hits."""

    def test_str_representation(self):
        phase = Phase(sequence_number=1, name="Foundation")
        self.assertIn("Foundation", str(phase))

    def test_default_status_is_not_started(self):
        phase = Phase(name="Foundation", sequence_number=1)
        self.assertEqual(phase.status, Phase.STATUS_NOT_STARTED)

    def test_allowed_transitions_from_not_started(self):
        allowed = Phase.ALLOWED_TRANSITIONS[Phase.STATUS_NOT_STARTED]
        self.assertEqual(allowed, {Phase.STATUS_IN_PROGRESS})

    def test_completed_is_final(self):
        self.assertEqual(Phase.ALLOWED_TRANSITIONS[Phase.STATUS_COMPLETED], set())


class PhaseSerializerTests(TestCase):
    def test_rejects_invalid_status_transition(self):
        from .serializers import PhaseSerializer

        instance = Phase(status=Phase.STATUS_COMPLETED)
        serializer = PhaseSerializer()
        serializer.instance = instance
        with self.assertRaises(Exception):
            serializer.validate_status(Phase.STATUS_IN_PROGRESS)

    def test_allows_same_status(self):
        from .serializers import PhaseSerializer

        instance = Phase(status=Phase.STATUS_IN_PROGRESS)
        serializer = PhaseSerializer()
        serializer.instance = instance
        self.assertEqual(
            serializer.validate_status(Phase.STATUS_IN_PROGRESS), Phase.STATUS_IN_PROGRESS
        )

    def test_end_date_before_start_date_rejected(self):
        from .serializers import PhaseSerializer

        serializer = PhaseSerializer()
        serializer.instance = None
        with self.assertRaises(Exception):
            serializer.validate({"start_date": "2026-09-10", "end_date": "2026-09-01"})

    def test_completing_a_phase_auto_sets_full_progress(self):
        from decimal import Decimal

        from .serializers import PhaseSerializer

        instance = Phase(status=Phase.STATUS_IN_PROGRESS, progress_percentage=Decimal("60.00"))
        serializer = PhaseSerializer()
        serializer.instance = instance
        result = serializer.validate({"status": Phase.STATUS_COMPLETED})
        self.assertEqual(result["progress_percentage"], Decimal("100.00"))

    def test_explicit_progress_not_overridden_when_completing(self):
        from decimal import Decimal

        from .serializers import PhaseSerializer

        instance = Phase(status=Phase.STATUS_IN_PROGRESS, progress_percentage=Decimal("60.00"))
        serializer = PhaseSerializer()
        serializer.instance = instance
        result = serializer.validate(
            {"status": Phase.STATUS_COMPLETED, "progress_percentage": Decimal("95.00")}
        )
        self.assertEqual(result["progress_percentage"], Decimal("95.00"))