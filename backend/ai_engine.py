import os
import json
import logging
import time
import math
import wave

logger = logging.getLogger("mom_assistant.ai_engine")

# Fallback speech recognition
try:
    import speech_recognition as sr
except ImportError:
    sr = None

# Optional faster-whisper support (local Whisper model)
try:
    from faster_whisper import WhisperModel
    FW_AVAILABLE = True
except Exception:
    WhisperModel = None
    FW_AVAILABLE = False

def split_wav_file(input_path, chunk_duration_sec=12):
    """
    Splits a WAV file into smaller WAV chunks of chunk_duration_sec.
    Returns a list of chunk filepaths.
    """
    chunk_paths = []
    try:
        with wave.open(input_path, 'rb') as wav_file:
            params = wav_file.getparams()
            num_channels = params.nchannels
            sample_width = params.sampwidth
            frame_rate = params.framerate
            num_frames = params.nframes
            
            # Duration in seconds
            total_duration = num_frames / float(frame_rate)
            chunk_frames = int(frame_rate * chunk_duration_sec)
            
            num_chunks = math.ceil(total_duration / chunk_duration_sec)
            
            temp_dir = os.path.join("data", "audio", "tmp")
            os.makedirs(temp_dir, exist_ok=True)
            
            for i in range(num_chunks):
                chunk_path = os.path.join(temp_dir, f"chunk_{i}_{os.path.basename(input_path)}")
                
                with wave.open(chunk_path, 'wb') as chunk_file:
                    chunk_file.setparams(params)
                    wav_file.setpos(i * chunk_frames)
                    frames_data = wav_file.readframes(chunk_frames)
                    chunk_file.writeframes(frames_data)
                
                chunk_paths.append(chunk_path)
            logger.info(f"Successfully split WAV file into {len(chunk_paths)} chunks.")
    except Exception as e:
        logger.error(f"Failed to split WAV file: {e}")
        return [input_path]
        
    return chunk_paths


def _transcribe_with_whisper(audio_path, model_path="base"):
    """Transcribe audio using a local faster-whisper model.
    model_path can be a model name (e.g., 'small', 'base') or a local filesystem path to the model.
    """
    if not FW_AVAILABLE or WhisperModel is None:
        raise RuntimeError("faster-whisper is not available in the environment")

    # Create model instance (kept local to the call to avoid global GPU/CPU state issues)
    # Use CPU by default; if user has GPU set CUDA_VISIBLE_DEVICES or customize here
    device = os.environ.get("WHISPER_DEVICE", "cpu")
    logger.info(f"Loading Whisper model '{model_path}' on device '{device}'...")
    model = WhisperModel(model_path, device=device)

    logger.info("Starting transcription with faster-whisper...")
    segments, info = model.transcribe(audio_path, beam_size=5)
    texts = []
    try:
        for segment in segments:
            # segment.text contains the recognized text for this segment
            texts.append(segment.text)
    except Exception:
        # In some versions segments is an iterator
        for seg in segments:
            texts.append(getattr(seg, 'text', str(seg)))

    transcript = " ".join(t.strip() for t in texts if t and t.strip())
    return transcript

