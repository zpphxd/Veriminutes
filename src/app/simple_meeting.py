"""
Simplified meeting recorder that works with system audio.
Uses system commands for recording and basic transcription.
"""

import subprocess
import threading
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import tempfile
import os

from .service import VeriMinutesService


class SimpleMeetingRecorder:
    """
    Simple meeting recorder using system audio recording.
    Works without complex audio dependencies.
    """

    def __init__(self):
        self.is_recording = False
        self.recording_process = None
        self.audio_file = None
        self.start_time = None
        self.meeting_title = "Meeting"
        self.attendees = []
        self.verifier = VeriMinutesService()
        self.use_demo = False

    def start_recording(self, meeting_title: str, attendees: List[str], use_real_audio: bool = True) -> Dict:
        """Start recording audio using system commands."""

        if self.is_recording:
            return {"error": "Already recording"}

        # Create temp file for audio
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.audio_file = f"output/recordings/meeting_{timestamp}.wav"  # Use WAV for better compatibility
        Path(self.audio_file).parent.mkdir(parents=True, exist_ok=True)

        # If explicitly demo mode or real audio disabled, use demo
        if not use_real_audio:
            print("📝 Using demo mode as requested")
            self.is_recording = True
            self.start_time = time.time()
            self.meeting_title = meeting_title
            self.attendees = attendees
            self.use_demo = True

            return {
                "status": "recording",
                "mode": "demo",
                "message": "Demo recording started - call /meeting/stop to complete",
                "start_time": datetime.now().isoformat()
            }

        # Use ffmpeg for audio recording (works on macOS)
        try:
            # Check if ffmpeg is available
            subprocess.run(["which", "ffmpeg"], check=True, capture_output=True)

            # List available audio devices first
            list_devices = subprocess.run([
                "ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""
            ], capture_output=True, text=True)

            print("📱 Available audio devices:")
            audio_devices = []
            for line in list_devices.stderr.split('\n'):
                if '[AVFoundation indev @' in line and 'audio devices' not in line.lower():
                    # Extract device index and name
                    if '[' in line:
                        device_info = line.split(']', 1)[1].strip() if ']' in line else line
                        print(f"  {line.strip()}")
                        # Try to extract device index
                        if '[' in line:
                            device_idx = line.split('[')[1].split(']')[0]
                            audio_devices.append(device_idx)

            # Try different audio input methods in order of preference
            recording_started = False

            # Method 1: Try with explicit device index
            for device_idx in audio_devices:
                if recording_started:
                    break

                print(f"🎤 Trying audio device [{device_idx}]...")
                self.recording_process = subprocess.Popen([
                    "ffmpeg",
                    "-f", "avfoundation",
                    "-i", f":{device_idx}",  # Use device index
                    "-ar", "16000",
                    "-ac", "1",
                    "-acodec", "pcm_s16le",
                    "-y",
                    self.audio_file
                ], stderr=subprocess.PIPE, stdout=subprocess.PIPE)

                # Check if it started successfully
                time.sleep(0.5)
                if self.recording_process.poll() is None:
                    print(f"✅ Recording started with device [{device_idx}]")
                    recording_started = True
                    break
                else:
                    stderr = self.recording_process.stderr.read().decode()[:200]
                    print(f"   Failed: {stderr}")

            # Method 2: Try with explicit device names
            if not recording_started:
                device_names = [":MacBook Pro Microphone", ":0", ":default"]
                for device_name in device_names:
                    print(f"🎤 Trying device name: {device_name}")
                    self.recording_process = subprocess.Popen([
                        "ffmpeg",
                        "-f", "avfoundation",
                        "-i", device_name,
                        "-ar", "16000",
                        "-ac", "1",
                        "-acodec", "pcm_s16le",
                        "-y",
                        self.audio_file
                    ], stderr=subprocess.PIPE, stdout=subprocess.PIPE)

                    time.sleep(0.5)
                    if self.recording_process.poll() is None:
                        print(f"✅ Recording started with {device_name}")
                        recording_started = True
                        break

            if recording_started:
                print(f"🎙️ Recording audio to {self.audio_file}")
                print("🔴 RECORDING NOW - Please speak clearly into your microphone")
            else:
                print("❌ Failed to start audio recording with any method")
                raise subprocess.CalledProcessError(1, "ffmpeg", "No audio device could be accessed")

        except subprocess.CalledProcessError:
            # Fallback: create a mock recording for demo
            print("⚠️ ffmpeg not found - using demo mode")
            self.is_recording = True
            self.start_time = time.time()
            self.meeting_title = meeting_title
            self.attendees = attendees
            self.use_demo = True

            return {
                "status": "recording",
                "mode": "demo",
                "message": "Demo recording started - call /meeting/stop to complete",
                "start_time": datetime.now().isoformat()
            }

        self.is_recording = True
        self.start_time = time.time()
        self.meeting_title = meeting_title
        self.attendees = attendees

        return {
            "status": "recording",
            "audio_file": self.audio_file,
            "start_time": datetime.now().isoformat()
        }

    def stop_recording(self) -> Dict:
        """Stop recording and process the audio."""

        if not self.is_recording:
            return {"error": "Not recording"}

        # If in demo mode, create demo transcript
        if self.use_demo:
            self.is_recording = False
            duration = time.time() - self.start_time if self.start_time else 0
            result = self._create_demo_recording(self.meeting_title, self.attendees)
            result["duration"] = duration
            # Reset state
            self.use_demo = False
            self.start_time = None
            return result

        # Stop the recording process
        if self.recording_process:
            try:
                self.recording_process.terminate()
                stdout, stderr = self.recording_process.communicate(timeout=2)
                if stderr:
                    stderr_text = stderr.decode()
                    # Look for audio level information
                    if 'mean_volume' in stderr_text or 'max_volume' in stderr_text:
                        print(f"📢 Audio levels from recording:")
                        for line in stderr_text.split('\n'):
                            if 'volume' in line.lower():
                                print(f"   {line.strip()}")
                    else:
                        print(f"⚠️ FFmpeg output: {stderr_text[:500]}")
            except subprocess.TimeoutExpired:
                self.recording_process.kill()
                self.recording_process.wait()
            except Exception as e:
                print(f"Error stopping recording process: {e}")

        self.is_recording = False
        duration = time.time() - self.start_time if self.start_time else 0

        # Process and verify
        result = self._process_and_verify()
        result["duration"] = duration

        # Reset state
        self.recording_process = None
        self.audio_file = None
        self.start_time = None

        return result

    def _create_demo_recording(self, meeting_title: str, attendees: List[str]) -> Dict:
        """Create a demo transcript for testing without audio."""

        # Create demo transcript
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_file = f"output/transcripts/demo_{timestamp}.txt"
        Path(transcript_file).parent.mkdir(parents=True, exist_ok=True)

        # Generate demo transcript content
        demo_content = f"""Speaker 1  0:00
Good morning everyone. Welcome to {meeting_title}. Let's begin with roll call.

Speaker 2  0:10
{attendees[0] if attendees else 'Alice'} here, ready to proceed.

Speaker 3  0:15
{attendees[1] if len(attendees) > 1 else 'Bob'} present.

Speaker 1  0:20
Excellent. We have a quorum. Today we'll cover three main items:
First, approval of previous meeting minutes.
Second, quarterly financial review.
Third, discussion of upcoming initiatives.

Speaker 2  0:35
I motion to approve the previous meeting minutes as distributed.

Speaker 3  0:40
I second the motion.

Speaker 1  0:42
All in favor? Motion passes unanimously.

Speaker 2  0:48
For the financial review, I'm pleased to report strong Q3 performance.
Revenue exceeded projections by 15%.
Operating expenses remained under budget.

Speaker 3  1:05
Those are excellent results. What about our customer acquisition metrics?

Speaker 2  1:12
Customer acquisition cost is trending slightly higher at $15,000, up from $12,000.
We need to monitor this closely.

Speaker 1  1:25
Let's make that an action item. Can you prepare a CAC reduction strategy for next meeting?

Speaker 2  1:32
I'll have that ready by next month.

Speaker 3  1:36
For upcoming initiatives, we need to prioritize our product roadmap.
I propose focusing on mobile features first.

Speaker 1  1:45
Let's formalize that. I motion to prioritize mobile development for Q4.

Speaker 2  1:52
I second the motion.

Speaker 1  1:54
All in favor? Motion carries.

Speaker 3  2:00
I'll work with engineering to create the implementation plan.

Speaker 1  2:05
Excellent. Any other business?

Speaker 2  2:08
We should schedule our annual planning session.

Speaker 1  2:12
I'll send out a calendar poll. If there's no other business, I move to adjourn.

Speaker 3  2:18
Second.

Speaker 1  2:20
Meeting adjourned. Thank you everyone.
"""

        # Write demo transcript
        with open(transcript_file, 'w') as f:
            f.write(demo_content)

        # Process immediately
        result = self._process_transcript(transcript_file)

        return {
            "status": "demo_complete",
            "transcript_file": transcript_file,
            "message": "Demo transcript created and processed",
            **result
        }

    def _process_and_verify(self) -> Dict:
        """Process the recording and verify."""

        # Create transcript from audio using Whisper
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript_file = f"output/transcripts/meeting_{timestamp}.txt"
        Path(transcript_file).parent.mkdir(parents=True, exist_ok=True)

        # Check if audio file exists and has content
        if self.audio_file and Path(self.audio_file).exists():
            file_size = Path(self.audio_file).stat().st_size
            print(f"📊 Audio file size: {file_size} bytes")

            if file_size > 1000:  # At least 1KB of audio
                # First, analyze the audio file to check if it contains sound
                try:
                    # Use ffmpeg to check audio levels
                    audio_check = subprocess.run([
                        "ffmpeg", "-i", self.audio_file, "-af", "volumedetect", "-f", "null", "-"
                    ], capture_output=True, text=True, timeout=10)

                    if audio_check.stderr:
                        print("📢 Audio analysis:")
                        for line in audio_check.stderr.split('\n'):
                            if 'mean_volume' in line or 'max_volume' in line:
                                print(f"   {line.strip()}")
                                # Check if audio is too quiet (below -60 dB is essentially silence)
                                if 'mean_volume' in line:
                                    try:
                                        volume = float(line.split(':')[1].strip().split()[0])
                                        if volume < -60:
                                            print("⚠️ WARNING: Audio appears to be silent or very quiet!")
                                            print("🎙️ Please ensure:")
                                            print("   1. Your microphone is not muted")
                                            print("   2. Terminal/IDE has microphone permission in System Settings")
                                            print("   3. You're speaking close enough to the microphone")
                                    except:
                                        pass
                except Exception as e:
                    print(f"Could not analyze audio levels: {e}")

                # Try to transcribe with Whisper
                try:
                    print("🎯 Transcribing audio with Whisper...")
                    import whisper

                    # Load Whisper model (base is fast and good enough)
                    model = whisper.load_model("base")

                    # Transcribe the audio with adjusted parameters for low volume
                    result = model.transcribe(
                        self.audio_file,
                        language="en",
                        fp16=False,  # Use FP32 for better accuracy
                        verbose=True  # Show progress
                    )

                    print(f"📝 Whisper result: {result.get('text', '')[:100]}...")

                    # Format transcript in Otter.ai style
                    with open(transcript_file, 'w') as f:
                        f.write(f"{self.meeting_title}\n")
                        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d')}\n")
                        f.write(f"Attendees: {', '.join(self.attendees)}\n\n")

                        # Check if we got any text at all
                        full_text = result.get("text", "").strip()

                        if full_text:
                            # Write the transcribed text with segments if available
                            segments = result.get("segments", [])
                            if segments:
                                for segment in segments:
                                    timestamp_min = int(segment['start'] // 60)
                                    timestamp_sec = int(segment['start'] % 60)
                                    text = segment['text'].strip()
                                    if text:
                                        f.write(f"Speaker  {timestamp_min}:{timestamp_sec:02d}\n")
                                        f.write(f"{text}\n\n")
                            else:
                                # No segments, just write the full text
                                f.write("Speaker  0:00\n")
                                f.write(full_text + "\n")
                        else:
                            # No speech detected
                            f.write("Speaker  0:00\n")
                            f.write("[No speech detected in audio. Please speak clearly into microphone.]\n")
                            print("⚠️ No speech detected by Whisper")

                    print(f"✅ Transcription complete: {transcript_file}")

                except ImportError:
                    print("⚠️ Whisper not installed. Installing...")
                    subprocess.run([
                        "pip3", "install", "openai-whisper"
                    ], capture_output=True)
                    print("Please restart the application and try again.")
                    return {"error": "Whisper installed. Please restart and try again."}

                except Exception as e:
                    print(f"❌ Transcription error: {e}")
                    # Create basic transcript as fallback
                    with open(transcript_file, 'w') as f:
                        f.write(f"Meeting: {self.meeting_title}\n")
                        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d')}\n")
                        f.write(f"Attendees: {', '.join(self.attendees)}\n\n")
                        f.write("Speaker  0:00\n")
                        f.write("[Audio recorded but transcription failed]\n")
            else:
                print("⚠️ Audio file too small, using placeholder")
                with open(transcript_file, 'w') as f:
                    f.write(f"Meeting: {self.meeting_title}\n")
                    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d')}\n")
                    f.write(f"Attendees: {', '.join(self.attendees)}\n\n")
                    f.write("Speaker  0:00\n")
                    f.write("[No audio content recorded]\n")
        else:
            print("⚠️ No audio file found")
            with open(transcript_file, 'w') as f:
                f.write(f"Meeting: {self.meeting_title}\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d')}\n")
                f.write(f"Attendees: {', '.join(self.attendees)}\n\n")
                f.write("Speaker  0:00\n")
                f.write("This is a recorded meeting transcript.\n")

        return self._process_transcript(transcript_file)

    def _process_transcript(self, transcript_file: str) -> Dict:
        """Process transcript through VeriMinutes."""

        try:
            # Ingest transcript
            meeting_date = datetime.now().strftime("%Y-%m-%d")
            slug, transcript_path, manifest_path = self.verifier.ingest_transcript(
                transcript_file,
                date=meeting_date,
                attendees=",".join(self.attendees) if self.attendees else "",
                title=self.meeting_title if hasattr(self, 'meeting_title') else "Meeting"
            )

            # Build artifacts
            paths = self.verifier.build_artifacts(slug)

            # Verify
            verification = self.verifier.verify_artifacts(slug)

            return {
                "success": True,
                "slug": slug,
                "transcript_path": transcript_path,
                "pdf_path": paths.get("pdf"),
                "packet_path": paths.get("packet"),
                "verification": {
                    "valid": verification.valid,
                    "doc_hash": verification.docHash,
                    "merkle_root": verification.localRoot
                }
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# Global instance
simple_recorder = SimpleMeetingRecorder()