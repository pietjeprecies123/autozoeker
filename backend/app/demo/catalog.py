"""Catalogue used to generate the DEMO dataset.

Prices are rough Dutch list prices (€) for a typical trim when new; they only need to be plausible
enough to make the valuation and scoring demo meaningful. Nothing here is used for real listings.

Each trim: (title, fuel, kW, transmission, battery_kWh or None, new_price_factor[, (min_year, max_year)])
"""

from __future__ import annotations

# (make, model, popularity weight, base new price €, value retention factor, trims)
CATALOG: list[tuple[str, str, float, int, float, list[tuple]]] = [
    ("volkswagen", "golf", 10, 31000, 1.00, [
        ("1.0 TSI Trendline", "benzine", 81, "handgeschakeld", None, 0.85),
        ("1.4 TSI Highline", "benzine", 92, "handgeschakeld", None, 1.0, (None, 2019)),
        ("1.5 TSI Comfortline", "benzine", 110, "handgeschakeld", None, 1.0),
        ("1.6 TDI Comfortline", "diesel", 85, "handgeschakeld", None, 1.0, (None, 2019)),
        ("2.0 TDI Highline DSG", "diesel", 110, "automaat", None, 1.15),
        ("1.0 eTSI Life DSG", "hybride", 81, "automaat", None, 0.95, (2020, None)),
        ("1.5 eTSI Style DSG", "hybride", 110, "automaat", None, 1.1, (2020, None)),
        ("1.4 TSI DSG Highline", "benzine", 92, "automaat", None, 1.05, (None, 2019)),
        ("GTI Performance DSG", "benzine", 180, "automaat", None, 1.5),
        ("1.4 GTE DSG", "plugin_hybride", 150, "automaat", 13.0, 1.35, (2015, None)),
    ]),
    ("volkswagen", "polo", 8, 22000, 1.0, [
        ("1.0 MPI Trendline", "benzine", 48, "handgeschakeld", None, 0.85),
        ("1.0 TSI Comfortline", "benzine", 70, "handgeschakeld", None, 1.0),
        ("1.0 TSI Highline DSG", "benzine", 85, "automaat", None, 1.12),
        ("1.2 TSI Highline", "benzine", 66, "handgeschakeld", None, 1.0, (None, 2017)),
    ]),
    ("volkswagen", "up", 5, 14500, 1.0, [
        ("1.0 move up!", "benzine", 44, "handgeschakeld", None, 0.95),
        ("1.0 high up!", "benzine", 55, "handgeschakeld", None, 1.05),
        ("e-up! 32 kWh", "elektrisch", 61, "automaat", 32.3, 1.7, (2020, 2023)),
    ]),
    ("volkswagen", "t-roc", 6, 33000, 1.0, [
        ("1.0 TSI Style", "benzine", 81, "handgeschakeld", None, 0.95),
        ("1.5 TSI Sport DSG", "benzine", 110, "automaat", None, 1.1),
        ("2.0 TSI R 4Motion", "benzine", 221, "automaat", None, 1.55),
    ]),
    ("volkswagen", "tiguan", 6, 41000, 1.0, [
        ("1.4 TSI Comfortline", "benzine", 110, "handgeschakeld", None, 0.95, (None, 2019)),
        ("1.5 TSI Life DSG", "benzine", 110, "automaat", None, 1.0),
        ("2.0 TDI Highline 4Motion DSG", "diesel", 140, "automaat", None, 1.2),
        ("1.4 TSI eHybrid Elegance", "plugin_hybride", 180, "automaat", 13.0, 1.2, (2021, None)),
    ]),
    ("volkswagen", "id-3", 6, 41000, 0.92, [
        ("Pure 45 kWh", "elektrisch", 110, "automaat", 45.0, 0.9),
        ("Pro 58 kWh", "elektrisch", 150, "automaat", 58.0, 1.0),
        ("Pro S 77 kWh", "elektrisch", 150, "automaat", 77.0, 1.15),
    ]),
    ("volkswagen", "id-4", 4, 50000, 0.92, [
        ("Pure 52 kWh", "elektrisch", 125, "automaat", 52.0, 0.9),
        ("Pro 77 kWh", "elektrisch", 150, "automaat", 77.0, 1.0),
        ("GTX 4Motion 77 kWh", "elektrisch", 220, "automaat", 77.0, 1.15),
    ]),
    ("peugeot", "208", 9, 24500, 0.97, [
        ("1.2 PureTech Active", "benzine", 55, "handgeschakeld", None, 0.9),
        ("1.2 PureTech Allure", "benzine", 74, "handgeschakeld", None, 1.0),
        ("1.2 PureTech GT-Line EAT8", "benzine", 96, "automaat", None, 1.15, (2019, None)),
        ("e-208 GT 50 kWh", "elektrisch", 100, "automaat", 50.0, 1.5, (2020, None)),
    ]),
    ("peugeot", "2008", 6, 30000, 0.97, [
        ("1.2 PureTech Allure", "benzine", 96, "handgeschakeld", None, 1.0),
        ("1.2 PureTech GT EAT8", "benzine", 96, "automaat", None, 1.12),
        ("e-2008 Allure 50 kWh", "elektrisch", 100, "automaat", 50.0, 1.35, (2020, None)),
    ]),
    ("peugeot", "308", 5, 31000, 0.95, [
        ("1.2 PureTech Allure", "benzine", 96, "handgeschakeld", None, 1.0),
        ("1.5 BlueHDi Blue Lease Executive", "diesel", 96, "handgeschakeld", None, 1.0),
        ("1.6 HYbrid 180 GT EAT8", "plugin_hybride", 133, "automaat", 12.4, 1.3, (2020, None)),
    ]),
    ("peugeot", "3008", 4, 39000, 0.95, [
        ("1.2 PureTech Allure", "benzine", 96, "handgeschakeld", None, 0.95),
        ("1.2 PureTech GT-Line EAT8", "benzine", 96, "automaat", None, 1.05),
        ("1.6 HYbrid 225 GT EAT8", "plugin_hybride", 165, "automaat", 13.2, 1.25, (2020, None)),
        ("1.5 BlueHDi Allure", "diesel", 96, "handgeschakeld", None, 1.0),
    ]),
    ("kia", "picanto", 7, 16000, 1.05, [
        ("1.0 MPi ComfortPlusLine", "benzine", 49, "handgeschakeld", None, 1.0),
        ("1.0 DPi GT-Line", "benzine", 49, "handgeschakeld", None, 1.15),
        ("1.0 MPi DynamicLine AMT", "benzine", 49, "automaat", None, 1.05),
    ]),
    ("kia", "niro", 7, 36000, 1.02, [
        ("1.6 GDi Hybrid DynamicLine", "hybride", 104, "automaat", None, 0.9),
        ("e-Niro ExecutiveLine 64 kWh", "elektrisch", 150, "automaat", 64.0, 1.2, (2019, None)),
        ("1.6 GDi PHEV DynamicPlusLine", "plugin_hybride", 104, "automaat", 8.9, 1.05, (2017, None)),
    ]),
    ("kia", "sportage", 5, 40000, 1.02, [
        ("1.6 GDI ComfortLine", "benzine", 97, "handgeschakeld", None, 0.85, (None, 2021)),
        ("1.6 T-GDi Hybrid DynamicLine", "hybride", 169, "automaat", None, 1.0, (2022, None)),
        ("1.6 T-GDi PHEV GT-Line AWD", "plugin_hybride", 195, "automaat", 13.8, 1.2, (2022, None)),
    ]),
    ("kia", "ceed", 4, 28000, 1.0, [
        ("1.0 T-GDi DynamicLine", "benzine", 88, "handgeschakeld", None, 1.0),
        ("1.4 T-GDi GT-Line DCT", "benzine", 103, "automaat", None, 1.1),
        ("Sportswagon 1.6 GDI PHEV", "plugin_hybride", 104, "automaat", 8.9, 1.2, (2020, None)),
    ]),
    ("kia", "ev6", 2, 55000, 0.9, [
        ("Light 58 kWh", "elektrisch", 125, "automaat", 58.0, 0.85),
        ("GT-Line 77 kWh", "elektrisch", 168, "automaat", 77.4, 1.0),
        ("GT-Line AWD 77 kWh", "elektrisch", 239, "automaat", 77.4, 1.1),
    ]),
    ("toyota", "yaris", 8, 23000, 1.1, [
        ("1.0 VVT-i Comfort", "benzine", 53, "handgeschakeld", None, 0.85, (None, 2020)),
        ("1.5 Hybrid Active", "hybride", 85, "automaat", None, 1.0),
        ("1.5 Hybrid Dynamic", "hybride", 85, "automaat", None, 1.08),
    ]),
    ("toyota", "corolla", 6, 33000, 1.1, [
        ("1.8 Hybrid Dynamic", "hybride", 90, "automaat", None, 1.0),
        ("2.0 Hybrid GR-Sport", "hybride", 135, "automaat", None, 1.18, (2020, None)),
        ("Touring Sports 1.8 Hybrid Active", "hybride", 90, "automaat", None, 1.02),
    ]),
    ("toyota", "c-hr", 5, 35000, 1.08, [
        ("1.8 Hybrid Style", "hybride", 90, "automaat", None, 1.0),
        ("2.0 Hybrid Executive", "hybride", 135, "automaat", None, 1.15, (2020, None)),
    ]),
    ("toyota", "aygo", 5, 14000, 1.08, [
        ("1.0 VVT-i x-play", "benzine", 53, "handgeschakeld", None, 1.0),
        ("1.0 VVT-i x-joy", "benzine", 53, "handgeschakeld", None, 1.05),
    ]),
    ("toyota", "rav4", 3, 47000, 1.1, [
        ("2.5 Hybrid Dynamic", "hybride", 160, "automaat", None, 1.0, (2019, None)),
        ("2.5 Hybrid AWD Style", "hybride", 163, "automaat", None, 1.1, (2019, None)),
        ("2.5 Plug-in Hybrid AWD", "plugin_hybride", 225, "automaat", 18.1, 1.3, (2021, None)),
    ]),
    ("toyota", "prius", 3, 34000, 1.05, [
        ("1.8 Hybrid Business", "hybride", 90, "automaat", None, 1.0),
        ("1.8 Plug-in Hybrid Executive", "plugin_hybride", 90, "automaat", 8.8, 1.15, (2017, None)),
    ]),
    ("opel", "corsa", 7, 22500, 0.95, [
        ("1.2 Edition", "benzine", 55, "handgeschakeld", None, 0.9, (2020, None)),
        ("1.2 Turbo Elegance", "benzine", 74, "handgeschakeld", None, 1.05, (2020, None)),
        ("Corsa-e 50 kWh Elegance", "elektrisch", 100, "automaat", 50.0, 1.5, (2020, None)),
        ("1.4 Online Edition", "benzine", 66, "handgeschakeld", None, 0.95, (None, 2019)),
    ]),
    ("opel", "astra", 5, 28000, 0.93, [
        ("1.0 Turbo Online Edition", "benzine", 77, "handgeschakeld", None, 0.95, (None, 2021)),
        ("1.2 Turbo Edition", "benzine", 96, "handgeschakeld", None, 1.0, (2022, None)),
        ("Sports Tourer 1.6 CDTI Business", "diesel", 81, "handgeschakeld", None, 1.0, (None, 2021)),
    ]),
    ("renault", "clio", 7, 22000, 0.97, [
        ("0.9 TCe Limited", "benzine", 66, "handgeschakeld", None, 0.95, (None, 2019)),
        ("1.0 TCe Zen", "benzine", 67, "handgeschakeld", None, 1.0, (2020, None)),
        ("1.2 TCe Intens EDC", "benzine", 88, "automaat", None, 1.05, (2013, 2018)),
        ("1.6 E-Tech Hybrid Intens", "hybride", 103, "automaat", None, 1.2, (2020, None)),
    ]),
    ("renault", "captur", 5, 28000, 0.97, [
        ("0.9 TCe Intens", "benzine", 66, "handgeschakeld", None, 0.9, (None, 2019)),
        ("1.3 TCe Intens EDC", "benzine", 116, "automaat", None, 1.05, (2019, None)),
        ("1.6 E-Tech Plug-in Hybrid", "plugin_hybride", 116, "automaat", 9.8, 1.2, (2020, None)),
    ]),
    ("renault", "zoe", 4, 33000, 0.85, [
        ("Q210 Zen 22 kWh", "elektrisch", 65, "automaat", 22.0, 0.9, (2013, 2016)),
        ("R90 Intens 41 kWh", "elektrisch", 68, "automaat", 41.0, 1.0, (2017, 2019)),
        ("R110 Life 52 kWh", "elektrisch", 80, "automaat", 52.0, 1.05, (2020, 2024)),
        ("R135 Intens 52 kWh", "elektrisch", 100, "automaat", 52.0, 1.12, (2020, 2024)),
    ]),
    ("renault", "megane", 4, 29000, 0.93, [
        ("1.2 TCe Bose", "benzine", 97, "handgeschakeld", None, 1.0, (2016, 2018)),
        ("1.3 TCe Limited", "benzine", 103, "handgeschakeld", None, 1.0, (2019, None)),
        ("Estate 1.5 dCi Intens", "diesel", 81, "handgeschakeld", None, 1.05),
    ]),
    ("ford", "fiesta", 6, 21000, 0.93, [
        ("1.1 Trend", "benzine", 55, "handgeschakeld", None, 0.9, (2018, None)),
        ("1.0 EcoBoost Titanium", "benzine", 74, "handgeschakeld", None, 1.0),
        ("1.0 EcoBoost ST-Line", "benzine", 92, "handgeschakeld", None, 1.08),
        ("1.0 EcoBoost Titanium Powershift", "benzine", 74, "automaat", None, 1.05),
    ]),
    ("ford", "focus", 6, 29000, 0.92, [
        ("1.0 EcoBoost Titanium", "benzine", 92, "handgeschakeld", None, 1.0),
        ("1.5 EcoBoost ST-Line", "benzine", 110, "handgeschakeld", None, 1.1),
        ("Wagon 1.5 TDCi Trend Edition", "diesel", 88, "handgeschakeld", None, 1.0),
        ("1.0 EcoBoost Hybrid ST-Line", "hybride", 92, "handgeschakeld", None, 1.08, (2020, None)),
        ("1.6 Trend Powershift", "benzine", 92, "automaat", None, 0.95, (None, 2018)),
    ]),
    ("ford", "kuga", 4, 40000, 0.92, [
        ("1.5 EcoBoost ST-Line", "benzine", 110, "handgeschakeld", None, 0.95),
        ("2.5 PHEV Titanium", "plugin_hybride", 165, "automaat", 14.4, 1.15, (2020, None)),
        ("2.0 TDCi Titanium 4WD", "diesel", 132, "automaat", None, 1.05, (None, 2019)),
    ]),
    ("ford", "puma", 4, 30000, 0.96, [
        ("1.0 EcoBoost Hybrid ST-Line", "hybride", 92, "handgeschakeld", None, 1.0),
        ("1.0 EcoBoost Hybrid Titanium DCT", "hybride", 92, "automaat", None, 1.05),
    ]),
    ("hyundai", "i10", 5, 16000, 1.03, [
        ("1.0 Comfort", "benzine", 49, "handgeschakeld", None, 1.0),
        ("1.0 Premium", "benzine", 49, "handgeschakeld", None, 1.1),
    ]),
    ("hyundai", "i30", 4, 27000, 0.98, [
        ("1.0 T-GDi Comfort", "benzine", 88, "handgeschakeld", None, 1.0),
        ("1.4 T-GDi Premium DCT", "benzine", 103, "automaat", None, 1.12),
        ("Wagon 1.0 T-GDi i-Motion", "benzine", 88, "handgeschakeld", None, 1.02),
    ]),
    ("hyundai", "kona", 5, 34000, 0.98, [
        ("1.0 T-GDI Comfort", "benzine", 88, "handgeschakeld", None, 0.8),
        ("1.6 GDI HEV Fashion", "hybride", 104, "automaat", None, 0.95, (2019, None)),
        ("Electric 64 kWh Premium", "elektrisch", 150, "automaat", 64.0, 1.2, (2018, None)),
        ("Electric 39 kWh Comfort", "elektrisch", 100, "automaat", 39.2, 1.0, (2018, None)),
    ]),
    ("hyundai", "tucson", 4, 41000, 1.0, [
        ("1.6 T-GDI HEV Premium", "hybride", 169, "automaat", None, 1.0, (2021, None)),
        ("1.6 T-GDI PHEV N Line 4WD", "plugin_hybride", 195, "automaat", 13.8, 1.15, (2021, None)),
        ("1.6 GDi Comfort", "benzine", 97, "handgeschakeld", None, 0.8, (None, 2020)),
    ]),
    ("hyundai", "ioniq-5", 3, 52000, 0.9, [
        ("58 kWh Style", "elektrisch", 125, "automaat", 58.0, 0.9),
        ("77 kWh Lounge", "elektrisch", 168, "automaat", 77.4, 1.05),
        ("77 kWh Lounge AWD", "elektrisch", 239, "automaat", 77.4, 1.12),
    ]),
    ("hyundai", "ioniq", 3, 31000, 0.95, [
        ("1.6 GDi Hybrid Comfort", "hybride", 104, "automaat", None, 1.0),
        ("Electric 38 kWh Premium", "elektrisch", 100, "automaat", 38.3, 1.15, (2019, None)),
    ]),
    ("skoda", "octavia", 8, 33000, 1.0, [
        ("Combi 1.0 TSI Business Edition", "benzine", 85, "handgeschakeld", None, 0.95),
        ("Combi 1.5 TSI Style DSG", "benzine", 110, "automaat", None, 1.08),
        ("Combi 2.0 TDI Business Edition Plus", "diesel", 110, "handgeschakeld", None, 1.05),
        ("Combi 1.4 TSI iV Business Edition", "plugin_hybride", 150, "automaat", 13.0, 1.15, (2020, None)),
        ("1.2 TSI Ambition", "benzine", 77, "handgeschakeld", None, 0.9, (None, 2016)),
    ]),
    ("skoda", "fabia", 5, 21000, 1.0, [
        ("1.0 MPI Active", "benzine", 44, "handgeschakeld", None, 0.85, (None, 2021)),
        ("1.0 TSI Ambition", "benzine", 70, "handgeschakeld", None, 1.0),
        ("Combi 1.0 TSI Style", "benzine", 81, "handgeschakeld", None, 1.08),
    ]),
    ("skoda", "enyaq", 3, 52000, 0.93, [
        ("iV 60", "elektrisch", 132, "automaat", 62.0, 0.92),
        ("iV 80", "elektrisch", 150, "automaat", 82.0, 1.0),
        ("iV 80x Sportline", "elektrisch", 195, "automaat", 82.0, 1.1),
    ]),
    ("skoda", "kodiaq", 3, 45000, 1.0, [
        ("1.5 TSI Style DSG 7p", "benzine", 110, "automaat", None, 1.0),
        ("2.0 TDI Sportline 4x4", "diesel", 140, "automaat", None, 1.12),
    ]),
    ("bmw", "1-serie", 4, 36000, 0.95, [
        ("118i Executive", "benzine", 100, "automaat", None, 1.0),
        ("116d Business", "diesel", 85, "handgeschakeld", None, 0.95),
        ("120i M Sport", "benzine", 135, "automaat", None, 1.15),
    ]),
    ("bmw", "3-serie", 5, 50000, 0.94, [
        ("320i Executive", "benzine", 135, "automaat", None, 1.0),
        ("318d High Executive", "diesel", 110, "automaat", None, 0.95),
        ("330e M Sport", "plugin_hybride", 215, "automaat", 12.0, 1.12),
        ("Touring 320d xDrive", "diesel", 140, "automaat", None, 1.08),
    ]),
    ("bmw", "x1", 3, 45000, 0.95, [
        ("sDrive18i Executive", "benzine", 100, "automaat", None, 1.0),
        ("xDrive25e High Executive", "plugin_hybride", 162, "automaat", 10.0, 1.1, (2020, None)),
    ]),
    ("bmw", "i3", 2, 40000, 0.82, [
        ("94Ah", "elektrisch", 125, "automaat", 33.0, 1.0, (2016, 2018)),
        ("120Ah", "elektrisch", 125, "automaat", 42.2, 1.08, (2019, 2022)),
        ("REx 94Ah", "elektrisch", 125, "automaat", 33.0, 1.05, (2016, 2018)),
    ]),
    ("audi", "a3", 5, 38000, 0.97, [
        ("Sportback 30 TFSI Pro Line", "benzine", 81, "handgeschakeld", None, 0.95, (2018, None)),
        ("Sportback 35 TFSI S-Line S tronic", "benzine", 110, "automaat", None, 1.1),
        ("Sportback 1.4 TFSI e-tron", "plugin_hybride", 150, "automaat", 8.8, 1.05, (2015, 2020)),
    ]),
    ("audi", "q3", 3, 46000, 0.97, [
        ("35 TFSI S-Line", "benzine", 110, "automaat", None, 1.0),
        ("45 TFSI e S edition", "plugin_hybride", 180, "automaat", 13.0, 1.12, (2021, None)),
    ]),
    ("audi", "a4", 3, 48000, 0.94, [
        ("Avant 35 TFSI Advanced", "benzine", 110, "automaat", None, 1.0),
        ("Avant 2.0 TDI Sport", "diesel", 110, "automaat", None, 1.0),
    ]),
    ("mercedes-benz", "a-klasse", 4, 40000, 0.95, [
        ("A180 Business Solution", "benzine", 100, "automaat", None, 0.95),
        ("A200 AMG Line", "benzine", 120, "automaat", None, 1.05),
        ("A250e AMG Line", "plugin_hybride", 160, "automaat", 15.6, 1.15, (2020, None)),
    ]),
    ("mercedes-benz", "c-klasse", 4, 52000, 0.93, [
        ("C200 Business Solution", "benzine", 135, "automaat", None, 1.0),
        ("C300e AMG Line", "plugin_hybride", 230, "automaat", 13.5, 1.15, (2020, None)),
        ("Estate C220d Avantgarde", "diesel", 143, "automaat", None, 1.05),
    ]),
    ("mercedes-benz", "glc", 2, 65000, 0.95, [
        ("GLC 300e 4MATIC Business Solution AMG", "plugin_hybride", 235, "automaat", 13.5, 1.0),
        ("GLC 220d 4MATIC", "diesel", 143, "automaat", None, 0.95),
    ]),
    ("volvo", "xc40", 4, 46000, 0.98, [
        ("T3 Momentum", "benzine", 120, "handgeschakeld", None, 0.9),
        ("T5 Recharge R-Design", "plugin_hybride", 192, "automaat", 10.7, 1.08, (2020, None)),
        ("Recharge P8 AWD", "elektrisch", 300, "automaat", 78.0, 1.3, (2021, None)),
    ]),
    ("volvo", "xc60", 3, 62000, 0.98, [
        ("T8 Twin Engine Inscription", "plugin_hybride", 287, "automaat", 11.6, 1.08),
        ("B5 Momentum", "hybride", 184, "automaat", None, 0.95, (2020, None)),
        ("D4 Momentum", "diesel", 140, "automaat", None, 0.9, (None, 2020)),
    ]),
    ("volvo", "v60", 3, 52000, 0.96, [
        ("T6 Recharge AWD Inscription", "plugin_hybride", 250, "automaat", 11.6, 1.08, (2019, None)),
        ("B4 Momentum", "hybride", 145, "automaat", None, 0.95, (2020, None)),
    ]),
    ("citroen", "c3", 5, 21000, 0.93, [
        ("1.2 PureTech Feel", "benzine", 60, "handgeschakeld", None, 0.95),
        ("1.2 PureTech Shine", "benzine", 81, "handgeschakeld", None, 1.08),
    ]),
    ("citroen", "c1", 4, 13500, 1.0, [
        ("1.0 VTi Feel", "benzine", 53, "handgeschakeld", None, 1.0),
    ]),
    ("fiat", "500", 5, 17000, 1.02, [
        ("0.9 TwinAir Turbo Lounge", "benzine", 63, "handgeschakeld", None, 1.0),
        ("1.2 Pop", "benzine", 51, "handgeschakeld", None, 0.9),
        ("1.0 Hybrid Dolcevita", "hybride", 51, "handgeschakeld", None, 1.05, (2020, None)),
    ]),
    ("tesla", "model-3", 6, 52000, 0.9, [
        ("Standard Range Plus RWD", "elektrisch", 208, "automaat", 55.0, 0.9, (2019, 2023)),
        ("Long Range AWD", "elektrisch", 324, "automaat", 75.0, 1.05),
        ("Performance AWD", "elektrisch", 377, "automaat", 79.0, 1.15, (2019, None)),
    ]),
    ("tesla", "model-y", 4, 56000, 0.9, [
        ("RWD", "elektrisch", 220, "automaat", 60.0, 0.9, (2022, None)),
        ("Long Range AWD", "elektrisch", 378, "automaat", 75.0, 1.0),
        ("Performance AWD", "elektrisch", 393, "automaat", 75.0, 1.1),
    ]),
    ("tesla", "model-s", 2, 90000, 0.82, [
        ("75D", "elektrisch", 245, "automaat", 75.0, 0.9, (2016, 2019)),
        ("90D", "elektrisch", 310, "automaat", 90.0, 1.0, (2015, 2017)),
        ("Long Range", "elektrisch", 375, "automaat", 100.0, 1.1, (2019, None)),
    ]),
    ("seat", "ibiza", 5, 22000, 0.98, [
        ("1.0 TSI Style", "benzine", 70, "handgeschakeld", None, 1.0),
        ("1.0 TSI FR", "benzine", 85, "handgeschakeld", None, 1.08),
    ]),
    ("seat", "leon", 5, 30000, 0.97, [
        ("1.0 TSI Style", "benzine", 81, "handgeschakeld", None, 0.95),
        ("1.5 TSI FR", "benzine", 110, "handgeschakeld", None, 1.05),
        ("Sportstourer 1.4 TSI e-Hybrid FR", "plugin_hybride", 150, "automaat", 13.0, 1.2, (2020, None)),
    ]),
    ("nissan", "qashqai", 5, 33000, 0.95, [
        ("1.2 DIG-T Tekna", "benzine", 85, "handgeschakeld", None, 1.0, (None, 2018)),
        ("1.3 DIG-T N-Connecta", "benzine", 103, "handgeschakeld", None, 1.02, (2018, None)),
        ("1.5 dCi Acenta", "diesel", 81, "handgeschakeld", None, 0.95, (None, 2020)),
        ("1.3 MHEV Tekna Xtronic", "hybride", 116, "automaat", None, 1.15, (2021, None)),
    ]),
    ("nissan", "leaf", 4, 36000, 0.82, [
        ("Acenta 30 kWh", "elektrisch", 80, "automaat", 30.0, 0.9, (2016, 2017)),
        ("Acenta 40 kWh", "elektrisch", 110, "automaat", 40.0, 1.0, (2018, 2024)),
        ("e+ Tekna 62 kWh", "elektrisch", 160, "automaat", 62.0, 1.2, (2019, 2024)),
    ]),
    ("nissan", "micra", 3, 19000, 0.95, [
        ("0.9 IG-T N-Connecta", "benzine", 66, "handgeschakeld", None, 1.0),
    ]),
    ("mazda", "cx-5", 3, 40000, 1.03, [
        ("2.0 SkyActiv-G Skylease", "benzine", 121, "handgeschakeld", None, 1.0),
        ("2.2 SkyActiv-D GT-M AWD", "diesel", 129, "automaat", None, 1.1),
    ]),
    ("mazda", "3", 3, 31000, 1.02, [
        ("2.0 e-SkyActiv-G M Hybrid Comfort", "hybride", 90, "handgeschakeld", None, 1.0, (2019, None)),
        ("2.0 SkyActiv-G GT-M", "benzine", 88, "handgeschakeld", None, 0.95),
    ]),
    ("suzuki", "swift", 4, 19000, 1.05, [
        ("1.2 Select", "benzine", 66, "handgeschakeld", None, 1.0),
        ("1.2 Smart Hybrid Style", "hybride", 61, "handgeschakeld", None, 1.08, (2020, None)),
    ]),
    ("dacia", "sandero", 5, 15000, 1.02, [
        ("0.9 TCe Laureate", "benzine", 66, "handgeschakeld", None, 1.0),
        ("1.0 TCe Expression", "benzine", 67, "handgeschakeld", None, 1.05, (2021, None)),
        ("Stepway 1.0 TCe Bi-Fuel", "lpg", 74, "handgeschakeld", None, 1.1, (2021, None)),
    ]),
    ("dacia", "duster", 3, 22000, 1.02, [
        ("1.0 TCe Comfort", "benzine", 74, "handgeschakeld", None, 1.0, (2019, None)),
        ("1.3 TCe Prestige", "benzine", 110, "handgeschakeld", None, 1.12, (2019, None)),
    ]),
    ("mini", "mini", 3, 29000, 1.0, [
        ("Cooper 1.5 Chili", "benzine", 100, "handgeschakeld", None, 1.0),
        ("One 1.5 Business Edition", "benzine", 75, "handgeschakeld", None, 0.9),
        ("Cooper SE Yours 33 kWh", "elektrisch", 135, "automaat", 32.6, 1.25, (2020, None)),
    ]),
    ("mg", "mg4", 3, 36000, 0.85, [
        ("Standard 51 kWh", "elektrisch", 125, "automaat", 51.0, 0.9, (2022, None)),
        ("Comfort 64 kWh", "elektrisch", 150, "automaat", 64.0, 1.0),
        ("Luxury 64 kWh", "elektrisch", 150, "automaat", 64.0, 1.08),
    ]),
    ("mg", "zs", 2, 32000, 0.82, [
        ("EV Luxury 44 kWh", "elektrisch", 105, "automaat", 44.5, 1.0),
        ("EV Long Range Luxury 72 kWh", "elektrisch", 115, "automaat", 72.6, 1.15, (2022, None)),
    ]),
    ("mitsubishi", "outlander", 3, 45000, 0.9, [
        ("2.0 PHEV Instyle", "plugin_hybride", 149, "automaat", 12.0, 1.0, (2014, 2018)),
        ("2.4 PHEV Intense+", "plugin_hybride", 165, "automaat", 13.8, 1.05, (2019, None)),
    ]),
    ("mitsubishi", "space-star", 3, 15000, 1.0, [
        ("1.0 Cool+", "benzine", 52, "handgeschakeld", None, 1.0),
        ("1.2 Intense CVT", "benzine", 59, "automaat", None, 1.1),
    ]),
    ("honda", "jazz", 3, 26000, 1.08, [
        ("1.3 i-VTEC Elegance", "benzine", 75, "handgeschakeld", None, 0.85, (None, 2020)),
        ("1.5 e:HEV Executive", "hybride", 80, "automaat", None, 1.05, (2020, None)),
    ]),
    ("polestar", "2", 2, 55000, 0.85, [
        ("Long Range Single Motor 78 kWh", "elektrisch", 170, "automaat", 78.0, 1.0),
        ("Long Range Dual Motor 78 kWh", "elektrisch", 300, "automaat", 78.0, 1.1, (2020, None)),
    ]),
    ("lynk-co", "01", 2, 46000, 0.85, [
        ("1.5 PHEV", "plugin_hybride", 192, "automaat", 17.6, 1.0),
    ]),
    ("cupra", "born", 2, 43000, 0.9, [
        ("58 kWh", "elektrisch", 150, "automaat", 58.0, 1.0),
        ("e-Boost 77 kWh", "elektrisch", 170, "automaat", 77.0, 1.12),
    ]),
    ("cupra", "formentor", 2, 42000, 0.98, [
        ("1.5 TSI", "benzine", 110, "handgeschakeld", None, 0.9),
        ("1.4 e-Hybrid VZ", "plugin_hybride", 180, "automaat", 13.0, 1.12, (2021, None)),
    ]),
]

