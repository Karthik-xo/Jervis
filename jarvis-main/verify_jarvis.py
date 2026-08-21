"""
JARVIS System Comprehensive Automated Verification Suite.
Validates all subsystems, APIs, database, voice engine, brain tools, and web server.
Includes explicit verification for all sample user commands.
"""

import json
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("jarvis.verify")

def test_environment():
    log.info("--- 1. Testing Environment Setup ---")
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
    assert env_path.is_file(), ".env file missing!"
    log.info("✓ Environment file .env exists")
    
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    eleven_key = os.environ.get("ELEVENLABS_API_KEY")
    log.info(f"✓ ANTHROPIC_API_KEY present: {bool(anthropic_key)}")
    log.info(f"✓ ELEVENLABS_API_KEY present: {bool(eleven_key)}")

def test_database():
    log.info("--- 2. Testing Database Operations (db.py) ---")
    import db
    
    tid = db.add_task("Verification Test Task", due_minutes=15)
    assert tid > 0, "Failed adding task to database"
    log.info(f"✓ Task added successfully with ID #{tid}")
    
    tasks = db.list_tasks(include_done=True)
    target = next((t for t in tasks if t["id"] == tid), None)
    assert target is not None, "Added task not found in list_tasks"
    assert target["due_relative"] is not None, "Relative due time formatting missing"
    log.info(f"✓ Task retrieved with formatted due time: {target['due_relative']}")
    
    ok_complete = db.complete_task(tid)
    assert ok_complete, "Failed to mark task complete"
    log.info("✓ Task marked complete successfully")
    
    ok_delete = db.delete_task(tid)
    assert ok_delete, "Failed to delete task"
    log.info("✓ Task deleted successfully")

def test_tts():
    log.info("--- 3. Testing Text-To-Speech (tts.py) ---")
    import tts
    ok_local = tts._speak_local_fallback("System test.")
    assert ok_local, "Local SAPI5 TTS fallback failed"
    log.info("✓ Local SAPI5 TTS fallback operational")

def test_stt():
    log.info("--- 4. Testing Speech-To-Text (stt.py) ---")
    import stt
    dev_idx = stt._resolve_device_idx()
    log.info(f"✓ Audio device index resolved: {dev_idx}")
    model = stt._get_model()
    assert model is not None, "Whisper model failed to load"
    log.info("✓ Whisper STT model loaded successfully")

def test_brain():
    log.info("--- 5. Testing Brain Intelligence & Tools (brain.py) ---")
    import brain
    
    user_commands = [
        ("Open YouTube.", ["Opened", "youtube"]),
        ("Open Spotify.", ["Launched", "spotify"]),
        ("Search YouTube for relaxing music.", ["Searching YouTube", "relaxing music"]),
        ("What is the weather today?", ["Weather", "skies"]),
        ("Tell me a joke.", ["programmer", "joke", "code", "bugs", "binary", "cache"]),
    ]

    for cmd, expected_keywords in user_commands:
        reply = brain.handle_command(cmd)
        assert any(k.lower() in reply.lower() for k in expected_keywords), f"Failed response for '{cmd}': {reply}"
        log.info(f"✓ '{cmd}' -> '{reply}'")

def test_server():
    log.info("--- 6. Testing Web Server API (server.py) ---")
    import server
    import threading
    
    test_port = 8899
    srv_thread = server.start_server_thread("127.0.0.1", test_port)
    time.sleep(1)
    
    try:
        # GET /api/status
        req = urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/status")
        status_data = json.loads(req.read().decode("utf-8"))
        assert status_data["status"] == "online", "API status failed"
        log.info(f"✓ GET /api/status -> online ({status_data['model']})")
        
        # GET /api/tasks
        req_tasks = urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/tasks")
        tasks_data = json.loads(req_tasks.read().decode("utf-8"))
        assert "tasks" in tasks_data, "API tasks failed"
        log.info("✓ GET /api/tasks -> operational")
        
        # POST /api/command with test command
        post_data = json.dumps({"command": "Search YouTube for relaxing music"}).encode("utf-8")
        post_req = urllib.request.Request(
            f"http://127.0.0.1:{test_port}/api/command",
            data=post_data,
            headers={"Content-Type": "application/json"}
        )
        cmd_res = json.loads(urllib.request.urlopen(post_req).read().decode("utf-8"))
        assert "reply" in cmd_res, "API command failed"
        log.info(f"✓ POST /api/command -> reply: '{cmd_res['reply']}'")
    finally:
        log.info("✓ API Server tests completed")

def run_all_tests():
    log.info("==================================================")
    log.info("   JARVIS AI SYSTEM — COMPREHENSIVE TEST SUITE   ")
    log.info("==================================================")
    test_environment()
    test_database()
    test_tts()
    test_stt()
    test_brain()
    test_server()
    log.info("==================================================")
    log.info("   ALL 6 SUBSYSTEM VERIFICATIONS PASSED! 100% OK  ")
    log.info("==================================================")

if __name__ == "__main__":
    run_all_tests()
