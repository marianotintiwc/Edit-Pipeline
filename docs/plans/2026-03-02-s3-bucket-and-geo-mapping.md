# S3 Bucket Support & Multi-Geo Mapping – Plan

## 1. Requirement Restatement

- **S3 bucket support**: Allow per-job or per-campaign S3 bucket selection instead of relying solely on `S3_BUCKET` env var.
- **Multi-geo support**: Map ISO 3166-1 alpha-2 country codes (CL, AR, BR, MX, etc.) to MercadoLibre geo codes (MLC, MLA, MLB, MLM) so CSVs and external systems can use familiar country codes.

---

## 2. Current State

### S3 Bucket

| Location | Behavior |
|---------|----------|
| `handler.py` | `bucket = os.environ.get('S3_BUCKET', 'ugc-pipeline-outputs')` — no per-job override |
| Helper scripts | Hardcoded or env: `meli-ai.filmmaker`, `latam-ai.filmmaker` |
| RunPod | Single `S3_BUCKET` per endpoint; LATAM vs MELI require different endpoints or env changes |

### Geo

| Location | Behavior |
|----------|----------|
| `handler.py` | Accepts `MLA`, `MLB`, `MLC`, `MLM` only; validates `geo.upper() in ["MLA", "MLB", "MLC", "MLM"]` |
| `get_whisper_language(geo)` | MLB → `pt`, others → `es` |
| Helper scripts | Pass geo from CSV; some infer from filename (e.g. `-MLB-` → MLB) |
| No mapping | Country codes (CL, AR, BR) are not normalized to MercadoLibre geos |

---

## 3. Geo Mapping Table

| Country Code | MercadoLibre Geo | Country | Whisper Language |
|--------------|------------------|---------|------------------|
| CL | MLC | Chile | es |
| AR | MLA | Argentina | es |
| BR | MLB | Brazil | pt |
| MX | MLM | Mexico | es |
| CO | MCO | Colombia | es |
| PE | MPE | Peru | es |
| UY | MLU | Uruguay | es |
| EC | MEC | Ecuador | es |
| VE | MLV | Venezuela | es |

**Note**: Handler currently validates only MLA, MLB, MLC, MLM. MCO, MPE, MLU, MEC, MLV would require handler validation expansion if needed.

---

## 4. Proposed Design

### 4.1 Geo Mapping Module

**New file**: `src/geo_mapping.py` (or `config/geo_mapping.json` + loader)

```python
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

def normalize_geo(geo_or_country: str) -> str:
    """Convert country code (CL, AR) or already-valid geo (MLC, MLA) to MercadoLibre geo."""
    if not geo_or_country:
        return ""
    s = geo_or_country.strip().upper()
    if s.startswith("ML") and len(s) == 3:  # Already a Meli geo
        return s
    return COUNTRY_TO_MELI_GEO.get(s, s)  # Map or pass through
```

**Placement options**:
- A) Shared module under `src/` or project root
- B) Config JSON `config/geo_mapping.json` for easy extension
- C) Both: JSON as source of truth, Python loader for scripts and handler

### 4.2 Handler Changes (geo)

1. **Validation**: Accept both country codes and Meli geos; normalize before validation.
2. **Whisper**: Keep `get_whisper_language(geo)` — it already works with MLC, MLA, MLB, MLM.
3. **Validation list**: Extend `VALID_GEO` to include MCO, MPE, MLU, MEC, MLV if those geos are supported by the pipeline (or keep strict and fail fast for unsupported).

```python
# handler.py - in JobInput.__post_init__ or validate_payload
if self.geo:
    self.geo = normalize_geo(self.geo)
    if self.geo not in SUPPORTED_MELI_GEOS:
        raise ValueError(f"geo must be one of {SUPPORTED_MELI_GEOS}, got: {self.geo}")
```

### 4.3 S3 Bucket Support

**Option A – Per-job override (recommended)**

Add `output_bucket` to the job input schema:

