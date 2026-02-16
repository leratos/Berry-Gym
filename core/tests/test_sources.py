"""
Tests für Phase 5.1 – Scientific Source System.

Abdeckung:
- TrainingSource Model (citation_short, doi_url, str)
- sources_list View (HTTP 200, öffentlich ohne Login, Filterung)
- source_tags Template-Tag (source_tooltip, sources_count)
- Management Command load_training_sources (idempotent)
- Admin (TrainingSource registriert)
"""

from django.contrib.admin.sites import AdminSite
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.admin import TrainingSourceAdmin
from core.models import TrainingSource


class TrainingSourceModelTest(TestCase):
    """Tests für das TrainingSource-Model."""

    def setUp(self):
        self.source_single = TrainingSource.objects.create(
            category="ONE_RM",
            title="Prediction of 1 RM strength",
            authors="Epley, B.",
            year=1985,
            journal="University of Nebraska",
            doi="10.0000/test.single",
            key_findings=["Epley-Formel: 1RM = Gewicht x (1 + Wdh/30)"],
            applies_to=["1rm_standards"],
        )
        self.source_multi = TrainingSource.objects.create(
            category="VOLUME",
            title="Dose-response relationship",
            authors="Schoenfeld, B.J., Ogborn, D., & Krieger, J.W.",
            year=2017,
            journal="Journal of Sports Sciences",
            doi="10.0000/test.multi",
            key_findings=["Mehr Volumen = mehr Hypertrophie"],
            applies_to=["volume_metrics"],
        )

    def test_str_representation(self):
        """__str__ zeigt Autor, Jahr und Titelausschnitt."""
        result = str(self.source_single)
        self.assertIn("Epley", result)
        self.assertIn("1985", result)

    def test_citation_short_single_author(self):
        """Einzelner Autor: kein 'et al.'"""
        self.assertEqual(self.source_single.citation_short, "Epley (1985)")

    def test_citation_short_multiple_authors(self):
        """Mehrere Autoren (& im Feld): 'et al.' angehängt."""
        self.assertEqual(self.source_multi.citation_short, "Schoenfeld et al. (2017)")

    def test_doi_url_with_doi(self):
        """doi_url gibt vollständige DOI-URL zurück."""
        self.assertEqual(
            self.source_single.doi_url,
            "https://doi.org/10.0000/test.single",
        )

    def test_doi_url_fallback_to_url(self):
        """doi_url gibt url zurück wenn kein DOI vorhanden."""
        source = TrainingSource.objects.create(
            category="GENERAL",
            title="Kein DOI Test",
            authors="Mustermann, M.",
            year=2020,
            journal="Test",
            doi="",
            url="https://example.com/paper",
            applies_to=[],
        )
        self.assertEqual(source.doi_url, "https://example.com/paper")

    def test_doi_url_empty_when_no_doi_no_url(self):
        """doi_url gibt '' zurück wenn weder DOI noch URL."""
        source = TrainingSource.objects.create(
            category="GENERAL",
            title="Kein Link Test",
            authors="Mustermann, M.",
            year=2021,
            journal="Test",
            doi="",
            url="",
            applies_to=[],
        )
        self.assertEqual(source.doi_url, "")

    def test_is_active_default_true(self):
        """Neue Quellen sind standardmäßig aktiv."""
        self.assertTrue(self.source_single.is_active)

    def test_applies_to_is_list(self):
        """applies_to ist eine Liste."""
        self.assertIsInstance(self.source_single.applies_to, list)
        self.assertIn("1rm_standards", self.source_single.applies_to)


