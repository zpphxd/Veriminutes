import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import re


class StorageService:
    """Content-addressable storage and manifest management."""

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_slug(
        self,
        date: Optional[str] = None,
        title: Optional[str] = None
    ) -> str:
        """Create a slug for the session."""

        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        slug = date

        if title:
            title_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
            slug = f"{date}-{title_slug}"

        return slug

    def get_session_dir(self, slug: str) -> Path:
        """Get or create session directory."""

        session_dir = self.output_dir / slug
        session_dir.mkdir(parents=True, exist_ok=True)

        (session_dir / "cas" / "sha256").mkdir(parents=True, exist_ok=True)
        (session_dir / "cas" / "blake3").mkdir(parents=True, exist_ok=True)

        return session_dir

    def store_artifact(
        self,
        slug: str,
        file_name: str,
        content: Any
    ) -> str:
        """Store an artifact in the session directory."""

        session_dir = self.get_session_dir(slug)
        file_path = session_dir / file_name

        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, indent=2)
            file_path.write_text(content_str, encoding='utf-8')
        elif isinstance(content, str):
            file_path.write_text(content, encoding='utf-8')
        elif isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            raise ValueError(f"Unsupported content type: {type(content)}")

        return str(file_path)

    def store_in_cas(
        self,
        slug: str,
        algo: str,
        hash_value: str,
        content: bytes
    ) -> str:
        """Store content in CAS."""

        cas_dir = self.get_session_dir(slug) / "cas" / algo
        cas_file = cas_dir / hash_value

        if not cas_file.exists():
            cas_file.write_bytes(content)

        return str(cas_file)

    def read_artifact(self, slug: str, file_name: str) -> Any:
        """Read an artifact from the session directory."""

        session_dir = self.get_session_dir(slug)
        file_path = session_dir / file_name

        if not file_path.exists():
            raise FileNotFoundError(f"Artifact not found: {file_path}")

        if file_name.endswith('.json'):
            return json.loads(file_path.read_text(encoding='utf-8'))
        else:
            return file_path.read_text(encoding='utf-8')

    def create_manifest(self, slug: str) -> Dict[str, Any]:
        """Create or update manifest for session."""

        session_dir = self.get_session_dir(slug)
        manifest_path = session_dir / "manifest.json"

        manifest = {
            "slug": slug,
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "updatedAt": datetime.utcnow().isoformat() + "Z",
            "artifacts": []
        }

        if manifest_path.exists():
            existing = json.loads(manifest_path.read_text())
            manifest["createdAt"] = existing.get("createdAt", manifest["createdAt"])

        return manifest

    def update_manifest(
        self,
        slug: str,
        artifact_type: str,
        file_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Update manifest with new artifact."""

        session_dir = self.get_session_dir(slug)
        manifest_path = session_dir / "manifest.json"

        manifest = self.create_manifest(slug)

        artifact_entry = {
            "type": artifact_type,
            "fileName": file_name,
            "path": str(session_dir / file_name),
            "createdAt": datetime.utcnow().isoformat() + "Z"
        }

        if metadata:
            artifact_entry.update(metadata)

        manifest["artifacts"] = [
            a for a in manifest.get("artifacts", [])
            if a.get("fileName") != file_name
        ]
        manifest["artifacts"].append(artifact_entry)
        manifest["updatedAt"] = datetime.utcnow().isoformat() + "Z"

        manifest_path.write_text(json.dumps(manifest, indent=2))

        return str(manifest_path)

    def get_manifest(self, slug: str) -> Dict[str, Any]:
        """Get manifest for session."""

        session_dir = self.get_session_dir(slug)
        manifest_path = session_dir / "manifest.json"

        if not manifest_path.exists():
            return self.create_manifest(slug)

        return json.loads(manifest_path.read_text())

    def list_sessions(self) -> List[str]:
        """List all session slugs."""

        sessions = []
        for path in self.output_dir.iterdir():
            if path.is_dir() and not path.name.startswith('.'):
                sessions.append(path.name)

        return sorted(sessions)