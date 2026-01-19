# ─────────────────────────────────────────────────────────────────────────────
# UGC Pipeline - RunPod Serverless Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
# Base: RunPod PyTorch image with CUDA for Whisper & ML workloads
# Includes: RIFE (rife-ncnn-vulkan), Vulkan, FFmpeg, ImageMagick
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
    # FFmpeg for video processing
    ffmpeg \
    # ImageMagick for text rendering (subtitles)
    imagemagick \
    libmagickwand-dev \
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
# Fix ImageMagick Policy (allow PDF/text operations)
# ─────────────────────────────────────────────────────────────────────────────
RUN if [ -f /etc/ImageMagick-6/policy.xml ]; then \
        sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml; \
        sed -i 's/<policy domain="path" rights="none" pattern="@\*"/<policy domain="path" rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml; \
    fi

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

# ─────────────────────────────────────────────────────────────────────────────
# Pre-download Whisper Model (optional, speeds up first job)
# ─────────────────────────────────────────────────────────────────────────────
# Uncomment to pre-download model during build (adds ~1GB to image)
# RUN python -c "import whisper; whisper.load_model('small')"

# ─────────────────────────────────────────────────────────────────────────────
# Startup Validation Script
# ─────────────────────────────────────────────────────────────────────────────
# Create a script that validates environment at container start
RUN echo '#!/bin/bash\n\
echo "=== UGC Pipeline Container Startup ==="\n\
echo "Validating environment..."\n\
\n\
# Check Vulkan\n\
if command -v vulkaninfo &> /dev/null; then\n\
    echo "✅ Vulkan: $(vulkaninfo --summary 2>&1 | grep -i gpu | head -1 || echo available)"\n\
else\n\
    echo "⚠️  Vulkan: vulkaninfo not found"\n\
fi\n\
\n\
# Check RIFE\n\
if command -v rife-ncnn-vulkan &> /dev/null; then\n\
    echo "✅ RIFE: $(which rife-ncnn-vulkan)"\n\
else\n\
    echo "❌ RIFE: not found in PATH"\n\
fi\n\
\n\
# Check FFmpeg\n\
if command -v ffmpeg &> /dev/null; then\n\
    echo "✅ FFmpeg: $(ffmpeg -version 2>&1 | head -1)"\n\
else\n\
    echo "❌ FFmpeg: not found"\n\
fi\n\
\n\
# Check ImageMagick\n\
if command -v magick &> /dev/null || command -v convert &> /dev/null; then\n\
    echo "✅ ImageMagick: available"\n\
else\n\
    echo "⚠️  ImageMagick: not found"\n\
fi\n\
\n\
# Check CUDA\n\
python -c "import torch; print(f\"✅ CUDA: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"not available\"}\")" 2>/dev/null || echo "⚠️  PyTorch/CUDA check failed"\n\
\n\
echo "=== Starting handler ==="\n\
exec python -u handler.py\n\
' > /app/start.sh && chmod +x /app/start.sh

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
