#!/usr/bin/env python3
"""
Local Test Script for UGC Pipeline Handler.

This script tests the handler locally without RunPod infrastructure.
It simulates a RunPod job with sample input data.

Usage:
    # Test startup validation only
    python test_local.py --check-only
    
    # Test with sample URLs (requires network access)
    python test_local.py --test-job
    
    # Test with local files
    python test_local.py --local-videos /path/to/v1.mp4 /path/to/v2.mp4 /path/to/v3.mp4 /path/to/v4.mp4

Requirements:
    - All dependencies from requirements.txt installed
    - For full test: network access to download sample videos
    - For RIFE test: GPU with Vulkan support
"""

import os
import sys
import json
import argparse
import tempfile
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def test_startup_check():
    """Run environment validation."""
    print("=" * 60)
    print("  Testing Startup Validation")
    print("=" * 60)
    
    from startup_check import validate_environment, print_system_info
    
    print_system_info()
    
    try:
        results = validate_environment(require_rife=False, require_cuda=False)
        print("\n✅ Basic validation passed")
        return True
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        return False


def test_strict_validation():
    """Run strict environment validation (RIFE + CUDA required)."""
    print("\n" + "=" * 60)
    print("  Testing Strict Validation (RIFE + CUDA)")
    print("=" * 60)
    
    from startup_check import validate_environment
    
    try:
        results = validate_environment(require_rife=True, require_cuda=True)
        print("\n✅ Strict validation passed")
        return True
    except Exception as e:
        print(f"\n⚠️  Strict validation failed: {e}")
        print("    (This is expected if RIFE/CUDA is not available)")
        return False


def test_handler_import():
    """Test that handler module can be imported."""
    print("\n" + "=" * 60)
    print("  Testing Handler Import")
    print("=" * 60)
    
    try:
        from handler import handler, JobInput, EditPreset, SubtitleMode
        print("✅ Handler module imported successfully")
        print(f"   - JobInput: {JobInput}")
        print(f"   - EditPreset values: {[e.value for e in EditPreset]}")
        print(f"   - SubtitleMode values: {[m.value for m in SubtitleMode]}")
        return True
    except ImportError as e:
        print(f"❌ Handler import failed: {e}")
        return False


def test_job_input_validation():
    """Test JobInput validation."""
    print("\n" + "=" * 60)
    print("  Testing JobInput Validation")
    print("=" * 60)
    
    from handler import JobInput, EditPreset, SubtitleMode
    
    # Test valid input
    try:
        valid_input = JobInput(
            video_urls=[
                "https://example.com/v1.mp4",
                "https://example.com/v2.mp4",
                "https://example.com/v3.mp4",
                "https://example.com/v4.mp4"
            ],
            edit_preset="standard_vertical",
            music_url=None,
            music_volume=0.3,
            subtitle_mode="auto"
        )
        print("✅ Valid input accepted")
    except Exception as e:
        print(f"❌ Valid input rejected: {e}")
        return False
    
    # Test invalid: wrong number of videos
    try:
        invalid_input = JobInput(
            video_urls=["https://example.com/v1.mp4"],
            edit_preset="standard_vertical"
        )
        print("❌ Invalid input (1 video) was accepted")
        return False
    except ValueError as e:
        print(f"✅ Invalid input (1 video) correctly rejected: {e}")
    
    # Test invalid: bad music volume
    try:
        invalid_input = JobInput(
            video_urls=["https://a.mp4", "https://b.mp4", "https://c.mp4", "https://d.mp4"],
            music_volume=2.0  # Invalid: > 1.0
        )
        print("❌ Invalid input (volume > 1) was accepted")
        return False
    except ValueError as e:
        print(f"✅ Invalid input (volume > 1) correctly rejected")
    
    # Test invalid: manual subs without URL
    try:
        invalid_input = JobInput(
            video_urls=["https://a.mp4", "https://b.mp4", "https://c.mp4", "https://d.mp4"],
            subtitle_mode="manual",
            manual_srt_url=None
        )
        print("❌ Invalid input (manual subs, no URL) was accepted")
        return False
    except ValueError as e:
        print(f"✅ Invalid input (manual subs, no URL) correctly rejected")
    
    return True


