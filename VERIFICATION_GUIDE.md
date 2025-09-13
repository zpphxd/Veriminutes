# BlackBox Verification Stamp Guide

## Overview
The BlackBox verification stamp provides cryptographic proof that your meeting minutes are authentic, unaltered, and timestamped. This guide explains each component of the verification stamp found at the bottom of your PDF documents and in the proof packet.

---

## Verification Stamp Components

### 1. Timestamp
**Example:** `Stamped at: 2025-09-13T05:05:15.732100+00:00`

- **What it is:** ISO 8601 formatted timestamp in UTC (Coordinated Universal Time)
- **Purpose:** Records the exact moment the document was processed and sealed
- **Why it matters:** Provides temporal proof of when the minutes were finalized
- **Format breakdown:**
  - `2025-09-13` - Date (Year-Month-Day)
  - `T` - Separator between date and time
  - `05:05:15.732100` - Time with microsecond precision
  - `+00:00` - UTC timezone offset

---

### 2. Document Hashes

#### SHA-256 Hash
**Example:** `SHA-256: 11735d4475e3cefd78acce9fe0a337f4c36ec51c3db5a5f15d35db35da9f6f8c`

- **What it is:** A 64-character hexadecimal fingerprint of your document
- **Algorithm:** Secure Hash Algorithm 256-bit (SHA-256)
- **Purpose:** Creates a unique identifier for your exact document content
- **Properties:**
  - Changing even one character in the document produces a completely different hash
  - It's computationally infeasible to create two different documents with the same hash
  - One-way function: you cannot reconstruct the document from the hash

#### BLAKE3 Hash
**Example:** `BLAKE3: 3a9474da26e42ca453b82c3ad2955891c65879522962219a06c4125a3d01c133`

- **What it is:** A modern cryptographic hash using the BLAKE3 algorithm
- **Purpose:** Provides an additional layer of verification using a different algorithm
- **Why two hashes?**
  - Defense in depth: if one algorithm is ever compromised, the other still provides security
  - BLAKE3 is faster and more modern than SHA-256
  - Different algorithms make collision attacks exponentially harder

---

### 3. Digital Signature

#### Public Key
**Example:** `Public Key: FXsgh5bLKa9zl8lAsmvGn/Rxtecsc4T6TtWndIrxefU=`

- **What it is:** The public half of an Ed25519 cryptographic key pair (Base64 encoded)
- **Algorithm:** Ed25519 (Edwards-curve Digital Signature Algorithm)
- **Purpose:** Identifies the signer and allows signature verification
- **How it works:**
  - BlackBox generates a unique key pair for your installation
  - The private key (kept secret) creates signatures
  - The public key (shared) verifies signatures

#### Signature
**Example:** `Signature: KMwHKC8yLJdsI42Ma5JECo5q2+yxL/cPi3iMH2O6ogyT...`

- **What it is:** A cryptographic signature of the document hash
- **Purpose:** Proves the document was signed by the holder of the private key
- **Verification:** Anyone with the public key can verify this signature
- **Properties:**
  - Cannot be forged without the private key
  - Tied to both the document content and the signer
  - Any document modification invalidates the signature

---

### 4. Merkle Tree Verification

#### Root Hash
**Example:** `Root Hash: c4ee892b97d1d32708e82a1d649455b3304f8dd3d76092ec6c189734f2648db0`

- **What it is:** The top hash of a Merkle tree structure
- **Purpose:** Enables efficient verification of large documents
- **How it works:**
  1. Document is split into 64KB chunks
  2. Each chunk is hashed individually (leaves)
  3. Hashes are paired and hashed together
  4. Process continues until a single root hash remains
- **Benefits:**
  - Can verify specific parts of a document without the entire file
  - Efficient for large documents
  - Used in blockchain technology

#### Leaf Count
**Example:** `Leaf Count: 1`

- **What it is:** Number of chunks the document was divided into
- **Purpose:** Indicates document size and structure
- **Calculation:** `Leaf Count = ceiling(Document Size / 64KB)`

---

### 5. Blockchain Anchor (Optional)
*Note: This section appears only when blockchain anchoring is enabled*

