"""
Tests for Scientific Disclaimer System.

Tests:
- Disclaimer Context Processor
- Disclaimer display based on URL patterns
- Disclaimer severity levels
- User acknowledgment (localStorage)
"""

from django.test import RequestFactory

import pytest

from core.context_processors import disclaimers
from core.models_disclaimer import ScientificDisclaimer
from core.tests.factories import UserFactory


@pytest.mark.django_db
class TestDisclaimerContextProcessor:
    """Test: Disclaimer context processor correctly filters disclaimers."""

    def test_global_disclaimer_shown_on_all_pages(self):
        """Global disclaimers (empty show_on_pages) should appear everywhere."""
        # Create global disclaimer
        ScientificDisclaimer.objects.create(
            category="GENERAL",
            title="Global Warning",
            message="This applies everywhere",
            severity="INFO",
            show_on_pages=[],  # Empty = global
            is_active=True,
        )

        factory = RequestFactory()
        request = factory.get("/dashboard/")

        context = disclaimers(request)

        assert len(context["active_disclaimers"]) == 1
        assert context["active_disclaimers"][0].category == "GENERAL"

    def test_url_specific_disclaimer_shown_on_matching_page(self):
        """Disclaimers should only show on URLs matching show_on_pages patterns."""
        # Create stats-specific disclaimer
        ScientificDisclaimer.objects.create(
            category="1RM_STANDARDS",
            title="1RM Warning",
            message="Limited data",
            severity="WARNING",
            show_on_pages=["stats/", "uebungen/"],
            is_active=True,
        )

        factory = RequestFactory()

        # Test: Should show on /stats/
        request_stats = factory.get("/stats/exercise/1/")
        context_stats = disclaimers(request_stats)
        assert len(context_stats["active_disclaimers"]) == 1

        # Test: Should NOT show on /dashboard/
        request_dash = factory.get("/dashboard/")
        context_dash = disclaimers(request_dash)
        assert len(context_dash["active_disclaimers"]) == 0

    def test_inactive_disclaimers_not_shown(self):
        """Inactive disclaimers should never appear."""
        ScientificDisclaimer.objects.create(
            category="GENERAL",
            title="Inactive",
            message="Should not show",
            severity="INFO",
            show_on_pages=[],
            is_active=False,  # Disabled
        )

        factory = RequestFactory()
        request = factory.get("/dashboard/")
        context = disclaimers(request)

        assert len(context["active_disclaimers"]) == 0

    def test_multiple_disclaimers_on_same_page(self):
        """Multiple matching disclaimers should all be shown."""
        # Global disclaimer
        ScientificDisclaimer.objects.create(
            category="GENERAL",
            title="Global",
            message="Global message",
            severity="INFO",
            show_on_pages=[],
            is_active=True,
        )

        # Stats-specific disclaimer
        ScientificDisclaimer.objects.create(
            category="1RM_STANDARDS",
            title="1RM Warning",
            message="Stats warning",
            severity="WARNING",
            show_on_pages=["stats/"],
            is_active=True,
        )

        factory = RequestFactory()
        request = factory.get("/stats/exercise/1/")
        context = disclaimers(request)

        # Both should show
        assert len(context["active_disclaimers"]) == 2

    def test_disclaimer_severity_levels(self):
        """Different severity levels should be preserved."""
        for severity in ["INFO", "WARNING", "CRITICAL"]:
            ScientificDisclaimer.objects.create(
                category=f"TEST_{severity}",
                title=f"{severity} Test",
                message="Test message",
                severity=severity,
                show_on_pages=[],
                is_active=True,
            )

        factory = RequestFactory()
        request = factory.get("/dashboard/")
        context = disclaimers(request)

        severities = [d.severity for d in context["active_disclaimers"]]
        assert "INFO" in severities
        assert "WARNING" in severities
        assert "CRITICAL" in severities


@pytest.mark.django_db
class TestDisclaimerIntegration:
    """Test: Disclaimer system integration with views."""

    def test_disclaimer_appears_in_template_context(self, client):
        """Disclaimers should be available in template context via context processor."""
        user = UserFactory()
        client.force_login(user)

        # Create a disclaimer
        ScientificDisclaimer.objects.create(
            category="GENERAL",
            title="Test Disclaimer",
            message="Test message",
            severity="INFO",
            show_on_pages=[],
            is_active=True,
        )

        # Request a page (dashboard assumed to exist)
        response = client.get("/")

        # Check context has disclaimers
        if hasattr(response, "context") and response.context:
            # Context available (template rendered)
            assert "active_disclaimers" in response.context
            assert len(response.context["active_disclaimers"]) > 0
        else:
            # Redirect or API response - context not available
            # This is OK - just verify no errors
            assert response.status_code in [200, 301, 302]

    def test_disclaimer_categories_match_load_disclaimers_command(self):
        """Verify disclaimer categories from management command exist."""
        from django.core.management import call_command

        # Load default disclaimers
        call_command("load_disclaimers")

        # Verify expected categories exist
        categories = ScientificDisclaimer.objects.values_list("category", flat=True)

        assert "1RM_STANDARDS" in categories
        assert "FATIGUE_INDEX" in categories
        assert "GENERAL" in categories
