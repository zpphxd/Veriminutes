# VeriMinutes

Local-first verifiable minutes system that converts TXT transcripts to structured board minutes with cryptographic proofs.

## Features

- **TXT → JSON normalization**: Parse plain text transcripts into structured JSON
- **Board minutes structuring**: Extract agenda, motions, decisions, and action items
- **Cryptographic credentials**: Ed25519 signatures + SHA-256/BLAKE3 hashing
- **Merkle proofs**: 64KB chunking with inclusion proofs
- **Optional local anchoring**: Anchor to local EVM devnet (disabled by default)
- **PDF generation**: Professional meeting minutes PDFs
- **Full verification**: Verify integrity and authenticity of all artifacts

## Quick Start

```bash
# Setup
make setup

# Run API server
make api

# Process a transcript
make e2e
```

## CLI Usage

```bash
# Ingest a transcript
veriminutes ingest --path samples/meeting_generic.txt --date 2025-09-12 --attendees "Alice,Bob" --title "Q3 Board"

# Build credentials and proofs
veriminutes build --slug 2025-09-12-q3-board

# Verify artifacts
veriminutes verify --slug 2025-09-12-q3-board
```

## Architecture

- **100% local**: No external network calls
- **Stack**: Python 3.11, FastAPI, Pydantic, SQLite, hashlib, blake3, pynacl
- **Storage**: Content-addressable storage (CAS) for all artifacts
- **Verification**: Multi-layer verification (hashes, signatures, Merkle proofs)

## Output Structure

```
output/<slug>/
├── transcript.normalized.json    # Normalized transcript
├── minutes.json                  # Structured board minutes
├── minutes.cred.json            # Cryptographic credential
├── minutes.proof.json           # Merkle proof
├── minutes.packet.json          # Complete verification packet
├── minutes.pdf                  # Professional PDF output
├── manifest.json                # Artifact manifest
└── cas/                         # Content-addressable storage
    ├── sha256/
    └── blake3/
```