def test_config_generation():
    """Test clips.json and style.json generation."""
    print("\n" + "=" * 60)
    print("  Testing Config Generation")
    print("=" * 60)
    
    from handler import (
        generate_clips_config, 
        generate_style_config, 
        JobInput,
        ProcessingContext
    )
    
    with tempfile.TemporaryDirectory() as work_dir:
        # Test clips config
        video_paths = [
            "/tmp/v1.mp4",
            "/tmp/v2.mp4", 
            "/tmp/v3.mp4",
            "/tmp/v4.mp4"
        ]
        
        clips_path = generate_clips_config(video_paths, work_dir)
        print(f"✅ clips.json generated: {clips_path}")
        
        with open(clips_path) as f:
            clips_data = json.load(f)
            print(f"   Clips: {len(clips_data['clips'])} entries")
        
        # Test style config
        job_input = JobInput(
            video_urls=["https://a.mp4", "https://b.mp4", "https://c.mp4", "https://d.mp4"],
            edit_preset="no_interpolation",  # Don't require RIFE
            enable_interpolation=False
        )
        
        ctx = ProcessingContext(job_id="test", work_dir=work_dir)
        style_path = generate_style_config(job_input, work_dir, ctx)
        print(f"✅ style.json generated: {style_path}")
        
        with open(style_path) as f:
            style_data = json.load(f)
            print(f"   Frame interpolation enabled: {style_data['postprocess']['frame_interpolation']['enabled']}")
        
    return True


def test_mock_job():
    """Test handler with a mock job (no actual video processing)."""
    print("\n" + "=" * 60)
    print("  Testing Mock Job (validation only)")
    print("=" * 60)
    
    from handler import handler
    
    # This will fail at the download step, but tests validation
    mock_job = {
        "id": "test-job-001",
        "input": {
            "video_urls": [
                "https://example.com/nonexistent1.mp4",
                "https://example.com/nonexistent2.mp4",
                "https://example.com/nonexistent3.mp4",
                "https://example.com/nonexistent4.mp4"
            ],
            "edit_preset": "no_interpolation",
            "subtitle_mode": "none",
            "enable_interpolation": False
        }
    }
    
    print(f"Running handler with mock job...")
    result = handler(mock_job)
    
    if "error" in result:
        # Expected: download will fail for nonexistent URLs
        if "download" in result.get("error", "").lower() or "Download" in result.get("error_type", ""):
            print(f"✅ Handler correctly failed at download step")
            print(f"   Error: {result['error'][:100]}...")
            return True
        else:
            print(f"⚠️  Handler failed with unexpected error: {result['error']}")
            return False
    else:
        print(f"❌ Handler unexpectedly succeeded with nonexistent URLs")
        return False


def run_all_tests():
    """Run all test suites."""
    results = {}
    
    results["startup_check"] = test_startup_check()
    results["strict_validation"] = test_strict_validation()
    results["handler_import"] = test_handler_import()
    results["job_input_validation"] = test_job_input_validation()
    results["config_generation"] = test_config_generation()
    results["mock_job"] = test_mock_job()
    
    print("\n" + "=" * 60)
    print("  Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    print("=" * 60)
    
    return all(results.values())


def main():
    parser = argparse.ArgumentParser(description="Test UGC Pipeline Handler locally")
    parser.add_argument("--check-only", action="store_true", help="Only run startup checks")
    parser.add_argument("--test-job", action="store_true", help="Test with sample job")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    
    args = parser.parse_args()
    
    if args.check_only:
        success = test_startup_check()
        test_strict_validation()
        sys.exit(0 if success else 1)
    elif args.test_job:
        success = test_mock_job()
        sys.exit(0 if success else 1)
    else:
        # Default: run all tests
        success = run_all_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
