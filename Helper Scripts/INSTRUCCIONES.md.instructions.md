# UGC Pipeline - Instrucciones de Desarrollo

## Modo Recomendado: StreamingWorker

El modo **streaming** es el recomendado para producción completa:

```bash
# Pipeline completo (hasta lipsync)
python Scripts/StreamingWorker.py "INPUT.csv"

# Solo imágenes (sin video/lipsync)
python Scripts/StreamingWorker.py "INPUT.csv" --images-only

# Retomar procesamiento de registros incompletos
python Scripts/StreamingWorker.py "INPUT.csv" --resume --images-only
```

### Flags del StreamingWorker

| Flag | Efecto |
|------|--------|
| `--resume` | Salta registros con production_assets.json existente |
| `--images-only` | Para después de Scene 3 (sin video/lipsync) |
| `--skip-scene1` | No espera por Scene 1 |
| `--workers N` | Hilos concurrentes (default: 10) |
| `--runcomfy-concurrency N` | Llamadas paralelas a RunComfy (default: 5) |

### Pipeline de 18 Etapas (Fail-Fast)

1. Creative → 2. Creative Parse → 3. Creative Validate → 4. Visual → 5. Visual Parse → 6. Visual Validate → 7. Scene1 Submit → 8. Scene1 Poll → 9. Scene1 Download → 10. Background Remove → 11. Scene2 Submit → 12. Scene2 Poll → 13. Scene2 Download → 14. Scene3 Submit → 15. Scene3 Poll → 16. Scene3 Download → 17. Video → 18. Lipsync

## Reglas de Cohesión Creativa/Visual

### 1. Voice ID Determinístico
- Voz asignada en Python por `get_voice_id()`, NO por LLM
- Mismo voice_id en las 3 escenas de cada registro
- Pool de voces por GEO: `es_rioplatense` (ARG), `es_neutro` (MEX), `pt_br` (BRA)

### 2. Consistencia de Personaje
- Scene 1 usa Text-to-Image (T2I)
- Scenes 2-3 usan Image-to-Image (I2I) con Scene 1 como anchor
- `--use-nobg` mejora consistencia (sin fondo)

### 3. Variación de Fondo/Pose
- MISMA persona, DIFERENTE ángulo de cámara
- Pose natural progresiva (hook → testimonio → CTA)
 - Movimientos de cámara dinámicos pero suaves (handheld sutil, slow push-in, gentle handheld sway), siempre centrados en el personaje; evitar paneos laterales y composiciones donde el dispositivo sea el protagonista.

## Reglas de Producto por Tipo

### 1. TARJETA / Cartão (Productos de Tarjeta)
**Detección:** `"tarjeta"`, `"cartao"`, `"cartão"` en columna PRODUCTO

| Escena | Tarjeta Visible | Imagen de Referencia |
|--------|-----------------|---------------------|
| **1 (Hook)** | ❌ NO | `None` |
| **2 (Testimonio)** | ✅ SÍ | `MERCADOPAGO_CARD_REF_URL` |
| **3 (CTA)** | ❌ NO | `None` |

### 2. TAP / Cobro TAP (Phone-as-Terminal)
- Sin dispositivo físico (el teléfono es la terminal)
- Pantalla del teléfono NUNCA visible
- Escena de pago con tarjeta usa `MERCADOPAGO_CARD_REF_URL`
 - Las reglas detalladas de TAP (escena de pago, método de pago, etc.) están centralizadas en `System Prompts/ugc-tap-rules.md` y solo se inyectan cuando el producto es TAP.

### 3. Non-TARJETA / Default (Lifestyle)
- SIN tarjeta en NINGUNA escena
- Solo contexto lifestyle/testimonial

### 4. Smart 2 / Point Smart (POS físico)
- El dispositivo es un prop estático que aparece en TODAS las escenas, sin mostrar el momento exacto de pago.
- Si hay imagen de referencia de pantalla, todas las escenas deben reutilizar exactamente la misma UI (colores/layout/textos) sin animaciones de "pago aprobado".
- La sensación de cobro exitoso viene de la reacción del comerciante, no de cambios en la pantalla.
- **La escena 1 SIEMPRE debe mostrar el dispositivo Smart 2 / Point Smart visible en cuadro**; el pipeline valida y corrige prompts para que esto se cumpla.