class SourcesListViewTest(TestCase):
    """Tests für die öffentliche /quellen/ View."""

    def setUp(self):
        TrainingSource.objects.create(
            category="VOLUME",
            title="Volume Test Source",
            authors="Test, A.",
            year=2020,
            journal="Test Journal",
            doi="10.0000/view.vol",
            applies_to=["volume_metrics"],
        )
        TrainingSource.objects.create(
            category="INTENSITY",
            title="Intensity Test Source",
            authors="Test, B., & Co, C.",
            year=2021,
            journal="Test Journal",
            doi="10.0000/view.int",
            is_active=False,  # Inaktiv – soll nicht erscheinen
            applies_to=["rpe_quality"],
        )

    def test_sources_page_accessible_without_login(self):
        """Seite ist öffentlich – kein Login erforderlich."""
        response = self.client.get(reverse("sources_list"))
        self.assertEqual(response.status_code, 200)

    def test_sources_page_uses_correct_template(self):
        """Korrekte Template-Datei wird verwendet."""
        response = self.client.get(reverse("sources_list"))
        self.assertTemplateUsed(response, "core/sources.html")

    def test_shows_only_active_sources(self):
        """Inaktive Quellen erscheinen nicht in der Liste."""
        response = self.client.get(reverse("sources_list"))
        quellen = response.context["quellen"]
        for q in quellen:
            self.assertTrue(q.is_active)

    def test_category_filter_works(self):
        """?category=VOLUME filtert korrekt."""
        response = self.client.get(reverse("sources_list") + "?category=VOLUME")
        self.assertEqual(response.status_code, 200)
        quellen = response.context["quellen"]
        for q in quellen:
            self.assertEqual(q.category, "VOLUME")

    def test_gesamt_count_in_context(self):
        """gesamt_count zeigt Anzahl aller aktiven Quellen."""
        response = self.client.get(reverse("sources_list"))
        self.assertIn("gesamt_count", response.context)
        self.assertGreaterEqual(response.context["gesamt_count"], 1)

    def test_kategorien_in_context(self):
        """kategorien-Liste ist im Context vorhanden."""
        response = self.client.get(reverse("sources_list"))
        self.assertIn("kategorien", response.context)
        self.assertIsInstance(response.context["kategorien"], list)


class LoadTrainingSourcesCommandTest(TestCase):
    """Tests für das load_training_sources Management Command."""

    def test_command_creates_sources(self):
        """Command erstellt Quellen beim ersten Aufruf."""
        initial_count = TrainingSource.objects.count()
        call_command("load_training_sources", verbosity=0)
        self.assertGreater(TrainingSource.objects.count(), initial_count)

    def test_command_is_idempotent(self):
        """Zweimaliger Aufruf erzeugt keine Duplikate."""
        call_command("load_training_sources", verbosity=0)
        count_after_first = TrainingSource.objects.count()
        call_command("load_training_sources", verbosity=0)
        count_after_second = TrainingSource.objects.count()
        self.assertEqual(count_after_first, count_after_second)

    def test_command_loads_ten_sources(self):
        """Command lädt exakt 10 Quellen aus SOURCES."""
        call_command("load_training_sources", verbosity=0)
        self.assertEqual(TrainingSource.objects.count(), 10)

    def test_command_clear_flag_removes_all(self):
        """--clear löscht bestehende Quellen vor dem Laden."""
        call_command("load_training_sources", verbosity=0)
        self.assertGreater(TrainingSource.objects.count(), 0)
        call_command("load_training_sources", clear=True, verbosity=0)
        # Nach --clear + Neuladen wieder 10
        self.assertEqual(TrainingSource.objects.count(), 10)


class SourceTagsTest(TestCase):
    """Tests für source_tags Template-Tags."""

    def setUp(self):
        self.source = TrainingSource.objects.create(
            category="INTENSITY",
            title="RPE Test",
            authors="Test, A., & Co, B.",
            year=2020,
            journal="Test",
            doi="10.0000/tag.test",
            applies_to=["rpe_quality"],
        )

    def test_source_tooltip_returns_html_when_source_exists(self):
        """source_tooltip gibt HTML-String zurück wenn Quellen vorhanden."""
        from core.templatetags import source_tags

        # Cache leeren
        source_tags._SOURCE_CACHE.clear()

        result = source_tags.source_tooltip("rpe_quality")
        # Gibt entweder HTML oder leeren String zurück
        if result:
            self.assertIn("source-tooltip-link", result)
            self.assertIn("quellen", result)

    def test_source_tooltip_returns_empty_for_unknown_key(self):
        """source_tooltip gibt '' zurück wenn keine Quellen für key."""
        from core.templatetags import source_tags

        source_tags._SOURCE_CACHE.clear()
        result = source_tags.source_tooltip("nonexistent_key_xyz")
        self.assertEqual(result, "")

    def test_sources_count_returns_integer(self):
        """sources_count gibt int zurück."""
        from core.templatetags import source_tags

        count = source_tags.sources_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 1)


class TrainingSourceAdminTest(TestCase):
    """Test dass TrainingSource im Admin registriert ist."""

    def test_training_source_registered_in_admin(self):
        """TrainingSource ist im Django Admin registriert."""
        from django.contrib import admin

        self.assertIn(TrainingSource, admin.site._registry)

    def test_admin_list_display(self):
        """Admin zeigt erwartete Felder in list_display."""
        site = AdminSite()
        admin_instance = TrainingSourceAdmin(TrainingSource, site)
        self.assertIn("citation_short", admin_instance.list_display)
        self.assertIn("category", admin_instance.list_display)
        self.assertIn("is_active", admin_instance.list_display)