def transcribe_and_summarize(audio_path, api_key=None, ollama_model="tinyllama"):
    """
    Transcribes the audio file and generates a structured summary (Overview, Key Points, Decisions, Action Items).
    If api_key is provided, uses Gemini. Otherwise, falls back to local SpeechRecognition + Ollama.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Check if Gemini key is provided
    if api_key:
        try:
            return _process_with_gemini(audio_path, api_key)
        except Exception as e:
            logger.error(f"Gemini processing failed, trying fallback: {e}")
            # fall through to local recognition
    
    return _process_with_local_fallback(audio_path, ollama_model=ollama_model)

def _process_with_gemini(audio_path, api_key):
    logger.info("Processing audio with Google Gemini API...")
    from google import genai
    from google.genai import types

    # Initialize client
    client = genai.Client(api_key=api_key)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        audio_file = None
        try:
            logger.info(f"Uploading audio file to Gemini (Attempt {attempt}/{max_retries})...")
            audio_file = client.files.upload(file=audio_path)
            logger.info(f"Uploaded successfully. File name: {audio_file.name}")

            # Wait for the file to be processed if necessary
            state = audio_file.state.name
            while state == "PROCESSING":
                logger.info("Gemini is processing the uploaded audio file...")
                time.sleep(2)
                audio_file = client.files.get(name=audio_file.name)
                state = audio_file.state.name

            if state == "FAILED":
                raise RuntimeError("Gemini file processing failed on server.")

            prompt = """
            You are an expert executive assistant and minutes-of-meeting (MoM) creator.
            Analyze the provided audio recording of a meeting.
            
            Perform two tasks:
            1. Transcribe the meeting audio word-for-word. Identify different speakers if possible and label them (e.g., "Speaker A: ...", "Speaker B: ..."). Use proper formatting, paragraphs, and punctuation.
            2. Analyze the meeting and generate a structured minutes-of-meeting summary.

            Your output MUST be a JSON object matching this exact schema:
            {
              "transcript": "Full transcription text with speaker labels if possible.",
              "summary": {
                "overview": "A 2-3 sentence high-level overview of what was discussed and the main objective of the meeting.",
                "key_points": [
                  "Detailed key discussion point 1...",
                  "Detailed key discussion point 2..."
                ],
                "decisions": [
                  "Decision made 1...",
                  "Decision made 2..."
                ],
                "action_items": [
                  {
                    "task": "Clear, actionable description of the task",
                    "assignee": "Full name of the assignee or 'Unassigned' if not specified",
                    "deadline": "Target date or timeline, or 'Not specified'"
                  }
                ]
              }
            }

            Return ONLY the raw JSON object conforming to this schema. Do not enclose it in markdown blocks.
            """

            logger.info("Sending request to Gemini model (gemini-2.5-flash)...")
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[audio_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                ),
            )

            # Clean up the file from Gemini storage
            try:
                client.files.delete(name=audio_file.name)
                logger.info("Cleaned up uploaded file from Gemini.")
            except Exception as e:
                logger.warning(f"Failed to delete Gemini file: {e}")

            # Parse and validate response
            response_text = response.text.strip()
            data = json.loads(response_text)
            if "transcript" in data and "summary" in data:
                return data
            else:
                raise ValueError("Gemini response missing required keys.")

        except Exception as e:
            logger.error(f"Gemini API attempt {attempt} failed: {e}")
            # Ensure file is cleaned up if it was uploaded and we failed
            if audio_file:
                try:
                    client.files.delete(name=audio_file.name)
                except Exception:
                    pass
            
            if attempt == max_retries:
                # Re-raise error on final attempt to fall back
                raise e
            time.sleep(3) # Wait before retry

def _process_with_local_fallback(audio_path, ollama_model="tinyllama"):
    logger.info("Processing audio with local/offline SpeechRecognition fallback...")
    
    if not sr and not FW_AVAILABLE:
        return {
            "transcript": "No local speech recognition available. Install 'SpeechRecognition' or 'faster-whisper', or provide a Gemini API Key.",
            "summary": _get_no_key_summary_dict()
        }
    # If faster-whisper is available, prefer it for local transcription
    if FW_AVAILABLE:
        try:
            model_path = os.environ.get("WHISPER_MODEL_PATH") or os.environ.get("WHISPER_MODEL") or "base"
            logger.info(f"Using faster-whisper model at: {model_path}")
            transcript = _transcribe_with_whisper(audio_path, model_path=model_path)
            if transcript and transcript.strip():
                logger.info("Transcription via faster-whisper successful.")
                summary = _summarize_with_ollama(transcript, ollama_model)
                if not summary:
                    summary = _generate_rule_based_summary(transcript)
                return {
                    "transcript": transcript,
                    "summary": summary
                }
        except Exception as fw_err:
            logger.warning(f"faster-whisper transcription failed: {fw_err}")

    recognizer = sr.Recognizer()
    try:
        # Split audio into 12-second chunks to prevent free Google Speech Web API timeout errors (limited to ~15s)
        chunk_paths = split_wav_file(audio_path, chunk_duration_sec=12)
        transcripts = []
        
        logger.info(f"Audio split into {len(chunk_paths)} chunks for processing.")
        for idx, chunk_path in enumerate(chunk_paths):
            try:
                logger.info(f"Transcribing chunk {idx+1}/{len(chunk_paths)}...")
                with sr.AudioFile(chunk_path) as source:
                    audio_data = recognizer.record(source)
                    chunk_text = recognizer.recognize_google(audio_data)
                    if chunk_text.strip():
                        transcripts.append(chunk_text)
            except Exception as chunk_err:
                logger.warning(f"Failed to transcribe chunk {idx+1}: {chunk_err}")
            finally:
                # Remove chunk immediately to save space
                if chunk_path != audio_path and os.path.exists(chunk_path):
                    try:
                        os.remove(chunk_path)
                    except OSError:
                        pass
                        
        transcript = ". ".join(transcripts)
        if not transcript.strip():
            raise ValueError("All audio chunks failed to transcribe or file was silent.")
            
        logger.info("Local audio transcription complete. Requesting Ollama summary...")
        
        # Since we don't have an offline LLM, we generate a template summary based on transcription
        summary = _summarize_with_ollama(transcript, ollama_model)
        if not summary:
            logger.warning("Ollama summarization failed or not configured, falling back to rule-based summarization.")
            summary = _generate_rule_based_summary(transcript)
        
        return {
            "transcript": transcript,
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Local speech recognition failed: {e}", exc_info=True)
        return {
            "transcript": f"Speech transcription failed: {e}",
            "summary": _get_no_key_summary_dict(failed=True)
        }

def _generate_rule_based_summary(transcript):
    # Basic rule-based extraction for fallbacks
    sentences = transcript.split('.')
    overview = "This meeting was transcribed using the free Google Web Speech API fallback. For high-quality, structured summaries with decisions and action items, configure your Gemini API Key in Settings."
    
    # Try to extract key points or potential action items by keyword scanning
    key_points = []
    decisions = []
    action_items = []
    
    action_keywords = ["need to", "must", "should", "will", "action", "task", "assign", "todo"]
    decision_keywords = ["decided", "agreed", "concluded", "settled"]
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        lower_s = sentence.lower()
        
        # Classify sentence
        if any(kw in lower_s for kw in action_keywords):
            # Try to guess assignee: look for words capitalised or pronouns
            assignee = "Unassigned"
            words = sentence.split()
            for i, word in enumerate(words):
                if word in ["I", "we", "he", "she", "they"] or (word[0].isupper() and i > 0 and not words[i-1].endswith('.')):
                    assignee = word
                    break
            action_items.append({
                "task": sentence,
                "assignee": assignee,
                "deadline": "Not specified"
            })
        elif any(kw in lower_s for kw in decision_keywords):
            decisions.append(sentence)
        elif len(sentence) > 15:
            key_points.append(sentence)
            
    # Default values if empty
    if not key_points:
        key_points = [f"Discussed: {sentences[0]}..." if len(sentences) > 0 else "No key discussion points identified."]
    if not decisions:
        decisions = ["No explicit decisions identified. Try adding a Gemini API Key in Settings for AI extraction."]
    if not action_items:
        action_items = [{
            "task": "Add a Gemini API Key in Settings to unlock automated action item extraction.",
            "assignee": "System",
            "deadline": "Immediate"
        }]
        
    return {
        "overview": overview,
        "key_points": key_points[:5], # limit to 5
        "decisions": decisions[:3],
        "action_items": action_items[:3]
    }

def _get_no_key_summary_dict(failed=False):
    msg = "Transcription failed or was disabled." if failed else "Local transcription only."
    return {
        "overview": f"{msg} A Gemini API Key is required to automatically generate minutes of meetings, including summaries, key points, decisions, and action items.",
        "key_points": [
            "Please register a Gemini API key at Google AI Studio.",
            "Enter your key in the dashboard Settings panel to unlock AI-powered insights."
        ],
        "decisions": [
            "No API key provided."
        ],
        "action_items": [
            {
                "task": "Add Gemini API Key in Settings",
                "assignee": "Host Administrator",
                "deadline": "Before next meeting"
            }
        ]
    }

def _summarize_with_ollama(transcript, model_name="tinyllama"):
    import requests
    url = "http://localhost:11434/api/generate"
    
    # We construct a clean system/user style prompt for Ollama
    prompt = f"""
    You are an expert executive assistant and minutes-of-meeting (MoM) compiler.
    Based on the meeting transcript provided below, generate a structured minutes-of-meeting summary in JSON format.
    
    Transcript:
    "{transcript}"
    
    Your response must be a JSON object with this exact structure:
    {{
      "overview": "Write a 2-3 sentence summary of what was discussed and resolved.",
      "key_points": ["Write key discussion point 1", "Write key discussion point 2"],
      "decisions": ["Write decision 1", "Write decision 2"],
      "action_items": [
        {{
          "task": "Write task description",
          "assignee": "Name of assignee or Unassigned",
          "deadline": "Deadline date or Not specified"
        }}
      ]
    }}
    
    IMPORTANT: Generate the actual summary, points, decisions, and actions from the transcript. Do not use placeholders. Respond with ONLY the raw JSON.
    """
    
    try:
        logger.info(f"Contacting local Ollama service using model '{model_name}'...")
        response = requests.post(url, json={
            "model": model_name,
            "prompt": prompt,
            "format": "json",
            "stream": False
        }, timeout=90)  # 90 seconds timeout for local CPU/Pi execution
        
        if response.status_code == 200:
            res_json = response.json()
            response_text = res_json.get("response", "").strip()
            logger.info("Ollama response text received.")
            
            # Parse the JSON response
            data = json.loads(response_text)
            
            # Sanitize decisions (ensure it is a list of strings)
            if "decisions" in data and isinstance(data["decisions"], list):
                sanitized_decisions = []
                for d in data["decisions"]:
                    if isinstance(d, dict):
                        # Extract task/decision or stringify if the model generated a dict
                        sanitized_decisions.append(d.get("task") or d.get("decision") or d.get("Write decision 1") or str(d))
                    else:
                        sanitized_decisions.append(str(d))
                data["decisions"] = sanitized_decisions
                
            # Sanitize key_points (ensure it is a list of strings)
            if "key_points" in data and isinstance(data["key_points"], list):
                sanitized_points = []
                for pt in data["key_points"]:
                    if isinstance(pt, dict):
                        sanitized_points.append(pt.get("task") or pt.get("point") or str(pt))
                    else:
                        sanitized_points.append(str(pt))
                data["key_points"] = sanitized_points
                
            # Sanitize overview (ensure string)
            if "overview" in data:
                data["overview"] = str(data["overview"])
                
            # Sanitize action_items
            if "action_items" in data and isinstance(data["action_items"], list):
                sanitized_actions = []
                for item in data["action_items"]:
                    if isinstance(item, dict):
                        sanitized_actions.append({
                            "task": str(item.get("task") or item.get("Write task description") or "Task"),
                            "assignee": str(item.get("assignee") or item.get("Name of assignee or Unassigned") or "Unassigned"),
                            "deadline": str(item.get("deadline") or item.get("Deadline date or Not specified") or "Not specified")
                        })
                    else:
                        sanitized_actions.append({
                            "task": str(item),
                            "assignee": "Unassigned",
                            "deadline": "Not specified"
                        })
                data["action_items"] = sanitized_actions

            if "overview" in data and "key_points" in data and "decisions" in data and "action_items" in data:
                logger.info("Successfully generated and sanitized summary using local Ollama.")
                return data
            else:
                logger.warning("Ollama response did not match the expected MoM structure. Missing keys.")
        else:
            logger.warning(f"Ollama server returned status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Error communicating with local Ollama: {e}")
        
    return None
