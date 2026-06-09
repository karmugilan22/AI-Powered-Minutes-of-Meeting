import os
import json
import logging
import uuid
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import local modules
from backend.database import (
    init_db, create_meeting, get_meetings, get_meeting, 
    update_meeting_status, update_meeting_data, delete_meeting
)
from backend.recorder import recorder, SOUNDDEVICE_AVAILABLE
from backend.ai_engine import transcribe_and_summarize
from backend.pdf_report import generate_mom_pdf

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mom_assistant.main")

# Initialize DB on startup
init_db()

app = FastAPI(title="AI-Powered MoM Assistant API")

# Add CORS Middleware for local developer flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SETTINGS_PATH = os.path.join("data", "settings.json")
AUDIO_DIR = os.path.join("data", "audio")
PDF_DIR = os.path.join("data", "pdf")

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

class SettingsModel(BaseModel):
    gemini_api_key: Optional[str] = ""
    recording_device_id: Optional[int] = None
    company_name: Optional[str] = ""
    ollama_model: Optional[str] = "tinyllama"

def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
    
    # Check environment variable as fallback
    env_key = os.environ.get("GEMINI_API_KEY", "")
    return {
        "gemini_api_key": env_key,
        "recording_device_id": None,
        "company_name": "MoM Assistant",
        "ollama_model": "tinyllama"
    }

def save_settings_to_file(settings: dict):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    try:
        with open(SETTINGS_PATH, 'w') as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False

def get_wav_duration(filepath):
    import wave
    try:
        with wave.open(filepath, 'rb') as f:
            frames = f.getnframes()
            rate = f.getframerate()
            duration = frames / float(rate)
            return int(duration)
    except Exception as e:
        logger.error(f"Could not read WAV duration: {e}")
        return 0

# Background task to transcribe and summarize the meeting audio
def process_meeting_background(meeting_id: int, audio_path: str, api_key: str):
    logger.info(f"Starting background processing for meeting ID: {meeting_id}")
    try:
        # Determine duration
        duration = get_wav_duration(audio_path)
        
        settings = load_settings()
        ollama_model = settings.get("ollama_model", "tinyllama")
        
        # Call AI Engine
        result = transcribe_and_summarize(audio_path, api_key=api_key, ollama_model=ollama_model)
        
        # Save to database
        update_meeting_data(
            meeting_id=meeting_id,
            transcript=result["transcript"],
            summary_dict=result["summary"],
            duration=duration,
            status="completed"
        )
        logger.info(f"Background processing completed for meeting ID: {meeting_id}")
    except Exception as e:
        logger.error(f"Failed background processing for meeting ID {meeting_id}: {e}", exc_info=True)
        # Store failure state and template error message
        error_summary = {
            "overview": "Failed to generate AI Summary due to an internal error.",
            "key_points": [f"Error description: {str(e)}", "Verify your internet connection and Gemini API Key."],
            "decisions": ["None"],
            "action_items": [{"task": "Review backend logs & reprocess audio", "assignee": "Administrator", "deadline": "Asap"}]
        }
        update_meeting_data(
            meeting_id=meeting_id,
            transcript=f"Processing error: {str(e)}",
            summary_dict=error_summary,
            status="failed"
        )

# API ENDPOINTS

@app.get("/api/settings")
def get_settings():
    settings = load_settings()
    # Mask API Key in response for security
    masked_key = ""
    if settings.get("gemini_api_key"):
        key = settings["gemini_api_key"]
        masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "Saved (Masked)"
        
    devices = recorder.get_input_devices() if SOUNDDEVICE_AVAILABLE else []
    
    return {
        "settings": {
            "gemini_api_key": masked_key,
            "has_key": bool(settings.get("gemini_api_key")),
            "recording_device_id": settings.get("recording_device_id"),
            "company_name": settings.get("company_name", ""),
            "ollama_model": settings.get("ollama_model", "tinyllama")
        },
        "audio_devices": devices,
        "sounddevice_available": SOUNDDEVICE_AVAILABLE
    }

@app.post("/api/settings")
def update_settings(data: SettingsModel):
    settings = load_settings()
    
    # If the key was not provided (or matches masked), retain the existing one
    new_key = data.gemini_api_key.strip()
    if new_key and not (new_key.startswith("Saved") or "..." in new_key):
        settings["gemini_api_key"] = new_key
    elif not new_key:
        settings["gemini_api_key"] = ""
        
    settings["recording_device_id"] = data.recording_device_id
    settings["company_name"] = data.company_name
    settings["ollama_model"] = data.ollama_model or "tinyllama"
    
    if save_settings_to_file(settings):
        return {"status": "success", "message": "Settings updated successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save settings file")

@app.get("/api/meetings")
def list_meetings():
    return get_meetings()

@app.get("/api/meetings/{meeting_id}")
def view_meeting(meeting_id: int):
    meeting = get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting

