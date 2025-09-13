from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import tempfile
import shutil
from typing import Optional

from .service import VeriMinutesService
from .schema import (
    IngestRequest, IngestResponse,
    BuildRequest, BuildResponse,
    VerificationResult
)


app = FastAPI(
    title="BlackBox API",
    description="Cryptographically verified meeting minutes",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = VeriMinutesService()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest_transcript(request: IngestRequest):
    """Ingest a TXT transcript and normalize to JSON."""

    file_path = Path(request.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")

    try:
        slug, transcript_path, manifest_path = service.ingest_transcript(
            str(file_path),
            date=request.date,
            attendees=request.attendees,
            title=request.title
        )

        return IngestResponse(
            slug=slug,
            transcriptPath=transcript_path,
            manifestPath=manifest_path
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/build", response_model=BuildResponse)
async def build_artifacts(request: BuildRequest):
    """Build verification artifacts for a session."""

    try:
        paths = service.build_artifacts(request.slug)
        return BuildResponse(**paths)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/verify", response_model=VerificationResult)
async def verify_document(slug: str = Form(...)):
    """Verify a session's artifacts."""

    try:
        result = service.verify_artifacts(slug)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/verify", response_model=VerificationResult)
async def verify_artifacts(slug: str):
    """Verify artifacts for a session."""

    if not slug:
        raise HTTPException(status_code=400, detail="Slug parameter is required")

    try:
        result = service.verify_artifacts(slug)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/verify/packet")
async def verify_packet(file: UploadFile = File(...)):
    """Verify an uploaded proof packet - performs ACTUAL cryptographic verification."""
    import json
    import hashlib
    from .hashing import Hasher
    from .merkle import MerkleTree

    try:
        content = await file.read()
        packet_data = json.loads(content)

        # CRITICAL: Extract the actual transcript/minutes content
        minutes_content = packet_data.get("minutes", {})
        credential = packet_data.get("credential", {})
        proof = packet_data.get("proof", {})

        # Step 1: Recompute the SHA-256 hash of the actual content
        content_str = json.dumps(minutes_content, sort_keys=True, indent=2)
        computed_sha256 = hashlib.sha256(content_str.encode()).hexdigest()

        # Step 2: Compare computed hash with stored hash
        stored_sha256 = credential.get("sha256", "")
        hash_matches = (computed_sha256 == stored_sha256)

        # Step 3: Verify the digital signature (if present)
        signature_valid = False
        if credential.get("signature"):
            hasher = Hasher()
            # The signature is over the canonical JSON of the credential, not just the hash
            # We need to verify the entire credential structure
            cred_copy = credential.copy()
            if "signature" in cred_copy:
                sig = cred_copy.pop("signature")
                canonical_json = json.dumps(cred_copy, sort_keys=True, separators=(',', ':'))
                signature_valid = hasher.verify_signature(
                    canonical_json.encode('utf-8'),
                    sig,
                    credential.get("signer", {}).get("publicKey", "")
                )

        # Step 4: Verify Merkle tree integrity
        merkle_valid = False
        if proof.get("merkleRoot"):
            tree = MerkleTree()
            # Verify the content produces the same Merkle root
            merkle_valid = tree.verify_content_against_root(
                content_str,
                proof.get("merkleRoot")
            )

        # STRICT VALIDATION - ALL checks must pass
        # If any single check fails, the entire document is invalid
        has_signature = bool(credential.get("signature"))
        has_merkle = bool(proof.get("merkleRoot"))

        # Determine overall validity - EVERY check must pass
        is_valid = (
            hash_matches and  # Hash MUST match
            (signature_valid if has_signature else True) and  # If signed, signature MUST be valid
            (merkle_valid if has_merkle else True)  # If Merkle proof exists, it MUST be valid
        )

        # Determine specific failure reason
        failure_reason = None
        if not hash_matches:
            failure_reason = "TAMPERED: Document content has been modified!"
        elif has_signature and not signature_valid:
            failure_reason = "INVALID: Digital signature verification failed!"
        elif has_merkle and not merkle_valid:
            failure_reason = "CORRUPTED: Merkle tree verification failed!"

        verification_result = {
            "valid": is_valid,
            "details": {
                "hashMatch": hash_matches,
                "computedHash": computed_sha256,
                "storedHash": stored_sha256,
                "signatureValid": signature_valid if has_signature else None,
                "merkleValid": merkle_valid if has_merkle else None,
                "message": failure_reason if failure_reason else "VERIFIED: All cryptographic checks passed"
            },
            "credential": credential,
            "proof": proof,
            "stampedAt": packet_data.get("stampedAt"),
            "anchorReceipt": packet_data.get("anchorReceipt")
        }

        return verification_result
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid packet format: {str(e)}"}
        )


@app.post("/verify/transcript")
async def verify_transcript_against_stored(
    file: UploadFile = File(...),
    slug: Optional[str] = Form(None),
    date: Optional[str] = Form(None),
    title: Optional[str] = Form(None)
):
    """
    Verify a .txt transcript against stored proofs.
    Must provide either slug, date, or title to identify which session to verify against.
    """
    import hashlib

    try:
        # Read the uploaded transcript
        content = await file.read()
        content_str = content.decode('utf-8')

        # Compute hash of the new transcript
        computed_hash = hashlib.sha256(content).hexdigest()

        # Find the session to verify against
        target_slug = slug

        if not target_slug:
            # Try to find by date or title
            sessions = service.storage.list_sessions()
            for session_slug in sessions:
                try:
                    minutes = service.storage.read_artifact(session_slug, "minutes.json")
                    if date and minutes.get("date") == date:
                        target_slug = session_slug
                        break
                    if title and minutes.get("title") == title:
                        target_slug = session_slug
                        break
                except:
                    continue

        if not target_slug:
            return JSONResponse(
                status_code=404,
                content={"error": "No matching session found. Provide slug, date, or title."}
            )

        # Get the stored credential for comparison
        try:
            stored_cred = service.storage.read_artifact(target_slug, "minutes.cred.json")
            stored_transcript = service.storage.read_artifact(target_slug, "transcript.normalized.json")

            # Check if transcript matches
            transcript_items = stored_transcript.get("items", [])
            stored_text = "\n".join([item.get("text", "") for item in transcript_items])

            # Compare
            matches = (content_str.strip() == stored_text.strip())

            return {
                "valid": matches,
                "session": target_slug,
                "message": "Transcript matches stored version" if matches else "Transcript does NOT match",
                "storedHash": stored_cred.get("sha256"),
                "computedHash": computed_hash
            }

        except Exception as e:
            return JSONResponse(
                status_code=404,
                content={"error": f"Session {target_slug} not found or invalid"}
            )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/sessions")
async def list_sessions():
    """List all available sessions with metadata."""

    session_list = []
    for slug in service.storage.list_sessions():
        # Skip non-session directories
        if slug in ['recordings', 'transcripts', 'undefined']:
            continue

        try:
            manifest = service.storage.get_manifest(slug)

            # Try to get date and title from minutes.json
            date = ""
            title = slug.replace("-", " ").title()

            try:
                minutes = service.storage.read_artifact(slug, "minutes.json")
                date = minutes.get("date", "")
                title = minutes.get("title", title)
            except:
                pass

            session_list.append({
                "slug": slug,
                "date": date,
                "title": title,
                "createdAt": manifest.get("createdAt", "")
            })
        except:
            # If no manifest, try to extract date from slug
            parts = slug.split('-')
            if len(parts) >= 3:
                date = f"{parts[0]}-{parts[1]}-{parts[2]}"
                session_list.append({
                    "slug": slug,
                    "date": date,
                    "title": slug.replace("-", " ").title(),
                    "createdAt": ""
                })

    # Sort by date descending (most recent first)
    session_list.sort(key=lambda x: x.get("date", ""), reverse=True)

    return {"sessions": session_list}


@app.post("/upload")
async def upload_transcript(
    file: UploadFile = File(...),
    title: str = Form(...),
    date: str = Form(...),
    attendees: Optional[str] = Form(None)
):
    """Upload and process a transcript file."""

    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")

    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            content = await file.read()
            tmp.write(content.decode('utf-8'))
            temp_path = tmp.name

        # Process the transcript
        slug, transcript_path, manifest_path = service.ingest_transcript(
            temp_path,
            date=date,
            attendees=attendees,
            title=title
        )

        # Clean up temp file
        Path(temp_path).unlink()

        return {
            "slug": slug,
            "transcriptPath": transcript_path,
            "manifestPath": manifest_path
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/session/{slug}")
async def delete_session(slug: str):
    """Delete a session and all its artifacts."""

    try:
        session_dir = service.storage.get_session_dir(slug)

        if not session_dir.exists():
            raise HTTPException(status_code=404, detail="Session not found")

        # Delete the entire session directory
        import shutil
        shutil.rmtree(session_dir)

        return {"success": True, "message": f"Session {slug} deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{slug}/{artifact_type}")
async def download_artifact(slug: str, artifact_type: str):
    """Download a specific artifact."""

    session_dir = service.storage.get_session_dir(slug)

    file_mappings = {
        "pdf": "minutes.pdf",
        "packet": "minutes.packet.json",
        "proof": "minutes.proof.json",
        "transcript": "transcript.normalized.json",
        "minutes": "minutes.json",
        "credential": "minutes.cred.json"
    }

    if artifact_type not in file_mappings:
        raise HTTPException(status_code=404, detail="Invalid artifact type")

    file_path = session_dir / file_mappings[artifact_type]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")

    media_type = "application/pdf" if artifact_type == "pdf" else "application/json"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name
    )


# Meeting monitoring endpoint - using macOS recorder for real audio
from .macos_recorder import macos_recorder
from .simple_meeting import simple_recorder
import asyncio
from fastapi import WebSocket, WebSocketDisconnect


@app.post("/meeting/start")
async def start_meeting(
    title: str = Form("Meeting"),
    attendees: str = Form(""),
    auto_verify: bool = Form(True),
    use_real_audio: bool = Form(False)
):
    """Start recording a meeting (real audio or demo)."""

    # Always use simple recorder for now
    recorder = simple_recorder

    attendee_list = [a.strip() for a in attendees.split(',') if a.strip()]

    result = recorder.start_recording(
        meeting_title=title,
        attendees=attendee_list,
        use_real_audio=use_real_audio
    )

    return result


@app.post("/meeting/stop")
async def stop_meeting():
    """Stop recording and process the meeting."""

    # Check which recorder is active
    if macos_recorder.is_recording:
        result = macos_recorder.stop_recording()
    elif simple_recorder.is_recording:
        result = simple_recorder.stop_recording()
    else:
        return JSONResponse(
            status_code=400,
            content={"error": "No recording in progress"}
        )

    return result


@app.get("/meeting/status")
async def meeting_status():
    """Get current meeting recording status."""

    # Check which recorder is active
    is_recording = macos_recorder.is_recording or simple_recorder.is_recording

    return {
        "status": "recording" if is_recording else "idle",
        "is_recording": is_recording,
        "recorder": "macos" if macos_recorder.is_recording else ("simple" if simple_recorder.is_recording else "none")
    }


@app.websocket("/ws/meeting")
async def websocket_meeting(websocket: WebSocket):
    """WebSocket for real-time meeting updates."""
    await websocket.accept()

    try:
        while True:
            # Send updates if meeting is active
            is_recording = macos_recorder.is_recording or simple_recorder.is_recording
            if is_recording:
                await websocket.send_json({
                    "type": "status",
                    "data": {
                        "is_recording": is_recording,
                        "recorder": "macos" if macos_recorder.is_recording else "simple"
                    }
                })

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")


# Mount static files for the web interface
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")