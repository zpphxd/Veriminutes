"""
Speaker diarization module using voice embeddings.
Identifies and tracks different speakers in a meeting.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import pickle
from datetime import datetime
from scipy.spatial.distance import cosine
from sklearn.cluster import DBSCAN
import hashlib


class SpeakerProfile:
    """Represents a speaker's voice profile."""

    def __init__(self, name: str, embeddings: List[np.ndarray] = None):
        self.name = name
        self.embeddings = embeddings or []
        self.id = hashlib.sha256(name.encode()).hexdigest()[:8]
        self.created_at = datetime.now().isoformat()

    def add_embedding(self, embedding: np.ndarray):
        """Add a new voice embedding."""
        self.embeddings.append(embedding)

    def get_mean_embedding(self) -> Optional[np.ndarray]:
        """Get the average embedding for this speaker."""
        if not self.embeddings:
            return None
        return np.mean(self.embeddings, axis=0)

    def similarity(self, embedding: np.ndarray) -> float:
        """Calculate similarity to another embedding (0-1, higher is more similar)."""
        mean_emb = self.get_mean_embedding()
        if mean_emb is None:
            return 0.0
        return 1.0 - cosine(mean_emb, embedding)


class SpeakerDiarizer:
    """
    Speaker diarization using voice embeddings.
    Uses a simple embedding-based approach for speaker identification.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.75,
        profiles_path: str = "~/.veriminutes/speaker_profiles"
    ):
        """
        Initialize speaker diarizer.

        Args:
            similarity_threshold: Minimum similarity to identify a speaker
            profiles_path: Path to store speaker profiles
        """
        self.similarity_threshold = similarity_threshold
        self.profiles_path = Path(profiles_path).expanduser()
        self.profiles_path.mkdir(parents=True, exist_ok=True)

        # Load existing profiles
        self.speakers: Dict[str, SpeakerProfile] = self._load_profiles()

        # Current session tracking
        self.session_embeddings: List[Tuple[np.ndarray, str]] = []
        self.unknown_counter = 0

    def _load_profiles(self) -> Dict[str, SpeakerProfile]:
        """Load saved speaker profiles."""
        speakers = {}
        profiles_file = self.profiles_path / "profiles.pkl"

        if profiles_file.exists():
            try:
                with open(profiles_file, 'rb') as f:
                    speakers = pickle.load(f)
                print(f"Loaded {len(speakers)} speaker profiles")
            except Exception as e:
                print(f"Error loading profiles: {e}")

        return speakers

    def save_profiles(self):
        """Save speaker profiles to disk."""
        profiles_file = self.profiles_path / "profiles.pkl"
        try:
            with open(profiles_file, 'wb') as f:
                pickle.dump(self.speakers, f)
            print(f"Saved {len(self.speakers)} speaker profiles")
        except Exception as e:
            print(f"Error saving profiles: {e}")

    def enroll_speaker(self, name: str, audio_samples: List[np.ndarray]) -> SpeakerProfile:
        """
        Enroll a new speaker with voice samples.

        Args:
            name: Speaker's name
            audio_samples: List of audio samples for this speaker

        Returns:
            SpeakerProfile for the enrolled speaker
        """
        # Extract embeddings from audio samples
        embeddings = [self._extract_embedding(sample) for sample in audio_samples]

        # Create or update profile
        if name in self.speakers:
            profile = self.speakers[name]
            for emb in embeddings:
                profile.add_embedding(emb)
        else:
            profile = SpeakerProfile(name, embeddings)
            self.speakers[name] = profile

        # Save updated profiles
        self.save_profiles()

        print(f"Enrolled speaker: {name} with {len(embeddings)} samples")
        return profile

    def identify_speaker(self, audio_segment: np.ndarray) -> Tuple[str, float]:
        """
        Identify speaker from audio segment.

        Args:
            audio_segment: Audio segment to identify

        Returns:
            Tuple of (speaker_name, confidence)
        """
        # Extract embedding
        embedding = self._extract_embedding(audio_segment)

        # Find best matching speaker
        best_match = None
        best_similarity = 0.0

        for name, profile in self.speakers.items():
            similarity = profile.similarity(embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = name

        # Check if similarity meets threshold
        if best_similarity >= self.similarity_threshold:
            speaker_name = best_match
        else:
            # Unknown speaker
            self.unknown_counter += 1
            speaker_name = f"Speaker_{self.unknown_counter}"

        # Track for session
        self.session_embeddings.append((embedding, speaker_name))

        return speaker_name, best_similarity

    def _extract_embedding(self, audio_segment: np.ndarray) -> np.ndarray:
        """
        Extract voice embedding from audio segment.

        This is a simplified version using basic audio features.
        In production, you'd use a pre-trained model like Resemblyzer or SpeechBrain.
        """
        # Ensure audio is the right shape
        if len(audio_segment.shape) == 1:
            audio = audio_segment
        else:
            audio = audio_segment.flatten()

        # Simple feature extraction (for demo purposes)
        # In production, use a proper embedding model

        # Extract basic features
        features = []

        # 1. Spectral centroid (brightness)
        fft = np.fft.rfft(audio)
        magnitude = np.abs(fft)
        freqs = np.fft.rfftfreq(len(audio), 1/16000)
        if magnitude.sum() > 0:
            centroid = np.sum(freqs * magnitude) / magnitude.sum()
        else:
            centroid = 0
        features.append(centroid)

        # 2. Zero crossing rate (pitch indicator)
        zcr = np.sum(np.diff(np.sign(audio)) != 0) / len(audio)
        features.append(zcr)

        # 3. Energy (volume)
        energy = np.sqrt(np.mean(audio ** 2))
        features.append(energy)

        # 4. Spectral rolloff
        cumsum = np.cumsum(magnitude)
        if cumsum[-1] > 0:
            rolloff = freqs[np.where(cumsum >= 0.85 * cumsum[-1])[0][0]]
        else:
            rolloff = 0
        features.append(rolloff)

        # 5. MFCCs (simplified - normally use librosa)
        # Here we just use FFT bins as a proxy
        n_mfcc = 13
        if len(magnitude) >= n_mfcc:
            mfcc_proxy = magnitude[:n_mfcc]
        else:
            mfcc_proxy = np.pad(magnitude, (0, n_mfcc - len(magnitude)))
        features.extend(mfcc_proxy)

        # Create embedding vector
        embedding = np.array(features, dtype=np.float32)

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def cluster_session_speakers(self) -> Dict[str, List[int]]:
        """
        Cluster unknown speakers from the current session.

        Returns:
            Dictionary mapping speaker labels to segment indices
        """
        if not self.session_embeddings:
            return {}

        # Extract embeddings
        embeddings = np.array([emb for emb, _ in self.session_embeddings])

        # Cluster using DBSCAN
        clustering = DBSCAN(eps=0.3, min_samples=2, metric='cosine')
        labels = clustering.fit_predict(embeddings)

        # Group by cluster
        clusters = {}
        for idx, label in enumerate(labels):
            if label == -1:
                # Noise point - assign unique speaker
                speaker = f"Speaker_{idx}"
            else:
                speaker = f"Speaker_{label + 1}"

            if speaker not in clusters:
                clusters[speaker] = []
            clusters[speaker].append(idx)

        return clusters

    def generate_speaker_timeline(self, segments: List[Tuple[float, float, str]]) -> List[Dict]:
        """
        Generate a timeline of speaker segments.

        Args:
            segments: List of (start_time, end_time, speaker_name)

        Returns:
            List of speaker timeline entries
        """
        timeline = []

        for start, end, speaker in segments:
            timeline.append({
                "start": start,
                "end": end,
                "duration": end - start,
                "speaker": speaker
            })

        return timeline

    def get_speaker_statistics(self) -> Dict[str, Dict]:
        """
        Get statistics about speakers in the current session.

        Returns:
            Dictionary with speaker statistics
        """
        stats = {}

        # Count segments per speaker
        speaker_counts = {}
        for _, speaker in self.session_embeddings:
            if speaker not in speaker_counts:
                speaker_counts[speaker] = 0
            speaker_counts[speaker] += 1

        # Calculate statistics
        total_segments = len(self.session_embeddings)

        for speaker, count in speaker_counts.items():
            stats[speaker] = {
                "segments": count,
                "percentage": (count / total_segments * 100) if total_segments > 0 else 0,
                "is_enrolled": speaker in self.speakers
            }

        return stats

    def reset_session(self):
        """Reset the current session data."""
        self.session_embeddings = []
        self.unknown_counter = 0