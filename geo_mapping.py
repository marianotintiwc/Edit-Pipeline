"""
Country code to MercadoLibre geo mapping.

Maps ISO 3166-1 alpha-2 country codes (CL, AR, BR, etc.) to MercadoLibre geo codes
(MLC, MLA, MLB, etc.) so CSVs and external systems can use familiar country codes.
"""

# Country code (ISO 3166-1 alpha-2) → MercadoLibre geo
COUNTRY_TO_MELI_GEO = {
    "AR": "MLA",  # Argentina
    "BR": "MLB",  # Brazil
    "CL": "MLC",  # Chile
    "MX": "MLM",  # Mexico
    "CO": "MCO",  # Colombia
    "PE": "MPE",  # Peru
    "UY": "MLU",  # Uruguay
    "EC": "MEC",  # Ecuador
    "VE": "MLV",  # Venezuela
}

# Reverse: MercadoLibre geo → country code (for display/logging)
MELI_GEO_TO_COUNTRY = {v: k for k, v in COUNTRY_TO_MELI_GEO.items()}

# Geos supported by the pipeline (Whisper language, validation)
SUPPORTED_MELI_GEOS = frozenset({"MLA", "MLB", "MLC", "MLM", "MCO", "MPE", "MLU", "MEC", "MLV"})


def normalize_geo(geo_or_country: str) -> str:
    """
    Convert country code (CL, AR) or already-valid geo (MLC, MLA) to MercadoLibre geo.

    Args:
        geo_or_country: Country code (e.g. CL, AR, BR) or Meli geo (e.g. MLC, MLA)

    Returns:
        MercadoLibre geo code (e.g. MLC, MLA). Pass-through if already valid Meli geo.
        Empty string if input is empty/None.
    """
    if not geo_or_country:
        return ""
    s = str(geo_or_country).strip().upper()
    if len(s) == 3 and s[0] == "M" and s in SUPPORTED_MELI_GEOS:
        # Already a Meli geo (MLA, MLB, MLC, MLM, MCO, MPE, MLU, MEC, MLV)
        return s
    return COUNTRY_TO_MELI_GEO.get(s, s)
