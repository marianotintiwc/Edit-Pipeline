#!/bin/bash
echo "=== UGC Pipeline Container Startup ==="
echo "Validating environment..."

# Check Vulkan
if command -v vulkaninfo &> /dev/null; then
    echo "✅ Vulkan: $(vulkaninfo --summary 2>&1 | grep -i gpu | head -1 || echo available)"
else
    echo "⚠️  Vulkan: vulkaninfo not found"
fi

# Check RIFE
if command -v rife-ncnn-vulkan &> /dev/null; then
    echo "✅ RIFE: $(which rife-ncnn-vulkan)"
else
    echo "❌ RIFE: not found in PATH"
fi

# Check FFmpeg
if command -v ffmpeg &> /dev/null; then
    echo "✅ FFmpeg: $(ffmpeg -version 2>&1 | head -1)"
else
    echo "❌ FFmpeg: not found"
fi

# Check ImageMagick
if command -v magick &> /dev/null || command -v convert &> /dev/null; then
    echo "✅ ImageMagick: available"
else
    echo "⚠️  ImageMagick: not found"
fi

# Check CUDA
python -c "import torch; print(f'✅ CUDA: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"not available\"}')" 2>/dev/null || echo "⚠️  PyTorch/CUDA check failed"

echo "=== Starting handler ==="
exec python -u handler.py