DEALER_NAMES = [
    "Autobedrijf Van Dijk", "Auto Centrum Midden", "Garage De Vries & Zn", "Autohuis Bakker",
    "Mulder Occasions", "AutoPlaza Noord", "Car Center Zuid", "Visser Auto's", "Autobedrijf Jansen",
    "Occasioncentrum West", "De Boer Mobiliteit", "Autoservice Smit", "Meijer Automotive",
    "Dekker Car Selection", "Autohandel Bos", "Groen Auto's", "Vos Autogroep", "Autobedrijf Peters",
]
PRIVATE_NAMES = ["Particulier", "J. de Jong", "M. van den Berg", "S. Hendriks", "K. Willems", "R. Hoekstra"]

# Postcode regions weighted roughly by population/car supply
PC2_WEIGHTS = {
    "10": 5, "11": 3, "12": 3, "13": 4, "15": 2, "16": 2, "18": 2, "20": 3, "21": 2, "23": 3, "25": 5,
    "26": 2, "27": 2, "28": 2, "30": 5, "31": 2, "33": 2, "34": 2, "35": 4, "37": 2, "38": 3, "39": 1,
    "41": 1, "43": 1, "46": 1, "47": 1, "48": 3, "50": 3, "52": 3, "53": 2, "54": 1, "56": 4, "57": 2,
    "59": 2, "60": 1, "61": 1, "62": 2, "64": 2, "65": 3, "67": 2, "68": 3, "70": 1, "73": 2, "74": 2,
    "75": 3, "76": 1, "78": 1, "79": 1, "80": 2, "82": 1, "89": 2, "92": 1, "94": 1, "97": 3,
}

COLOURS = ["zwart", "wit", "grijs", "zilver", "blauw", "rood", "groen", "bruin"]
COLOUR_WEIGHTS = [26, 18, 24, 10, 12, 6, 2, 2]

OPTION_POOL = [
    "trekhaak", "navigatie", "climate_control", "airco", "cruise_control", "adaptive_cruise",
    "stoelverwarming", "panoramadak", "leder", "camera", "parkeersensoren", "apple_carplay", "led",
    "keyless", "lichtmetalen_velgen",
]
