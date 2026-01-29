# ─────────────────────────────────────────────────────────────────────────────
# UGC Pipeline - RunPod Serverless Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
# Base: RunPod PyTorch image with CUDA for Whisper & ML workloads
# Includes: RIFE (rife-ncnn-vulkan), Vulkan, FFmpeg, ImageMagick
# ─────────────────────────────────────────────────────────────────────────────
# NOTE: RunPod only provides -devel images for CUDA 12.4.1.
#       There is no -runtime variant available. Keeping -devel.
#       Future optimization: consider pytorch/pytorch base + manual CUDA setup.
# ─────────────────────────────────────────────────────────────────────────────

FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# ─────────────────────────────────────────────────────────────────────────────
# Environment Variables
# ─────────────────────────────────────────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV WHISPER_DEVICE=cuda

# RIFE model path (models are downloaded at build time)
ENV RIFE_MODEL_PATH=/opt/rife-models

# Ensure /usr/local/bin is in PATH (for rife-ncnn-vulkan)
ENV PATH="/usr/local/bin:${PATH}"

# ─────────────────────────────────────────────────────────────────────────────
# System Dependencies
# ─────────────────────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Vulkan for RIFE GPU acceleration
    libvulkan1 \
    libvulkan-dev \
    vulkan-tools \
    mesa-vulkan-drivers \
    # FFmpeg for video processing (replaced with NVENC-capable static build later)
    ffmpeg \
    # ImageMagick for text rendering (subtitles)
    imagemagick \
    libmagickwand-dev \
    # Fonts for subtitles (Impact, Arial, etc.)
    fontconfig \
    fonts-liberation \
    fonts-dejavu-core \
    # General utilities
    wget \
    curl \
    unzip \
    git \
    # OpenCV dependencies
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    # Audio processing
    libsndfile1 \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ─────────────────────────────────────────────────────────────────────────────
