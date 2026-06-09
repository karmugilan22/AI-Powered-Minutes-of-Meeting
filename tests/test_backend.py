import os
import sys
import shutil

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, create_meeting, get_meetings, get_meeting, update_meeting_data, delete_meeting
from backend.pdf_report import generate_mom_pdf

def test_database():
    print("Testing Database Functions...")
    # Initialize DB (creates data/mom_assistant.db)
    init_db()
    
    # Create test meeting
    meeting_id = create_meeting("Test Meeting Title", audio_path="data/audio/test.wav", duration=120)
    print(f"Created meeting with ID: {meeting_id}")
    assert meeting_id is not None
    
    # Update meeting data
    mock_summary = {
        "overview": "This is a test overview summarizing the mock discussion.",
        "key_points": ["Point A was discussed.", "Point B was introduced."],
        "decisions": ["We decided to proceed with Test C."],
        "action_items": [{"task": "Complete tests", "assignee": "AI Tester", "deadline": "Immediate"}]
    }
    update_meeting_data(meeting_id, "Speaker 1: Hello. Speaker 2: Hi there.", mock_summary, duration=150, status="completed")
    print("Updated meeting data successfully.")
    
    # Retrieve meeting
    meeting = get_meeting(meeting_id)
    assert meeting is not None
    assert meeting["title"] == "Test Meeting Title"
    assert meeting["status"] == "completed"
    assert meeting["duration"] == 150
    assert meeting["summary"]["overview"] == "This is a test overview summarizing the mock discussion."
    print("Retrieved meeting details are valid.")
    
    # List meetings
    meetings = get_meetings()
    assert len(meetings) > 0
    print(f"Fetched meeting list: {len(meetings)} meetings total.")
    
    return meeting

def test_pdf_generation(meeting):
    print("Testing PDF Generation...")
    pdf_path = "data/pdf/test_mom_report.pdf"
    
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        
    generate_mom_pdf(meeting, pdf_path)
    
    assert os.path.exists(pdf_path)
    print(f"PDF successfully generated at {pdf_path} (size: {os.path.getsize(pdf_path)} bytes)")
    
    # Cleanup test files
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

if __name__ == "__main__":
    print("--- STARTING BACKEND TESTS ---")
    try:
        meeting_data = test_database()
        test_pdf_generation(meeting_data)
        
        # Cleanup test meeting
        delete_meeting(meeting_data["id"])
        print("Test meeting deleted and cleaned up successfully.")
        
        print("\n--- ALL BACKEND TESTS PASSED SUCCESSFULY ---")
        sys.exit(0)
    except Exception as e:
        print(f"\nTest Execution Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
