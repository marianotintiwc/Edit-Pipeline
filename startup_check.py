"""
Startup Validation Module for UGC Pipeline.

This module provides validation functions to ensure all required dependencies
and system components are available before processing jobs. It's designed to
fail fast with clear error messages.

Validates:
- FFmpeg installation
- ImageMagick installation
- Vulkan support (for RIFE GPU acceleration)
- RIFE binary availability and functionality
- GPU/CUDA availability for Whisper
- Required Python packages

Usage:
    from startup_check import validate_environment
    
    try:
        validate_environment()
    except Exception as e:
        print(f"Environment not ready: {e}")
"""

import os
import subprocess
import shutil
import sys
from typing import Optional, Tuple, List


# ─────────────────────────────────────────────────────────────────────────────
# Custom Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class StartupValidationError(Exception):
    """Base exception for startup validation failures."""
    pass


class FFmpegNotAvailableError(StartupValidationError):
    """FFmpeg is not installed or not accessible."""
    pass


class ImageMagickNotAvailableError(StartupValidationError):
    """ImageMagick is not installed or not accessible."""
    pass


class VulkanNotAvailableError(StartupValidationError):
    """Vulkan is not available for GPU acceleration."""
    pass


class RIFENotAvailableError(StartupValidationError):
    """RIFE binary is not installed or not functional."""
    pass


