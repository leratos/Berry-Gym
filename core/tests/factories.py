"""
Factory Boy Factories für Test-Daten.

Diese Factories erstellen realistische Test-Objekte für Models.
Verwendet in allen Tests um Boilerplate zu vermeiden.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User

import factory
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker("de_DE")  # Deutsche Fake-Daten


class UserFactory(DjangoModelFactory):
    """Factory für User-Objekte."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@homegym.test")
    first_name = factory.Faker("first_name", locale="de_DE")
    last_name = factory.Faker("last_name", locale="de_DE")
    is_active = True
    is_staff = False

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        """Set password for user."""
        if extracted:
            obj.set_password(extracted)
        else:
            obj.set_password("testpass123")


class UebungFactory(DjangoModelFactory):
    """Factory für Übungen."""

    class Meta:
        model = "core.Uebung"
        django_get_or_create = ("bezeichnung",)

    bezeichnung = factory.Sequence(lambda n: f"Übung {n}")
    muskelgruppe = "BRUST"
    hilfsmuskeln = factory.LazyFunction(lambda: ["TRIZEPS", "SCHULTER_VORN"])
    gewichts_typ = "GESAMT"
    bewegungstyp = "DRUECKEN"
    beschreibung = factory.Faker("text", max_nb_chars=200, locale="de_DE")
    is_custom = False
    created_by = None

    # 1RM Standards (optional)
    standard_beginner = Decimal("60.0")
    standard_intermediate = Decimal("80.0")
    standard_advanced = Decimal("100.0")
    standard_elite = Decimal("130.0")


class CustomUebungFactory(UebungFactory):
    """Factory für custom user-spezifische Übungen."""

    is_custom = True
    created_by = factory.SubFactory(UserFactory)


class PlanFactory(DjangoModelFactory):
    """Factory für Trainingspläne."""

    class Meta:
        model = "core.Plan"

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Trainingsplan {n}")
    beschreibung = factory.Faker("text", max_nb_chars=300, locale="de_DE")
    is_public = False


class PlanUebungFactory(DjangoModelFactory):
    """Factory für Plan-Übungen Zuordnungen."""

    class Meta:
        model = "core.PlanUebung"

    plan = factory.SubFactory(PlanFactory)
    uebung = factory.SubFactory(UebungFactory)
    reihenfolge = factory.Sequence(lambda n: n + 1)
    saetze_ziel = 3
    wiederholungen_ziel = "10"
    pausenzeit = 90
    trainingstag = ""
    superset_gruppe = 0


class TrainingseinheitFactory(DjangoModelFactory):
    """Factory für Trainingseinheiten."""

    class Meta:
        model = "core.Trainingseinheit"

    user = factory.SubFactory(UserFactory)
    plan = factory.SubFactory(PlanFactory, user=factory.SelfAttribute("..user"))
    dauer_minuten = factory.Faker("random_int", min=30, max=120)
    kommentar = factory.Faker("sentence", locale="de_DE")
    ist_deload = False

    @factory.lazy_attribute
    def datum(self):
        """Random date within last 90 days."""
        days_ago = fake.random_int(min=0, max=90)
        return datetime.now() - timedelta(days=days_ago)


class SatzFactory(DjangoModelFactory):
    """Factory für einzelne Sätze."""

    class Meta:
        model = "core.Satz"

    einheit = factory.SubFactory(TrainingseinheitFactory)
    uebung = factory.SubFactory(UebungFactory)
    satz_nr = factory.Sequence(lambda n: n + 1)
    gewicht = factory.Faker(
        "pydecimal", left_digits=3, right_digits=2, min_value=20, max_value=200, positive=True
    )
    wiederholungen = factory.Faker("random_int", min=1, max=20)
    ist_aufwaermsatz = False
    rpe = factory.Faker(
        "pydecimal", left_digits=1, right_digits=1, min_value=6.0, max_value=9.5, positive=True
    )
    notiz = factory.Faker("sentence", locale="de_DE", nb_words=6)
    superset_gruppe = 0


class AufwaermsatzFactory(SatzFactory):
    """Factory für Aufwärmsätze."""

    ist_aufwaermsatz = True
    gewicht = factory.Faker(
        "pydecimal", left_digits=2, right_digits=2, min_value=20, max_value=60, positive=True
    )
    rpe = factory.Faker(
        "pydecimal", left_digits=1, right_digits=1, min_value=3.0, max_value=6.5, positive=True
    )


class KoerperWerteFactory(DjangoModelFactory):
    """Factory für Körperwerte."""

    class Meta:
        model = "core.KoerperWerte"

    user = factory.SubFactory(UserFactory)
    groesse_cm = factory.Faker("random_int", min=160, max=200)
    gewicht = factory.Faker(
        "pydecimal", left_digits=3, right_digits=2, min_value=60, max_value=120, positive=True
    )
    koerperfett_prozent = factory.Faker(
        "pydecimal", left_digits=2, right_digits=1, min_value=8.0, max_value=30.0, positive=True
    )
    muskelmasse_kg = factory.LazyAttribute(
        lambda obj: obj.gewicht * (1 - obj.koerperfett_prozent / 100) * Decimal("0.85")
    )


class EquipmentFactory(DjangoModelFactory):
    """Factory für Equipment."""

    class Meta:
        model = "core.Equipment"
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"EQUIPMENT_{n}")
    beschreibung = factory.Faker("text", max_nb_chars=100, locale="de_DE")


class CardioEinheitFactory(DjangoModelFactory):
    """Factory für Cardio-Einheiten."""

    class Meta:
        model = "core.CardioEinheit"

    user = factory.SubFactory(UserFactory)
    aktivitaet = factory.Iterator(["LAUFEN", "RADFAHREN", "SCHWIMMEN"])
    dauer_minuten = factory.Faker("random_int", min=20, max=90)
    intensitaet = factory.Iterator(["LEICHT", "MODERAT", "INTENSIV"])
    notiz = factory.Faker("sentence", locale="de_DE")

    @factory.lazy_attribute
    def datum(self):
        """Random date within last 30 days."""
        days_ago = fake.random_int(min=0, max=30)
        return (datetime.now() - timedelta(days=days_ago)).date()
