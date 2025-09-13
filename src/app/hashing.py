import hashlib
import json
import base64
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

import blake3
import nacl.signing
import nacl.encoding


class HashingService:
    """Cryptographic hashing and signing service."""

    def __init__(self, keys_path: str = "~/.veriminutes/keys"):
        self.keys_path = Path(keys_path).expanduser()
        self.keys_path.mkdir(parents=True, exist_ok=True)
        self.signing_key = self._get_or_create_signing_key()

    def _get_or_create_signing_key(self) -> nacl.signing.SigningKey:
        """Get existing Ed25519 key or create new one."""

        key_file = self.keys_path / "ed25519.key"

        if key_file.exists():
            with open(key_file, 'rb') as f:
                key_bytes = f.read()
                return nacl.signing.SigningKey(key_bytes)
        else:
            signing_key = nacl.signing.SigningKey.generate()
            with open(key_file, 'wb') as f:
                f.write(bytes(signing_key))
            key_file.chmod(0o600)
            return signing_key

    def compute_sha256(self, data: bytes) -> str:
        """Compute SHA-256 hash of data."""
        return hashlib.sha256(data).hexdigest()

    def compute_blake3(self, data: bytes) -> str:
        """Compute BLAKE3 hash of data."""
        return blake3.blake3(data).hexdigest()

    def compute_file_hashes(self, file_path: str) -> Tuple[str, str, int]:
        """Compute SHA-256 and BLAKE3 hashes for a file."""

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        data = path.read_bytes()
        sha256_hash = self.compute_sha256(data)
        blake3_hash = self.compute_blake3(data)

        return sha256_hash, blake3_hash, len(data)

    def sign_data(self, data: bytes) -> str:
        """Sign data with Ed25519 private key."""

        signed = self.signing_key.sign(data)
        return base64.b64encode(signed.signature).decode('ascii')

    def verify_signature(
        self,
        data: bytes,
        signature_b64: str,
        public_key_b64: str
    ) -> bool:
        """Verify Ed25519 signature."""

        try:
            signature = base64.b64decode(signature_b64)
            public_key_bytes = base64.b64decode(public_key_b64)
            verify_key = nacl.signing.VerifyKey(public_key_bytes)
            verify_key.verify(data, signature)
            return True
        except Exception:
            return False

    def get_public_key(self) -> str:
        """Get public key in base64 format."""

        public_key = self.signing_key.verify_key
        return base64.b64encode(bytes(public_key)).decode('ascii')

    def create_credential(
        self,
        target_file: str,
        schema: str
    ) -> Dict[str, Any]:
        """Create a cryptographic credential for a file."""

        sha256_hash, blake3_hash, size = self.compute_file_hashes(target_file)

        credential = {
            "target": Path(target_file).name,
            "sha256": sha256_hash,
            "blake3": blake3_hash,
            "size": size,
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "schema": schema,
            "signer": {
                "type": "ed25519",
                "publicKey": self.get_public_key()
            }
        }

        canonical_json = json.dumps(credential, sort_keys=True, separators=(',', ':'))
        signature = self.sign_data(canonical_json.encode('utf-8'))
        credential["signature"] = signature

        return credential

    def verify_credential(self, credential: Dict[str, Any], file_path: str) -> bool:
        """Verify a credential against a file."""

        try:
            sha256_hash, blake3_hash, size = self.compute_file_hashes(file_path)

            if (credential["sha256"] != sha256_hash or
                credential["blake3"] != blake3_hash or
                credential["size"] != size):
                return False

            cred_copy = credential.copy()
            signature = cred_copy.pop("signature")

            canonical_json = json.dumps(cred_copy, sort_keys=True, separators=(',', ':'))

            return self.verify_signature(
                canonical_json.encode('utf-8'),
                signature,
                credential["signer"]["publicKey"]
            )
        except Exception:
            return False