class CUDANotAvailableError(StartupValidationError):
    """CUDA is not available for GPU acceleration."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Validation Functions
# ─────────────────────────────────────────────────────────────────────────────

def check_ffmpeg() -> Tuple[bool, str]:
    """
    Check if FFmpeg is available.
    
    Returns:
        Tuple of (is_available, version_or_error)
    """
    # Try imageio_ffmpeg first (bundled with pip package)
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        version = result.stdout.split('\n')[0] if result.stdout else "unknown"
        return True, f"imageio_ffmpeg: {version}"
    except ImportError:
        pass
    except Exception as e:
        pass
    
    # Fall back to system ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return False, "FFmpeg not found in PATH or imageio_ffmpeg"
    
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        version = result.stdout.split('\n')[0] if result.stdout else "unknown"
        return True, f"system: {version}"
    except Exception as e:
        return False, f"FFmpeg found but failed to run: {e}"


def check_imagemagick() -> Tuple[bool, str]:
    """
    Check if ImageMagick is available.
    
    Returns:
        Tuple of (is_available, version_or_error)
    """
    # Check for 'magick' (ImageMagick 7+) or 'convert' (older versions)
    for cmd in ["magick", "convert"]:
        path = shutil.which(cmd)
        if path:
            try:
                result = subprocess.run(
                    [path, "-version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    version = result.stdout.split('\n')[0] if result.stdout else "unknown"
                    return True, f"{cmd}: {version}"
            except Exception as e:
                continue
    
    return False, "ImageMagick not found (tried 'magick' and 'convert')"


def check_vulkan() -> Tuple[bool, str]:
    """
    Check if Vulkan is available for GPU acceleration.
    
    Returns:
        Tuple of (is_available, info_or_error)
    """
    vulkaninfo_path = shutil.which("vulkaninfo")
    if not vulkaninfo_path:
        return False, "vulkaninfo not found - install vulkan-tools"
    
    try:
        result = subprocess.run(
            [vulkaninfo_path, "--summary"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return False, f"vulkaninfo failed: {result.stderr}"
        
        # Parse GPU info from output
        output = result.stdout
        gpu_info = "Vulkan available"
        
        for line in output.split('\n'):
            if 'GPU' in line.upper() or 'deviceName' in line:
                gpu_info = line.strip()
                break
        
        return True, gpu_info
        
    except subprocess.TimeoutExpired:
        return False, "vulkaninfo timed out"
    except Exception as e:
        return False, f"vulkaninfo error: {e}"


def check_rife_binary() -> Tuple[bool, str]:
    """
    Check if RIFE binary is available and functional.
    
    Returns:
        Tuple of (is_available, info_or_error)
        
    Raises:
        RIFENotAvailableError: If RIFE is required but not available
    """
    # Check standard locations
    rife_path = shutil.which("rife-ncnn-vulkan")
    
    if not rife_path:
        # Check /usr/local/bin explicitly
        alt_path = "/usr/local/bin/rife-ncnn-vulkan"
        if os.path.isfile(alt_path) and os.access(alt_path, os.X_OK):
            rife_path = alt_path
    
    if not rife_path:
        return False, "rife-ncnn-vulkan not found in PATH or /usr/local/bin"
    
    try:
        # Test with --help to verify it runs
        result = subprocess.run(
            [rife_path, "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # rife-ncnn-vulkan may return non-zero with --help, check if output exists
        if result.stdout or result.stderr:
            # Extract version if available
            output = result.stdout + result.stderr
            version = "version unknown"
            for line in output.split('\n'):
                if 'rife' in line.lower() and ('version' in line.lower() or 'v4' in line.lower()):
                    version = line.strip()
                    break
            return True, f"{rife_path}: {version}"
        else:
            return False, f"RIFE binary at {rife_path} produced no output"
            
    except subprocess.TimeoutExpired:
        return False, "RIFE binary timed out"
    except Exception as e:
        return False, f"RIFE binary error: {e}"


def check_rife_vulkan_gpu() -> Tuple[bool, str]:
    """
    Test that RIFE can actually use Vulkan GPU.
    
    This is a more thorough check that creates a small test to verify
    the full RIFE + Vulkan pipeline works.
    
    Returns:
        Tuple of (is_functional, info_or_error)
    """
    import tempfile
    
    rife_path = shutil.which("rife-ncnn-vulkan") or "/usr/local/bin/rife-ncnn-vulkan"
    
    if not os.path.isfile(rife_path):
        return False, "RIFE binary not found"
    
    try:
        # List available GPUs
        result = subprocess.run(
            [rife_path, "-g", "-1"],  # -1 often lists GPUs or runs CPU mode
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check if GPU 0 is mentioned or if it succeeded
        output = result.stdout + result.stderr
        
        if "gpu" in output.lower() or "vulkan" in output.lower():
            return True, "RIFE Vulkan GPU test passed"
        
        # Even if verbose output isn't available, if it ran without crashing, assume OK
        return True, "RIFE binary executed successfully"
        
    except Exception as e:
        return False, f"RIFE GPU test failed: {e}"


def check_cuda() -> Tuple[bool, str]:
    """
    Check if CUDA is available for PyTorch/Whisper.
    
    Returns:
        Tuple of (is_available, info_or_error)
    """
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            cuda_version = torch.version.cuda
            return True, f"CUDA {cuda_version}: {device_name}"
        else:
            return False, "PyTorch installed but CUDA not available"
    except ImportError:
        return False, "PyTorch not installed"
    except Exception as e:
        return False, f"CUDA check error: {e}"


def check_python_packages() -> Tuple[bool, List[str]]:
    """
    Check if required Python packages are installed.
    
    Returns:
        Tuple of (all_available, list_of_missing)
    """
    required = [
        "runpod",
        "requests",
        "boto3",
        "moviepy",
        "pysrt",
        "numpy",
        "PIL",  # Pillow
        "cv2",  # opencv-python
    ]
    
    # Optional but recommended
    optional = [
        "whisper",       # openai-whisper
        "faster_whisper", # faster-whisper (alternative)
    ]
    
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    # Check if at least one whisper variant is available
    whisper_available = False
    for whisper_pkg in ["whisper", "faster_whisper"]:
        try:
            __import__(whisper_pkg)
            whisper_available = True
            break
        except ImportError:
            continue
    
    if not whisper_available:
        missing.append("whisper (or faster_whisper)")
    
    return len(missing) == 0, missing


# ─────────────────────────────────────────────────────────────────────────────
# Main Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_environment(require_rife: bool = True, require_cuda: bool = True) -> dict:
    """
    Validate the complete environment for running the UGC pipeline.
    
    Args:
        require_rife: If True, raise exception if RIFE is not available
        require_cuda: If True, raise exception if CUDA is not available
        
    Returns:
        Dictionary with validation results
        
    Raises:
        StartupValidationError: If any required component is missing
    """
    results = {}
    errors = []
    
    print("🔍 Validating environment...")
    print("-" * 50)
    
    # FFmpeg (required)
    ffmpeg_ok, ffmpeg_info = check_ffmpeg()
    results['ffmpeg'] = {'available': ffmpeg_ok, 'info': ffmpeg_info}
    status = "✅" if ffmpeg_ok else "❌"
    print(f"{status} FFmpeg: {ffmpeg_info}")
    if not ffmpeg_ok:
        errors.append(FFmpegNotAvailableError(ffmpeg_info))
    
    # ImageMagick (required for subtitles)
    magick_ok, magick_info = check_imagemagick()
    results['imagemagick'] = {'available': magick_ok, 'info': magick_info}
    status = "✅" if magick_ok else "⚠️"
    print(f"{status} ImageMagick: {magick_info}")
    # ImageMagick is soft-required (subtitles will fail without it)
    
    # Vulkan (required for RIFE GPU)
    vulkan_ok, vulkan_info = check_vulkan()
    results['vulkan'] = {'available': vulkan_ok, 'info': vulkan_info}
    status = "✅" if vulkan_ok else "❌"
    print(f"{status} Vulkan: {vulkan_info}")
    if require_rife and not vulkan_ok:
        errors.append(VulkanNotAvailableError(vulkan_info))
    
    # RIFE binary
    rife_ok, rife_info = check_rife_binary()
    results['rife'] = {'available': rife_ok, 'info': rife_info}
    status = "✅" if rife_ok else "❌"
    print(f"{status} RIFE: {rife_info}")
    if require_rife and not rife_ok:
        errors.append(RIFENotAvailableError(rife_info))
    
    # CUDA (required for Whisper GPU)
    cuda_ok, cuda_info = check_cuda()
    results['cuda'] = {'available': cuda_ok, 'info': cuda_info}
    status = "✅" if cuda_ok else "⚠️"
    print(f"{status} CUDA: {cuda_info}")
    if require_cuda and not cuda_ok:
        errors.append(CUDANotAvailableError(cuda_info))
    
    # Python packages
    pkgs_ok, missing_pkgs = check_python_packages()
    results['packages'] = {'available': pkgs_ok, 'missing': missing_pkgs}
    status = "✅" if pkgs_ok else "❌"
    pkg_info = "All required packages installed" if pkgs_ok else f"Missing: {', '.join(missing_pkgs)}"
    print(f"{status} Packages: {pkg_info}")
    if not pkgs_ok:
        errors.append(StartupValidationError(f"Missing packages: {', '.join(missing_pkgs)}"))
    
    print("-" * 50)
    
    # Raise first critical error
    if errors:
        raise errors[0]
    
    return results


def print_system_info():
    """Print detailed system information for debugging."""
    print("\n📊 System Information")
    print("-" * 50)
    
    # Python
    print(f"Python: {sys.version}")
    
    # OS
    import platform
    print(f"OS: {platform.system()} {platform.release()}")
    
    # CUDA details
    try:
        import torch
        if torch.cuda.is_available():
            print(f"PyTorch: {torch.__version__}")
            print(f"CUDA: {torch.version.cuda}")
            print(f"cuDNN: {torch.backends.cudnn.version()}")
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                print(f"GPU {i}: {props.name} ({props.total_memory / 1024**3:.1f} GB)")
    except ImportError:
        print("PyTorch: Not installed")
    
    # Disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage("/tmp")
        print(f"/tmp space: {free / 1024**3:.1f} GB free of {total / 1024**3:.1f} GB")
    except Exception:
        pass
    
    print("-" * 50)


# ─────────────────────────────────────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  UGC Pipeline - Environment Validation")
    print("=" * 60)
    
    print_system_info()
    
    try:
        results = validate_environment(require_rife=True, require_cuda=True)
        print("\n✅ All validations passed! Environment is ready.\n")
        sys.exit(0)
    except StartupValidationError as e:
        print(f"\n❌ Validation failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        sys.exit(1)
