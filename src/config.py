"""
Shared configuration for the Enterprise Field Service Analytics pipeline.

Everything that defines the fictional company (regions, service catalogue,
SLA policy, pricing) lives here so the generator, cleaner and model builder
all agree on the same business rules.
"""
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
QUARANTINE_DIR = ROOT / "data" / "quarantine"
DOCS_DIR = ROOT / "docs"
SQL_DIR = ROOT / "sql"
WAREHOUSE_DB = ROOT / "data" / "warehouse.db"

# --------------------------------------------------------------------------
# Reproducibility & time window
# --------------------------------------------------------------------------
SEED = 42
START_DATE = "2024-01-01"
SNAPSHOT_DATE = "2026-09-30 23:59:59"   # "as of" timestamp of the data extract
CALENDAR_END = "2026-12-31"
FISCAL_YEAR_START_MONTH = 4             # Fiscal year starts April 1 (common in Canada)
TARGET_REQUESTS = 75_000

# --------------------------------------------------------------------------
# Regions
# --------------------------------------------------------------------------
REGIONS = [
    # name,               province, manager,             share of demand, technicians
    ("Toronto",            "ON", "Priya Raman",          0.29, 26),
    ("Mississauga",        "ON", "Daniel Okafor",        0.18, 16),
    ("Ottawa",             "ON", "Sophie Tremblay",      0.17, 15),
    ("Hamilton",           "ON", "Marcus Bell",          0.13, 12),
    ("Kitchener-Waterloo", "ON", "Hannah Schultz",       0.12, 11),
    ("London",             "ON", "Owen Fraser",          0.11, 10),
]

# Messy spellings that the "source system" sometimes emits; the cleaner maps them back.
REGION_ALIASES = {
    "Toronto": ["toronto", "TORONTO", "Toronto ", "Tor.", "TO"],
    "Mississauga": ["mississauga", "Missisauga", "MISSISSAUGA", "Mississauga "],
    "Ottawa": ["ottawa", "OTTAWA", "Ottawa ", "Ott."],
    "Hamilton": ["hamilton", "HAMILTON", "Hamilton ", "Ham."],
    "Kitchener-Waterloo": ["Kitchener Waterloo", "K-W", "KW", "kitchener-waterloo", "Kitchener"],
    "London": ["london", "LONDON", "London ", "London ON"],
}

# --------------------------------------------------------------------------
# Service catalogue
# --------------------------------------------------------------------------
# category, service type, share of volume, base price ($), on-site work hours (mean), parts cost mean ($)
SERVICE_TYPES = [
    ("Repair",       "Standard Repair",        0.24, 420, 2.5, 180),
    ("Repair",       "Emergency Repair",       0.10, 780, 3.5, 260),
    ("Maintenance",  "Preventive Maintenance", 0.22, 310, 2.0,  60),
    ("Maintenance",  "Scheduled Maintenance",  0.12, 280, 1.8,  45),
    ("Inspection",   "Safety Inspection",      0.10, 220, 1.2,  10),
    ("Inspection",   "Compliance Inspection",  0.07, 260, 1.5,  10),
    ("Installation", "New Installation",       0.10, 1150, 5.5, 650),
    ("Installation", "Equipment Upgrade",      0.05, 890, 4.0, 480),
]

# --------------------------------------------------------------------------
# SLA policy (hours from creation to closure)
# --------------------------------------------------------------------------
PRIORITIES = [
    # priority, sla hours, price multiplier, sort order
    ("Critical", 8,   1.50, 1),
    ("High",     24,  1.20, 2),
    ("Medium",   72,  1.00, 3),
    ("Low",      120, 0.95, 4),
]

# --------------------------------------------------------------------------
# Customers & workforce
# --------------------------------------------------------------------------
SEGMENTS = {  # segment: (share of customers, price multiplier, request-volume weight)
    "Enterprise":     (0.12, 0.90, 6.0),
    "Government":     (0.08, 0.92, 4.0),
    "Mid-Market":     (0.35, 1.00, 1.8),
    "Small Business": (0.45, 1.05, 0.7),
}
INDUSTRIES = ["Manufacturing", "Healthcare", "Retail", "Education", "Hospitality",
              "Logistics", "Property Management", "Public Sector", "Food & Beverage",
              "Technology"]
N_CUSTOMERS = 1_400

SKILL_LEVELS = {  # level: (share, hourly wage $, repeat-visit probability)
    "Junior":       (0.30, 34, 0.13),
    "Intermediate": (0.35, 41, 0.075),
    "Senior":       (0.25, 49, 0.045),
    "Expert":       (0.10, 58, 0.03),
}
SPECIALIZATIONS = ["HVAC", "Electrical", "Mechanical", "Controls & Automation", "General"]
MONTHLY_CAPACITY_PER_TECH = 29  # requests a technician can comfortably absorb per month

PARTS_MARKUP = 1.35  # parts are re-billed at cost x markup
