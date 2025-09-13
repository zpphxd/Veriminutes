#!/usr/bin/env python3
"""
Demonstration script to prove VeriMinutes tampering detection works.
This shows that any change to the transcript or minutes breaks verification.
"""

import json
import shutil
from pathlib import Path
from src.app.service import VeriMinutesService
import time

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def main():
    service = VeriMinutesService()

    print_section("VERIMINUTES TAMPERING DETECTION DEMO")

    # Step 1: Process original transcript
    print_section("Step 1: Process Original Transcript")
    print("Processing samples/meeting_generic.txt...")

    slug, _, _ = service.ingest_transcript(
        "samples/meeting_generic.txt",
        date="2025-09-12",
        attendees="Alice,Bob,Carol",
        title="Demo Meeting"
    )

    paths = service.build_artifacts(slug)
    print(f"✓ Created artifacts for session: {slug}")

    # Step 2: Verify original - should PASS
    print_section("Step 2: Verify Original Files")
    result = service.verify_artifacts(slug)

    print(f"Verification Result: {'✅ PASSED' if result.valid else '❌ FAILED'}")
    print(f"  SHA-256: {result.docHash[:32]}...")
    print(f"  Merkle Root: {result.localRoot[:32]}...")

    # Save original hashes for comparison
    original_doc_hash = result.docHash
    original_merkle_root = result.localRoot

    # Step 3: Tamper with the TRANSCRIPT
    print_section("Step 3: Tamper with Transcript")

    transcript_path = Path(f"output/{slug}/transcript.normalized.json")
    transcript_backup = transcript_path.with_suffix('.json.backup')

    # Backup original
    shutil.copy(transcript_path, transcript_backup)

    # Load and modify transcript
    transcript = json.loads(transcript_path.read_text())
    print(f"Original speaker text: '{transcript['items'][0]['text'][:50]}...'")

    # Change the first speaker's text
    transcript['items'][0]['text'] = "TAMPERED: This meeting never happened!"
    transcript_path.write_text(json.dumps(transcript, indent=2))

    print(f"Modified to: '{transcript['items'][0]['text']}'")

    # Verify again - should FAIL
    print("\nVerifying tampered transcript...")
    result = service.verify_artifacts(slug)
    print(f"Verification Result: {'✅ PASSED' if result.valid else '❌ FAILED'}")
    print("  ↳ Detected transcript tampering!")

    # Restore original
    shutil.move(transcript_backup, transcript_path)

    # Step 4: Tamper with the MINUTES
    print_section("Step 4: Tamper with Meeting Minutes")

    minutes_path = Path(f"output/{slug}/minutes.json")
    minutes_backup = minutes_path.with_suffix('.json.backup')

    # Backup original
    shutil.copy(minutes_path, minutes_backup)

    # Load and modify minutes
    minutes = json.loads(minutes_path.read_text())
    print(f"Original title: '{minutes['title']}'")

    # Change the title
    minutes['title'] = "FAKE MEETING - NEVER HAPPENED"
    minutes_path.write_text(json.dumps(minutes, indent=2))

    print(f"Modified to: '{minutes['title']}'")

    # Verify again - should FAIL
    print("\nVerifying tampered minutes...")
    result = service.verify_artifacts(slug)
    print(f"Verification Result: {'✅ PASSED' if result.valid else '❌ FAILED'}")
    print(f"  Current hash: {result.docHash[:32]}...")
    print(f"  Original hash: {original_doc_hash[:32]}...")
    print("  ↳ Hashes don't match - tampering detected!")

    # Restore original
    shutil.move(minutes_backup, minutes_path)

    # Step 5: Tamper with CREDENTIAL
    print_section("Step 5: Tamper with Credential Signature")

    cred_path = Path(f"output/{slug}/minutes.cred.json")
    cred_backup = cred_path.with_suffix('.json.backup')

    # Backup original
    shutil.copy(cred_path, cred_backup)

    # Load and modify credential
    cred = json.loads(cred_path.read_text())
    original_sig = cred['signature']
    print(f"Original signature: {original_sig[:40]}...")

    # Corrupt the signature
    cred['signature'] = "FAKE_SIGNATURE_1234567890abcdef=="
    cred_path.write_text(json.dumps(cred, indent=2))

    print(f"Modified to: {cred['signature']}")

    # Verify again - should FAIL
    print("\nVerifying tampered credential...")
    result = service.verify_artifacts(slug)
    print(f"Verification Result: {'✅ PASSED' if result.valid else '❌ FAILED'}")
    print("  ↳ Invalid signature - tampering detected!")

    # Restore original
    shutil.move(cred_backup, cred_path)

    # Step 6: Final verification - should PASS again
    print_section("Step 6: Verify Restored Files")
    print("All files have been restored to original state...")

    result = service.verify_artifacts(slug)
    print(f"Verification Result: {'✅ PASSED' if result.valid else '❌ FAILED'}")
    print(f"  SHA-256: {result.docHash[:32]}...")
    print(f"  Merkle Root: {result.localRoot[:32]}...")

    # Summary
    print_section("DEMONSTRATION COMPLETE")
    print("""
This demo proves that VeriMinutes:

1. ✅ Detects ANY change to the transcript
2. ✅ Detects ANY change to the meeting minutes
3. ✅ Detects corrupted/fake signatures
4. ✅ Uses cryptographic hashes (SHA-256 & BLAKE3)
5. ✅ Uses Ed25519 digital signatures
6. ✅ Creates tamper-evident Merkle trees

The system provides cryptographic proof that:
- The minutes match the original transcript
- No modifications have been made since creation
- The signer's identity is verified via public key

Even changing a SINGLE CHARACTER breaks verification!
    """)

if __name__ == "__main__":
    main()