#### Transaction Hash
**Example:** `Transaction: 0x742d35cc6634c0532925a3b844bc454fc23d5a8f9e4f8a5c9e8b3d2f1a5b8c9d`

- **What it is:** Unique identifier of a blockchain transaction
- **Purpose:** Provides immutable timestamp on a public blockchain
- **Verification:** Can be looked up on blockchain explorers

#### Chain ID
**Example:** `Chain ID: 1` (Ethereum Mainnet)

- **What it is:** Identifies which blockchain network was used
- **Common values:**
  - 1: Ethereum Mainnet
  - 137: Polygon
  - 42161: Arbitrum One

#### Contract Address
**Example:** `Contract: 0x1234567890abcdef1234567890abcdef12345678`

- **What it is:** Smart contract address that stores the hash
- **Purpose:** Points to the on-chain location of your document proof

---

## Verification Process

### How to Verify a Document

1. **Hash Verification**
   - Recompute the SHA-256 hash of the minutes.json file
   - Compare with the hash in the verification stamp
   - If they match, the document is unaltered

2. **Signature Verification**
   - Use the public key to verify the signature
   - Confirms the document was signed by the claimed party
   - Ensures non-repudiation

3. **Merkle Proof Verification**
   - Verify the inclusion proof shows your document hash
   - Confirms the document is part of the merkle tree
   - Root hash should match the claimed root

4. **Blockchain Verification** (if applicable)
   - Look up the transaction on a blockchain explorer
   - Verify the merkle root is stored in the transaction
   - Check the timestamp matches the claimed time

---

## Security Properties

### What the Verification Stamp Proves

1. **Integrity**: The document has not been modified since stamping
2. **Authenticity**: The document was created by the claimed system
3. **Non-repudiation**: The signer cannot deny creating the document
4. **Timestamp**: The document existed at the claimed time
5. **Completeness**: All parts of the document are accounted for

### What It Does NOT Prove

1. **Content Accuracy**: Does not verify the truthfulness of the content
2. **Identity**: Does not verify real-world identity of participants
3. **Authorization**: Does not prove the signer had authority to create the document

---

## Proof Packet Structure

The `.packet.json` file contains all verification data:

```json
{
  "minutes": { /* Original minutes content */ },
  "transcript": { /* Full transcript */ },
  "credential": {
    "sha256": "document hash",
    "blake3": "alternate hash",
    "signer": { "publicKey": "..." },
    "signature": "..."
  },
  "proof": {
    "merkleRoot": "root hash",
    "leaves": ["array of chunk hashes"],
    "inclusion": { /* proof data */ }
  },
  "stampedAt": "ISO timestamp",
  "hashStamp": {
    "transcript_sha256": "...",
    "minutes_sha256": "...",
    "merkle_root": "..."
  }
}
```

---

## Best Practices

### For Document Creators
1. **Save the proof packet** - Store the `.packet.json` file securely
2. **Protect your private key** - Located at `~/.veriminutes/keys/ed25519.key`
3. **Record the timestamp** - Note when important documents were stamped
4. **Share the public key** - Distribute your public key for verification

### For Document Verifiers
1. **Always verify hashes** - Don't trust, verify
2. **Check multiple elements** - Verify hash, signature, and merkle proof
3. **Compare timestamps** - Ensure timing makes sense for the document
4. **Use independent tools** - Verify using standard cryptographic tools

---

## Technical Standards

- **Hashing**: SHA-256 (FIPS 180-4), BLAKE3
- **Signatures**: Ed25519 (RFC 8032)
- **Encoding**: Base64 for keys/signatures, Hexadecimal for hashes
- **Timestamps**: ISO 8601 with UTC timezone
- **Merkle Trees**: Binary tree with 64KB chunk size

---

## Glossary

- **Hash**: A fixed-size fingerprint of data
- **Digital Signature**: Cryptographic proof of authorship
- **Merkle Tree**: A tree structure of hashes for efficient verification
- **Public Key**: The shareable part of a cryptographic key pair
- **Private Key**: The secret part of a cryptographic key pair
- **UTC**: Coordinated Universal Time, the global time standard
- **Blockchain**: A distributed ledger for immutable timestamps
- **Non-repudiation**: Cannot deny having performed an action

---

*Generated by BlackBox - Cryptographically Verified Meeting Minutes*
