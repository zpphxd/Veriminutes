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
    title="VeriMinutes API",
    description="Local-first verifiable minutes system",
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
    """List all available sessions."""

    sessions = service.storage.list_sessions()
    return {"sessions": sessions}


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


# Meeting monitoring endpoint
from .meeting_monitor import MeetingMonitor
import asyncio
from fastapi import WebSocket, WebSocketDisconnect

# Global meeting monitor instance
meeting_monitor: Optional[MeetingMonitor] = None


@app.post("/meeting/start")
async def start_meeting(
    title: str = Form("Meeting"),
    attendees: str = Form(""),
    auto_verify: bool = Form(True)
):
    """Start a new meeting recording."""
    global meeting_monitor

    if meeting_monitor and meeting_monitor.is_monitoring:
        raise HTTPException(status_code=400, detail="Meeting already in progress")

    try:
        # Parse attendees
        attendees_list = [a.strip() for a in attendees.split(",") if a.strip()]

        # Create meeting monitor
        meeting_monitor = MeetingMonitor(
            meeting_title=title,
            attendees=attendees_list,
            auto_verify=auto_verify,
            model_size="tiny"  # Use tiny model for speed in demo
        )

        # Start meeting
        slug = meeting_monitor.start_meeting()

        return {
            "slug": slug,
            "status": "recording",
            "message": "Meeting started successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/meeting/stop")
async def stop_meeting():
    """Stop the current meeting recording."""
    global meeting_monitor

    if not meeting_monitor or not meeting_monitor.is_monitoring:
        raise HTTPException(status_code=400, detail="No meeting in progress")

    try:
        # Stop meeting and get results
        results = meeting_monitor.end_meeting()

        # Clear monitor
        meeting_monitor = None

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/meeting/status")
async def get_meeting_status():
    """Get current meeting status."""
    global meeting_monitor

    if not meeting_monitor:
        return {"status": "idle"}

    return meeting_monitor.get_meeting_status()


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