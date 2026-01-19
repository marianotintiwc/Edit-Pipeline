# UGC Video Pipeline

A local Python CLI tool to automate basic UGC video editing (9:16 format).

## Features
- Concatenate video clips.
- Add background music with loop and volume control.
- Generate "CapCut-style" animated subtitles from .srt files.
- Export to vertical MP4 (1080x1920).

## Requirements
- Python 3.10+
- FFmpeg (must be installed and in PATH)
- ImageMagick (required for moviepy TextClip)

## Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    py -m pip install -r requirements.txt
    ```

## Modo Fácil (Principiantes)

1.  **Preparar archivos:**
    *   **Videos:**
        *   Opción A (Recomendada): Pon tus videos en la carpeta `assets/video`. Nómbralos con números para ordenarlos (ej: `1.mp4`, `2.mp4`, `10.mp4`).
        *   Opción B: Usa el archivo `config/clips.json` para un control manual.
    *   Pon tu música en `assets/audio/music.mp3`.
    *   **Subtítulos:**
        *   Opción A: Pon tus subtítulos en `assets/subs/subtitles.srt`.
        *   Opción B: **¡No hagas nada!** Si no pones el archivo, el programa escuchará el video y creará los subtítulos automáticamente (necesita internet la primera vez).
    *   (Opcional) Ajusta el estilo en `config/style.json`.

2.  **Ejecutar:**
    *   Haz doble clic en el archivo `run.bat`.
    *   ¡Listo! Tu video aparecerá en la carpeta `exports`.

## Modo Avanzado (CLI)

Si prefieres usar la línea de comandos para especificar archivos distintos:

```bash
py ugc_pipeline.py --clips_config ./config/clips.json --music ./assets/audio/music.mp3 --subtitles ./assets/subs/subtitles.srt --output ./exports/video_final.mp4 --style ./config/style.json
```

### Configuration

See `config/clips.sample.json` and `config/style.sample.json` for configuration examples.
