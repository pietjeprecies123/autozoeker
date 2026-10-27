"""Printable viewing / test-drive checklist: generic Dutch checks + model-specific issues."""

from __future__ import annotations

from app.knowledge.service import IssueMatch
from app.models import Listing, Vehicle

GENERIC: list[tuple[str, list[str]]] = [
    ("Voor je gaat", [
        "Vraag het kenteken en check het in Autozoeker (RDW: APK, NAP, terugroepacties, import).",
        "Vraag of de onderhoudshistorie compleet is (boekje of facturen) en laat foto's sturen.",
        "Particulier: vraag of de auto op naam van de verkoper staat en of er geen financiering/lease op loopt.",
        "Plan de bezichtiging bij daglicht en vraag de auto koud te laten staan (geen voorverwarmde motor).",
    ]),
    ("Documenten", [
        "Kentekencard + tenaamstellingscode (of digitale registratie) – naam = verkoper.",
        "Onderhoudsboekje/facturen; kloppen datums en kilometerstanden?",
        "NAP-tellerrapport (dealer: verplicht bij BOVAG) en eerdere APK-rapporten.",
        "Twee sleutels aanwezig? Een extra sleutel kost vaak €200–500.",
        "Dealer: garantievoorwaarden schriftelijk; BOVAG-garantie geldt alleen bij BOVAG-leden.",
    ]),
    ("Exterieur", [
        "Kleurverschil, ongelijke naden of overspuitnevel → mogelijke schadehistorie.",
        "Roest op dorpels, wielkasten en onder de deuren.",
        "Banden: profiel (≥ 3 mm prettig), DOT-code (ouder dan 6 jaar = vervangen), scheve slijtage → uitlijning/ophanging.",
        "Ruiten (sterretjes), verlichting, spiegels en camera's.",
    ]),
    ("Interieur", [
        "Slijtage van stuur, pook, pedalen en bestuurdersstoel past bij de kilometerstand?",
        "Geur van vocht of rook; voel onder de matten naar natte vloer.",
        "Contact aan: alle waarschuwingslampjes gaan aan en daarna weer uit.",
        "Test airco (koud), verwarming, ramen, stoelverwarming, infotainment, camera, sensoren.",
    ]),
    ("Motorruimte (koude motor)", [
        "Koude start: luister naar tikken, rammelen of lang starten; let op rook uit de uitlaat.",
        "Oliepeil en -kleur; mayonaise onder de dop kan op koppakking wijzen.",
        "Koelvloeistof op niveau en schoon (geen olie).",
        "Lekkages onder de auto na stilstaan.",
    ]),
    ("Proefrit (minimaal 20 minuten, incl. snelweg)", [
        "Rijdt rechtuit los van het stuur; trekt niet bij remmen.",
        "Remmen zonder trillingen in het stuur of pedaal.",
        "Alle versnellingen soepel; automaat schakelt zonder schokken of slippen.",
        "Koppeling: aangrijppunt niet helemaal bovenin (anders versleten).",
        "Geen klunken over drempels; geen zoemende wiellagers op de snelweg.",
        "Cruise control, rijhulpsystemen en klimaat werken onderweg.",
    ]),
    ("Afronding", [
        "Laat bij twijfel een aankoopkeuring doen (ANWB/BOVAG/onafhankelijk, ca. €150–250).",
        "Particulier: maak een koopovereenkomst (ANWB-model) en schrijf direct over bij RDW-loket, postkantoor of online.",
        "Betaal grote bedragen niet contant; nooit vooraf aanbetalen zonder de auto te hebben gezien.",
        "Bewaar het vrijwaringsbewijs en het overschrijvingsbewijs.",
    ]),
]

EV_CHECKS = [
    "Vraag een batterijrapport (State of Health, bijv. Aviloo of dealer-uitlezing); <85% bij jonge auto is opvallend.",
    "Laad 100%: welke actieradius geeft de auto aan? Vergelijk met de WLTP-waarde.",
    "Test snelladen (DC) en AC-laden; zit de laadkabel erbij (type 2)?",
    "Warmtepomp aanwezig? Scheelt in de winter veel actieradius.",
    "Check de batterijgarantie (jaren/km, minimale SoH) en of die overdraagbaar is.",
    "12V-accu: vreemde foutmeldingen of opstartproblemen zijn vaak een zwakke 12V-accu.",
]
PHEV_CHECKS = [
    "Rij een stuk volledig elektrisch: schakelt de motor onverwacht bij?",
    "Elektrische actieradius bij volle accu vergelijken met de WLTP-waarde.",
    "Laadkabel aanwezig en laadpoort onbeschadigd.",
]
HYBRID_CHECKS = [
    "Hybride-systeem: soepele overgang tussen elektrisch en benzine, geen waarschuwingen.",
    "Vraag naar de hybride-batterijcheck in het onderhoudsboekje (bij Toyota verlengt die vaak de garantie).",
]


def build(listing: Listing, vehicle: Vehicle | None, issues: list[IssueMatch]) -> dict:
    sections = [{"title": t, "items": list(items)} for t, items in GENERIC]
    if listing.fuel == "elektrisch":
        sections.insert(5, {"title": "Elektrische auto", "items": EV_CHECKS})
    elif listing.fuel == "plugin_hybride":
        sections.insert(5, {"title": "Plug-in hybride", "items": PHEV_CHECKS + EV_CHECKS[:1]})
    elif listing.fuel == "hybride":
        sections.insert(5, {"title": "Hybride", "items": HYBRID_CHECKS})

    car_items: list[str] = []
    if vehicle and vehicle.found:
        if vehicle.open_recall:
            car_items.append("Er staat een terugroepactie open: laat de dealer die vóór aflevering uitvoeren.")
        if vehicle.is_import:
            car_items.append("Importauto: vraag buitenlandse onderhoudshistorie en km-bewijs van vóór de import.")
        if (vehicle.odometer_judgement or "").lower().startswith("onlogisch"):
            car_items.append("NAP onlogisch: vraag een verklaring en documenten; zonder goede uitleg niet kopen.")
        if vehicle.taxi:
            car_items.append("Ex-taxi: check stoelen, stuur en vering extra kritisch.")
    for fl in listing.red_flags or []:
        if fl.get("severity") in ("high", "medium"):
            car_items.append(f"{fl['title']}: {fl.get('detail', '')}".strip(": "))
    if car_items:
        sections.insert(0, {"title": "Specifiek voor deze auto", "items": car_items})

    model_questions: list[dict] = []
    for m in issues:
        model_questions.append({
            "title": m.issue.get("title"),
            "severity": m.issue.get("severity"),
            "certainty": m.certainty,
            "recall_status": m.recall_status,
            "questions": m.issue.get("questions", []),
            "verify": m.issue.get("verify", []),
            "test_drive": m.issue.get("test_drive", []),
        })
    return {"sections": sections, "model_issues": model_questions}
