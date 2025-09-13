import pytest
import tempfile
from pathlib import Path

from src.app.hashing import HashingService


class TestHashingService:
    def setup_method(self):
        self.service = HashingService()

    def test_sha256_hash(self):
        data = b"Hello, World!"
        expected = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        assert self.service.compute_sha256(data) == expected

    def test_blake3_hash(self):
        data = b"Hello, World!"
        result = self.service.compute_blake3(data)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_file_hashes(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b"Test content for hashing")
            temp_path = f.name

        try:
            sha256, blake3, size = self.service.compute_file_hashes(temp_path)
            assert len(sha256) == 64
            assert len(blake3) == 64
            assert size == 24
        finally:
            Path(temp_path).unlink()

    def test_sign_and_verify(self):
        data = b"Sign this message"
        signature = self.service.sign_data(data)
        public_key = self.service.get_public_key()

        assert self.service.verify_signature(data, signature, public_key)

        assert not self.service.verify_signature(b"Different data", signature, public_key)

    def test_create_credential(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"test": "data"}')
            temp_path = f.name

        try:
            cred = self.service.create_credential(temp_path, "TestSchema_v1")

            assert cred["target"] == Path(temp_path).name
            assert cred["schema"] == "TestSchema_v1"
            assert "sha256" in cred
            assert "blake3" in cred
            assert "signature" in cred
            assert cred["signer"]["type"] == "ed25519"
        finally:
            Path(temp_path).unlink()

    def test_verify_credential(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"test": "data"}')
            temp_path = f.name

        try:
            cred = self.service.create_credential(temp_path, "TestSchema_v1")
            assert self.service.verify_credential(cred, temp_path)

            cred["sha256"] = "0" * 64
            assert not self.service.verify_credential(cred, temp_path)
        finally:
            Path(temp_path).unlink()