# Install Microsoft Core Fonts (Impact, Arial, etc.) via manual download
# ─────────────────────────────────────────────────────────────────────────────
RUN mkdir -p /tmp/fonts && cd /tmp/fonts \
    # Download core fonts from SourceForge
    && wget -q -O impact.exe "https://deac-fra.dl.sourceforge.net/project/corefonts/the%20fonts/final/impact32.exe" \
    && wget -q -O arial.exe "https://deac-fra.dl.sourceforge.net/project/corefonts/the%20fonts/final/arial32.exe" \
    # Install cabextract to extract fonts
    && apt-get update && apt-get install -y --no-install-recommends cabextract \
    # Extract and install fonts
    && cabextract impact.exe && cabextract arial.exe \
    && mkdir -p /usr/share/fonts/truetype/msttcorefonts \
    && mv *.ttf /usr/share/fonts/truetype/msttcorefonts/ 2>/dev/null || mv *.TTF /usr/share/fonts/truetype/msttcorefonts/ 2>/dev/null || true \
    # Clean up
    && cd / && rm -rf /tmp/fonts \
    && rm -rf /var/lib/apt/lists/* \
    # Rebuild font cache
    && fc-cache -f -v

# ─────────────────────────────────────────────────────────────────────────────
# Install Meli Custom Font (MELIPROXIMANOVAA-BOLD)
# ─────────────────────────────────────────────────────────────────────────────
# Create custom fonts directory for Meli font
RUN mkdir -p /usr/share/fonts/truetype/meli

# Font will be copied via COPY . . later, so create symlink path
# The actual font is in assets/fonts/MELIPROXIMANOVAA-BOLD.OTF
# After COPY, we'll create symlinks

# ─────────────────────────────────────────────────────────────────────────────
# Fix ImageMagick Policy + Create 'magick' symlink (IM6 uses 'convert', not 'magick')
# ─────────────────────────────────────────────────────────────────────────────
RUN if [ -f /etc/ImageMagick-6/policy.xml ]; then \
        sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml; \
        sed -i 's/<policy domain="path" rights="none" pattern="@\*"/<policy domain="path" rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml; \
    fi \
    # Create 'magick' symlink for IM6 compatibility (MoviePy looks for 'magick')
    && if [ -f /usr/bin/convert ] && [ ! -f /usr/bin/magick ]; then \
        ln -s /usr/bin/convert /usr/bin/magick; \
    fi \
    # Verify ImageMagick is working
    && (magick -version || convert -version || echo "ImageMagick check failed")

# ─────────────────────────────────────────────────────────────────────────────
# Install RIFE (rife-ncnn-vulkan) - Pinned to release 20221029
# ─────────────────────────────────────────────────────────────────────────────
# Using the Ubuntu build from nihui/rife-ncnn-vulkan releases
ARG RIFE_VERSION=20221029
ARG RIFE_URL=https://github.com/nihui/rife-ncnn-vulkan/releases/download/${RIFE_VERSION}/rife-ncnn-vulkan-${RIFE_VERSION}-ubuntu.zip

RUN mkdir -p /tmp/rife && cd /tmp/rife \
    && wget -q "${RIFE_URL}" -O rife.zip \
    && unzip -q rife.zip \
    && mv rife-ncnn-vulkan-${RIFE_VERSION}-ubuntu/rife-ncnn-vulkan /usr/local/bin/ \
    && chmod +x /usr/local/bin/rife-ncnn-vulkan \
    # Copy RIFE models to opt
    && mkdir -p ${RIFE_MODEL_PATH} \
    && cp -r rife-ncnn-vulkan-${RIFE_VERSION}-ubuntu/rife* ${RIFE_MODEL_PATH}/ 2>/dev/null || true \
    # Cleanup
    && rm -rf /tmp/rife \
    # Verify installation
    && rife-ncnn-vulkan --help || echo "RIFE installed (help may show usage)"

# ─────────────────────────────────────────────────────────────────────────────
# Working Directory
# ─────────────────────────────────────────────────────────────────────────────
WORKDIR /app

# ─────────────────────────────────────────────────────────────────────────────
# Python Dependencies
# ─────────────────────────────────────────────────────────────────────────────
# Copy requirements first for layer caching
COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    # Install faster-whisper for better performance (alternative to openai-whisper)
    && pip install faster-whisper \
    # Cleanup pip cache
    && rm -rf ~/.cache/pip

# ─────────────────────────────────────────────────────────────────────────────
# Application Code
# ─────────────────────────────────────────────────────────────────────────────
# Copy all application files
COPY . .

# Ensure ugc_pipeline package is importable (fix hyphen issue)
RUN if [ -d "ugc-pipeline" ] && [ ! -d "ugc_pipeline" ]; then \
        ln -s ugc-pipeline ugc_pipeline; \
    fi

# Install Meli custom font to system fonts
RUN if [ -f "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF" ]; then \
        cp /app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF /usr/share/fonts/truetype/meli/; \
        fc-cache -f -v; \
        echo "Meli font installed successfully"; \
    else \
        echo "WARNING: Meli font not found at /app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF"; \
    fi

# ─────────────────────────────────────────────────────────────────────────────
# Pre-download Whisper Model (speeds up first job)
# ─────────────────────────────────────────────────────────────────────────────
# Pre-download "large" model to match style.json transcription config (~2.9GB)
RUN python -c "import whisper; print('Downloading Whisper large model...'); whisper.load_model('large'); print('Whisper model cached successfully')"

# ─────────────────────────────────────────────────────────────────────────────
# Startup Validation Script
# ─────────────────────────────────────────────────────────────────────────────
# Copy and set up startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh && \
    # Convert Windows line endings to Unix (just in case)
    sed -i 's/\r$//' /app/start.sh

# ─────────────────────────────────────────────────────────────────────────────
# Health Check (optional)
# ─────────────────────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import torch; assert torch.cuda.is_available()" || exit 1

# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────
# Use the startup script that validates then runs handler
CMD ["/app/start.sh"]

# Alternative: Run handler directly (skip startup checks)
# CMD ["python", "-u", "handler.py"]