## Constantes Importantes

```python
MERCADOPAGO_CARD_REF_URL = "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/TC+MLB+-+front+perspective.png"
TAP_PRODUCT_KEYWORDS = ["tap", "tap to phone", "cobro tap"]
TARJETA_PRODUCT_KEYWORDS = ["tarjeta", "cartao", "cartão"]
```

## Zonas Seguras y Márgenes (Subtítulos)

Los subtítulos se mantienen dentro de zonas seguras por defecto, independientemente del perfil.

### TikTok (9:16 vertical)
Referencia: `margenesdeseguridad_tiktok_new` (540×960). top=126, bottom=54, left=60, right=120, zone_height=780.

### UAC 16:9 (horizontal)
Referencia: `Margenes UAC_16x9.png` (4000×2250). La zona prohibida está en rojo; la zona segura en blanco. Márgenes calculados con maximal rectangle.

| Borde | 4000×2250 | 1920×1080 | 1280×720 |
|-------|-----------|-----------|----------|
| top | 83 | 40 | 27 |
| bottom | 1050 | 504 | 336 |
| left | 218 | 105 | 70 |
| right | 1074 | 516 | 344 |

Config para 1920×1080:
```json
"uac_16x9_margins": {
  "ref_width": 1920,
  "ref_height": 1080,
  "top": 40,
  "bottom": 504,
  "left": 105,
  "right": 516
}
```

### Subtítulos: Cajita Aesthetic y Frases Cortas

Cuando `highlight.enabled` es true (estilo MELI/LATAM), los subtítulos usan una **cajita por frase** (content-sized) en lugar de una barra de ancho completo:

- **Background:** La caja amarilla (o `bg_color`) envuelve solo la frase, centrada en la zona segura.
- **Wrap:** `highlight.max_chars_per_line` (default: 30) define el máximo de caracteres por línea.
- **Frases más cortas:** Con `word_level: false`, `transcription.max_chars_per_phrase` (ej. 45) divide segmentos largos de Whisper en trozos por límite de caracteres (corte en espacios, tiempo repartido proporcionalmente).

Ejemplo en presets:
```json
"highlight": {
  "enabled": true,
  "bg_color": "#FFE600",
  "max_chars_per_line": 30
},
"transcription": {
  "word_level": false,
  "max_chars_per_phrase": 45
}
```

## Troubleshooting

### Imágenes Scene 2 Faltantes (Timeout API)
```bash
python Scripts/StreamingWorker.py "INPUT.csv" --resume --images-only
```

### Error 403 (Rate Limit)
- Esperar 5-10 minutos
- Reducir `--runcomfy-concurrency`
- Usar `--resume` para saltar completados

### B-roll Alpha Invertido (TAP/MLB - Feb 2026)
**Síntoma:** El b-roll de TAP aparece con el canal alpha invertido (la pantalla del teléfono opaca, la mano transparente).

**Causa:** `auto_invert_alpha` detecta incorrectamente que el alpha necesita inversión.

**Solución:** Agregar explícitamente en `style_overrides`:
```json
"broll_alpha_fill": {
  "enabled": true,
  "invert_alpha": false,
  "auto_invert_alpha": false
}
```

**Verificación:** El script `Helper Scripts/run_sellers_from_scenes_csv.py` ya incluye este fix.

### Audio de Escena 3 corta abrupto (Endcard Overlap)
**Causa:** `end_time: -1` recorta 1 segundo completo del clip o falta `endcard.audio_fade_seconds`.

**Solución recomendada:**
- No usar `end_time: -1` salvo que quieras recortar 1s completo.
- Usar `endcard.overlap_seconds: 0.5` y `endcard.audio_fade_seconds: 0.1` para un fade suave durante el overlap.