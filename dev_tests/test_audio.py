#!/usr/bin/env python3
"""
Audio recording diagnostic test for VeriMinutes.
Tests different recording methods and provides diagnostic information.
"""

import subprocess
import time
import os
from pathlib import Path
import sys

def test_ffmpeg_devices():
    """List all available audio devices."""
    print("=" * 60)
    print("AUDIO DEVICE DETECTION TEST")
    print("=" * 60)

    try:
        result = subprocess.run([
            "ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""
        ], capture_output=True, text=True)

        print("Available audio devices:")
        for line in result.stderr.split('\n'):
            if '[AVFoundation indev @' in line and 'audio devices' not in line.lower():
                print(f"  {line.strip()}")

        return True
    except Exception as e:
        print(f"❌ Error listing devices: {e}")
        return False

def test_recording(device_spec, duration=3):
    """Test recording with a specific device specification."""
    test_file = f"test_audio_{device_spec.replace(':', '_')}.wav"

    print(f"\n🎤 Testing recording with device: {device_spec}")
    print(f"   Recording for {duration} seconds...")

    try:
        # Start recording
        process = subprocess.Popen([
            "ffmpeg", "-f", "avfoundation", "-i", device_spec,
            "-t", str(duration),  # Record for N seconds
            "-ar", "16000", "-ac", "1", "-acodec", "pcm_s16le",
            "-y", test_file
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Wait for recording to complete
        stdout, stderr = process.communicate(timeout=duration+2)

        if process.returncode == 0:
            # Check file size
            file_size = Path(test_file).stat().st_size
            print(f"   ✅ Recording successful! File size: {file_size} bytes")

            # Analyze audio levels
            analyze_audio(test_file)

            # Clean up
            os.remove(test_file)
            return True
        else:
            print(f"   ❌ Recording failed: {stderr.decode()[:200]}")
            return False

    except subprocess.TimeoutExpired:
        process.kill()
        print(f"   ❌ Recording timed out")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def analyze_audio(audio_file):
    """Analyze audio levels in a file."""
    try:
        result = subprocess.run([
            "ffmpeg", "-i", audio_file, "-af", "volumedetect", "-f", "null", "-"
        ], capture_output=True, text=True, timeout=5)

        print("   Audio levels:")
        for line in result.stderr.split('\n'):
            if 'mean_volume' in line or 'max_volume' in line:
                print(f"     {line.strip()}")

                # Check if audio is silent
                if 'mean_volume' in line:
                    try:
                        volume = float(line.split(':')[1].strip().split()[0])
                        if volume < -60:
                            print("     ⚠️ Audio is very quiet or silent!")
                            print("     Check: Is your microphone muted?")
                        elif volume < -40:
                            print("     ⚠️ Audio is quite low - speak louder or closer to mic")
                        else:
                            print("     ✅ Audio level is good!")
                    except:
                        pass
    except Exception as e:
        print(f"   Could not analyze audio: {e}")

def test_whisper(audio_file):
    """Test Whisper transcription on a file."""
    print("\n🎯 Testing Whisper transcription...")

    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_file, language="en")

        text = result.get("text", "").strip()
        if text:
            print(f"   ✅ Transcription: {text[:100]}...")
        else:
            print("   ⚠️ No speech detected by Whisper")

    except ImportError:
        print("   ❌ Whisper not installed")
        print("   Run: pip3 install openai-whisper")
    except Exception as e:
        print(f"   ❌ Whisper error: {e}")

def main():
    print("\n" + "="*60)
    print("VERIMINUTES AUDIO DIAGNOSTIC TEST")
    print("="*60)

    # Test 1: Check ffmpeg
    print("\n1. Checking ffmpeg installation...")
    try:
        subprocess.run(["which", "ffmpeg"], check=True, capture_output=True)
        print("   ✅ ffmpeg is installed")
    except:
        print("   ❌ ffmpeg not found! Install with: brew install ffmpeg")
        sys.exit(1)

    # Test 2: List devices
    if not test_ffmpeg_devices():
        sys.exit(1)

    # Test 3: Test recording with different devices
    print("\n" + "="*60)
    print("RECORDING TESTS")
    print("="*60)
    print("PLEASE SPEAK CLEARLY during each test!")

    devices_to_test = [":0", ":1", ":MacBook Pro Microphone"]

    success = False
    for device in devices_to_test:
        if test_recording(device, duration=3):
            success = True
            print(f"   🎉 Device {device} works!")
            break

    if not success:
        print("\n❌ No working audio device found!")
        print("\nTroubleshooting steps:")
        print("1. Check System Settings > Privacy & Security > Microphone")
        print("2. Ensure Terminal/IDE has microphone permission")
        print("3. Check if microphone is muted")
        print("4. Try running: ffmpeg -f avfoundation -i \":0\" -t 5 test.wav")
    else:
        print("\n✅ Audio recording is working!")

    # Test 4: Create a longer test recording for Whisper
    print("\n" + "="*60)
    print("FULL TEST RECORDING")
    print("="*60)
    print("Recording 5 seconds - PLEASE SPEAK NOW...")

    test_file = "test_full.wav"
    subprocess.run([
        "ffmpeg", "-f", "avfoundation", "-i", ":0",
        "-t", "5", "-ar", "16000", "-ac", "1",
        "-acodec", "pcm_s16le", "-y", test_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if Path(test_file).exists():
        analyze_audio(test_file)
        test_whisper(test_file)
        os.remove(test_file)

    print("\n" + "="*60)
    print("DIAGNOSTIC TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()