```json
{
  "input": {
    "geo": "MLC",
    "output_folder": "LATAM/LATAM_Exports",
    "output_bucket": "latam-ai.filmmaker",
    "clips": [...]
  }
}
```

**Resolution order**: `input.output_bucket` → `S3_BUCKET` env → default `ugc-pipeline-outputs`

**Security**: Restrict allowed buckets via env (e.g. `ALLOWED_S3_BUCKETS=latam-ai.filmmaker,meli-ai.filmmaker`) to prevent arbitrary bucket writes. If not set, allow any (current behavior).

**Option B – Bucket-by-geo mapping**

Config: `{ "MLC": "latam-ai.filmmaker", "MLA": "meli-ai.filmmaker", ... }`

- Pro: Automatic bucket selection from geo
- Con: Less flexible; geo ≠ bucket (e.g. MLC could be LATAM or MELI Chile)

**Recommendation**: Option A (per-job `output_bucket`) with optional bucket allowlist.

### 4.4 Helper Scripts

| Script | Changes |
|--------|---------|
| `run_meli_from_latam_csv.py` | Use `normalize_geo(row["geo"])`; optionally pass `output_bucket` in payload |
| `run_meli_from_users_csv.py` | Use `normalize_geo()` for CSV geo column |
| `run_meli_from_mlb_csv.py` | Same |
| `run_meli_from_para_editar_csv.py` | `extract_geo_from_filename()` already returns Meli geo; add fallback `normalize_geo()` for CSV geo |
| Other `run_meli_from_*` | Import and use `normalize_geo()` where geo comes from CSV |

---

## 5. Files to Create/Modify

| File | Action |
|------|--------|
| `config/geo_mapping.json` | Create – country → Meli geo mapping (optional; can be code-only) |
| `src/geo_mapping.py` or `geo_mapping.py` | Create – `normalize_geo()`, constants |
| `handler.py` | Modify – add `output_bucket` to JobInput, VALID_INPUT_KEYS, validation; use `normalize_geo()` |
| `API_DOCUMENTATION.md` | Update – document `output_bucket`, geo mapping (CL→MLC, etc.) |
| `Helper Scripts/run_meli_from_latam_csv.py` | Use `normalize_geo()`; add `output_bucket` if desired |
| `Helper Scripts/run_meli_from_*_csv.py` | Use `normalize_geo()` where geo comes from CSV |

---

## 6. Implementation Order

1. **Phase 1 – Geo mapping (low risk)**
   - Add `geo_mapping.py` with `COUNTRY_TO_MELI_GEO` and `normalize_geo()`
   - Update handler to call `normalize_geo()` before validation
   - Update helper scripts to use `normalize_geo()` for CSV geo
   - No breaking change: existing payloads with MLC, MLA, etc. continue to work

2. **Phase 2 – S3 bucket override**
   - Add `output_bucket` to handler input schema
   - In upload step: `bucket = job_input.output_bucket or os.environ.get('S3_BUCKET', 'ugc-pipeline-outputs')`
   - Optional: add `ALLOWED_S3_BUCKETS` env for allowlist
   - Update API docs and LATAM script to pass `output_bucket: "latam-ai.filmmaker"`

---

## 7. Trade-offs

| Decision | Trade-off |
|----------|-----------|
| Geo in code vs JSON | Code: simpler, no file I/O. JSON: easier to extend without code change. |
| Per-job bucket vs geo→bucket | Per-job: explicit, flexible. Geo→bucket: implicit, can be wrong for cross-campaign use. |
| Bucket allowlist | Safer but requires config. No allowlist: matches current behavior. |
| Extend VALID_GEO to MCO, MPE, etc. | Only if pipeline/Whisper supports those geos; otherwise fail fast. |

---

## 8. Out of Scope (for this plan)

- RunPod multi-endpoint strategy (different endpoints per bucket)
- Per-geo style presets (e.g. different highlight colors by geo)
- Region-specific S3 endpoints (e.g. `us-east-2` vs `sa-east-1`)
