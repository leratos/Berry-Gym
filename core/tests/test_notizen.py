"""
Tests für Phase 7.3 – Notizen erweitern.

Prüft:
- PlanUebung.notiz: Feld existiert, speichert korrekt
- Satz.notiz: kein max_length mehr
- training_list: Kommentar wird angezeigt
- training_session: plan_uebung_hinweise im Context
- edit_plan: notiz wird beim POST gespeichert
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Plan, PlanUebung, Satz, Trainingseinheit, Uebung, UserProfile  # noqa: F401


class TestPlanUebungNotiz(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("notiz_user", password="pw")
        self.uebung = Uebung.objects.create(
            bezeichnung="Kniebeuge",
            muskelgruppe="beine",
            gewichts_typ="barbell",
            is_custom=False,
        )
        self.plan = Plan.objects.create(user=self.user, name="Testplan")

    def test_planuebung_notiz_default_null(self):
        """PlanUebung ohne Notiz hat None."""
        pu = PlanUebung.objects.create(plan=self.plan, uebung=self.uebung)
        self.assertIsNone(pu.notiz)

    def test_planuebung_notiz_speichert(self):
        """PlanUebung.notiz wird korrekt gespeichert und geladen."""
        pu = PlanUebung.objects.create(
            plan=self.plan,
            uebung=self.uebung,
            notiz="Fersen auf dem Boden halten 🦵",
        )
        pu.refresh_from_db()
        self.assertEqual(pu.notiz, "Fersen auf dem Boden halten 🦵")

    def test_planuebung_notiz_leer_string_wird_none(self):
        """Leerer String wird in der View zu None normalisiert."""
        pu = PlanUebung.objects.create(plan=self.plan, uebung=self.uebung, notiz=None)
        self.assertIsNone(pu.notiz)


class TestSatzNotizKeinMaxLength(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("satz_user", password="pw")
        self.uebung = Uebung.objects.create(
            bezeichnung="Bankdrücken",
            muskelgruppe="brust",
            gewichts_typ="barbell",
            is_custom=False,
        )
        self.einheit = Trainingseinheit.objects.create(user=self.user)

    def test_satz_notiz_lang(self):
        """Satz.notiz akzeptiert Texte länger als 500 Zeichen."""
        langer_text = "x" * 600
        satz = Satz.objects.create(
            einheit=self.einheit,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=100,
            wiederholungen=5,
            notiz=langer_text,
        )
        satz.refresh_from_db()
        self.assertEqual(len(satz.notiz), 600)

    def test_satz_notiz_mit_emojis(self):
        """Emojis in Satz.notiz werden korrekt gespeichert."""
        notiz = "💪 Stärker | 🎯 PR | 🔥 Pump"
        satz = Satz.objects.create(
            einheit=self.einheit,
            uebung=self.uebung,
            satz_nr=1,
            gewicht=100,
            wiederholungen=5,
            notiz=notiz,
        )
        satz.refresh_from_db()
        self.assertEqual(satz.notiz, notiz)


class TestTrainingListKommentar(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("list_user", password="pw")
        self.client.login(username="list_user", password="pw")

    def test_kommentar_in_trainingsliste(self):
        """Kommentar wird in der Trainingsliste angezeigt."""
        Trainingseinheit.objects.create(user=self.user, kommentar="Schulter etwas müde heute")
        response = self.client.get(reverse("training_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Schulter etwas müde heute")

    def test_kein_kommentar_kein_icon(self):
        """Ohne Kommentar erscheint kein Chat-Icon."""
        Trainingseinheit.objects.create(user=self.user, kommentar=None)
        response = self.client.get(reverse("training_list"))
        self.assertEqual(response.status_code, 200)
        # Kein Fehler, Seite lädt korrekt
        self.assertNotContains(response, "bi-chat-left-text")


class TestTrainingSessionHinweise(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("session_user", password="pw")
        self.client.login(username="session_user", password="pw")
        self.uebung = Uebung.objects.create(
            bezeichnung="Deadlift",
            muskelgruppe="ruecken",
            gewichts_typ="barbell",
            is_custom=False,
        )
        self.plan = Plan.objects.create(user=self.user, name="Plan mit Hinweis")
        self.pu = PlanUebung.objects.create(
            plan=self.plan,
            uebung=self.uebung,
            notiz="Rücken gerade halten!",
        )
        self.einheit = Trainingseinheit.objects.create(user=self.user, plan=self.plan)

    def test_hinweis_im_context(self):
        """plan_uebung_hinweise im Context enthält die Übungsnotiz."""
        response = self.client.get(reverse("training_session", args=[self.einheit.id]))
        self.assertEqual(response.status_code, 200)
        hinweise = response.context["plan_uebung_hinweise"]
        self.assertIn(self.uebung.id, hinweise)
        self.assertEqual(hinweise[self.uebung.id], "Rücken gerade halten!")

    def test_hinweis_leer_wenn_kein_plan(self):
        """Ohne Plan ist plan_uebung_hinweise leer."""
        einheit_ohne_plan = Trainingseinheit.objects.create(user=self.user)
        response = self.client.get(reverse("training_session", args=[einheit_ohne_plan.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["plan_uebung_hinweise"], {})

    def test_hinweis_nur_wenn_notiz_gesetzt(self):
        """Übungen ohne Notiz erscheinen nicht in plan_uebung_hinweise."""
        uebung2 = Uebung.objects.create(
            bezeichnung="Rudern",
            muskelgruppe="ruecken",
            gewichts_typ="barbell",
            is_custom=False,
        )
        PlanUebung.objects.create(plan=self.plan, uebung=uebung2)  # notiz=None
        response = self.client.get(reverse("training_session", args=[self.einheit.id]))
        hinweise = response.context["plan_uebung_hinweise"]
        self.assertNotIn(uebung2.id, hinweise)


class TestEditPlanNotizPost(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("edit_user", password="pw")
        self.client.login(username="edit_user", password="pw")
        self.uebung = Uebung.objects.create(
            bezeichnung="Squat",
            muskelgruppe="beine",
            gewichts_typ="barbell",
            is_custom=False,
        )
        self.plan = Plan.objects.create(user=self.user, name="Editierplan")
        PlanUebung.objects.create(plan=self.plan, uebung=self.uebung)

    def test_notiz_wird_gespeichert(self):
        """Notiz aus POST wird in PlanUebung gespeichert."""
        self.client.post(
            reverse("edit_plan", args=[self.plan.id]),
            {
                "name": "Editierplan",
                "uebungen": [self.uebung.id],
                f"saetze_{self.uebung.id}": 3,
                f"wdh_{self.uebung.id}": "8-12",
                f"pause_{self.uebung.id}": 120,
                f"superset_gruppe_{self.uebung.id}": 0,
                f"notiz_{self.uebung.id}": "Schulterblätter einziehen",
            },
        )
        pu = PlanUebung.objects.get(plan=self.plan, uebung=self.uebung)
        self.assertEqual(pu.notiz, "Schulterblätter einziehen")

    def test_leere_notiz_wird_none(self):
        """Leerer Notiz-POST-Wert wird als None gespeichert."""
        self.client.post(
            reverse("edit_plan", args=[self.plan.id]),
            {
                "name": "Editierplan",
                "uebungen": [self.uebung.id],
                f"saetze_{self.uebung.id}": 3,
                f"wdh_{self.uebung.id}": "8-12",
                f"pause_{self.uebung.id}": 120,
                f"superset_gruppe_{self.uebung.id}": 0,
                f"notiz_{self.uebung.id}": "   ",  # nur Whitespace
            },
        )
        pu = PlanUebung.objects.get(plan=self.plan, uebung=self.uebung)
        self.assertIsNone(pu.notiz)
