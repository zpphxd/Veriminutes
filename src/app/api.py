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
    """Build credentials, proofs, and PDF for a session."""

    try:
        paths = service.build_artifacts(request.slug)

        return BuildResponse(
            minutesPath=paths.get("minutes", ""),
            credentialPath=paths.get("minutes_cred", ""),
            proofPath=paths.get("minutes_proof", ""),
            packetPath=paths.get("packet", ""),
            pdfPath=paths.get("pdf", ""),
            anchorReceiptPath=paths.get("anchor_receipt")
        )
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
    use_real_audio: bool = Form(True)
):
    """Start a new meeting recording."""

    try:
        # Parse attendees
        attendees_list = [a.strip() for a in attendees.split(",") if a.strip()]

        # Use real audio recorder if requested
        if use_real_audio:
            result = macos_recorder.start_recording(
                meeting_title=title,
                attendees=attendees_list
            )
        else:
            # Fallback to demo recorder
            result = simple_recorder.start_recording(
                meeting_title=title,
                attendees=attendees_list
            )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/meeting/stop")
async def stop_meeting():
    """Stop the current meeting recording."""

    try:
        # Stop whichever recorder is active
        if macos_recorder.is_recording:
            results = macos_recorder.stop_recording()
        else:
            results = simple_recorder.stop_recording()

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/meeting/status")
async def get_meeting_status():
    """Get current meeting status."""
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
            if meeting_monitor and meeting_monitor.is_monitoring:
                status = meeting_monitor.get_meeting_status()
                await websocket.send_json({
                    "type": "status",
                    "data": status
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