@app.post("/api/meetings/upload")
def upload_meeting_audio(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    file: UploadFile = File(...)
):
    # Save uploaded file
    file_ext = os.path.splitext(file.filename)[1]
    # We enforce saving as a secure filename to avoid path traversal
    safe_name = f"{uuid.uuid4()}{file_ext}"
    dest_path = os.path.join(AUDIO_DIR, safe_name)
    
    logger.info(f"Saving uploaded file to {dest_path}")
    try:
        with open(dest_path, "wb") as buffer:
            buffer.write(file.file.read())
    except Exception as e:
        logger.error(f"Error saving uploaded audio file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save audio file")
        
    # Get configuration and API Key
    settings = load_settings()
    api_key = settings.get("gemini_api_key", "")
    
    # Create meeting record in DB (status: processing)
    meeting_id = create_meeting(title=title, audio_path=dest_path, status="processing")
    
    # Add background processing task
    background_tasks.add_task(process_meeting_background, meeting_id, dest_path, api_key)
    
    return {
        "status": "success",
        "meeting_id": meeting_id,
        "message": "Audio file uploaded. Processing started in background."
    }

@app.post("/api/meetings/record/start")
def start_server_recording():
    if not SOUNDDEVICE_AVAILABLE:
        raise HTTPException(status_code=400, detail="Physical microphone recording is not supported on this host (libraries missing).")
        
    settings = load_settings()
    device_id = settings.get("recording_device_id")
    
    # Formulate path
    safe_name = f"record_{uuid.uuid4()}.wav"
    output_path = os.path.join(AUDIO_DIR, safe_name)
    
    try:
        started = recorder.start_recording(output_path, device_id=device_id)
        if started:
            return {"status": "success", "message": "Microphone recording started on host."}
        else:
            return {"status": "warning", "message": "Recording already in progress."}
    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/meetings/record/status")
def get_recording_status():
    return {
        "is_recording": recorder.is_recording,
        "duration": recorder.duration,
        "sounddevice_available": SOUNDDEVICE_AVAILABLE
    }

@app.post("/api/meetings/record/stop")
def stop_server_recording(
    background_tasks: BackgroundTasks,
    title: str = Query(...)
):
    if not recorder.is_recording:
        raise HTTPException(status_code=400, detail="No active recording to stop.")
        
    audio_path = recorder.output_filepath
    duration = recorder.stop_recording()
    
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=500, detail="Failed to save recorded audio file.")
        
    settings = load_settings()
    api_key = settings.get("gemini_api_key", "")
    
    # Create meeting record in DB (status: processing)
    meeting_id = create_meeting(title=title, audio_path=audio_path, duration=duration, status="processing")
    
    # Add background processing task
    background_tasks.add_task(process_meeting_background, meeting_id, audio_path, api_key)
    
    return {
        "status": "success",
        "meeting_id": meeting_id,
        "message": "Microphone recording stopped. Processing started in background."
    }

@app.delete("/api/meetings/{meeting_id}")
def remove_meeting(meeting_id: int):
    meeting = get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
        
    delete_meeting(meeting_id)
    return {"status": "success", "message": "Meeting deleted successfully"}

@app.get("/api/meetings/{meeting_id}/pdf")
def download_pdf(meeting_id: int):
    meeting = get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
        
    if meeting["status"] != "completed":
        raise HTTPException(status_code=400, detail="Meeting reports can only be generated for completed transcriptions.")
        
    # Formulate output file name
    pdf_filename = f"MoM_{meeting_id}_{uuid.uuid4().hex[:8]}.pdf"
    pdf_path = os.path.join(PDF_DIR, pdf_filename)
    
    try:
        generate_mom_pdf(meeting, pdf_path)
        return FileResponse(
            pdf_path, 
            media_type="application/pdf", 
            filename=f"Minutes_of_Meeting_{meeting['id']}.pdf"
        )
    except Exception as e:
        logger.error(f"Error generating PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")

@app.get("/api/meetings/{meeting_id}/audio")
def stream_audio(meeting_id: int):
    meeting = get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    audio_path = meeting.get("audio_path")
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    media_type = "audio/wav"
    if audio_path.endswith(".mp3"):
        media_type = "audio/mp3"
    elif audio_path.endswith(".webm"):
        media_type = "audio/webm"
    elif audio_path.endswith(".m4a"):
        media_type = "audio/x-m4a"
        
    return FileResponse(audio_path, media_type=media_type)

class RenameModel(BaseModel):
    title: str

@app.patch("/api/meetings/{meeting_id}")
def update_meeting_title(meeting_id: int, data: RenameModel):
    from backend.database import rename_meeting
    meeting = get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    rename_meeting(meeting_id, data.title)
    return {"status": "success", "message": "Meeting renamed successfully"}

# Mount static frontend
# We check if frontend exists and serve it
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def serve_index():
    # If the user goes to root, serve frontend/index.html
    index_path = os.path.join("frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "backend_running", "message": "Frontend static assets directory 'frontend' not found."}
