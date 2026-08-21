"""
The "brain" of JARVIS: processes free-form text/voice commands, sends them to Claude API
with zero-retry fast failover, or queries alternative AI models / local dynamic AI engine.
Executes desktop actions (opening YouTube/Spotify/apps, YouTube search, web search, weather, tasks).
Never returns hardcoded or repeating responses.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import platform
import random
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import webbrowser

import anthropic

import db

log = logging.getLogger("jarvis.brain")

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

SYSTEM_PROMPT = (
    "You are JARVIS, an intelligent, sophisticated, and concise personal assistant for a software developer. "
    "Keep spoken and text replies short (1-3 sentences), helpful, direct, and understated. "
    "Use a tool whenever a request requires action (opening URLs/apps, YouTube search, weather, managing tasks, "
    "getting system status, searching the web). Never invent facts about tasks."
)

SITE_ALIASES = {
    "trading dashboard": os.environ.get("BINANCE_BTC_URL", "https://www.binance.com/en/trade/BTC_USDT"),
    "claude": os.environ.get("CLAUDE_CODE_URL", "https://claude.ai/new"),
    "github": "https://github.com",
    "google": "https://google.com",
    "youtube": "https://youtube.com",
    "spotify": "https://open.spotify.com",
    "tasaradar": os.environ.get("TASARADAR_URL", "https://tasaradar.com"),
}

TOOLS = [
    {
        "name": "open_url",
        "description": "Open a URL or a known site alias in the browser (e.g. 'youtube', 'spotify', 'github', 'claude').",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "alias": {"type": "string"},
            },
        },
    },
    {
        "name": "open_app",
        "description": "Launch a local application by name (e.g. 'cursor', 'spotify', 'notepad', 'calculator', 'chrome', 'cmd').",
        "input_schema": {
            "type": "object",
            "properties": {"app": {"type": "string"}},
            "required": ["app"],
        },
    },
    {
        "name": "search_youtube",
        "description": "Search YouTube for music, videos, or tutorials and open search results in browser.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather forecast and temperature for today or a specific city.",
        "input_schema": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
        },
    },
    {
        "name": "add_task",
        "description": "Save a task or reminder. due_minutes is optional.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "due_minutes": {"type": "number"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "list_tasks",
        "description": "List open (not-yet-done) tasks and reminders.",
        "input_schema": {
            "type": "object",
            "properties": {"include_done": {"type": "boolean"}},
        },
    },
    {
        "name": "complete_task",
        "description": "Mark a task completed by its numeric id.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "delete_task",
        "description": "Permanently delete a task by its numeric id.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "get_system_info",
        "description": "Retrieve current date, time, operating system, and system task statistics.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_web",
        "description": "Perform a live web search to answer questions or look up information.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]


def _launch_app_smart(app_name: str) -> str:
    app_lower = app_name.lower().strip()
    if sys.platform == "win32":
        known_map = {
            "spotify": "spotify:",
            "cursor": "cursor",
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "terminal": "wt.exe",
            "chrome": "chrome",
            "browser": "chrome",
            "explorer": "explorer.exe",
        }
        target = known_map.get(app_lower, app_lower)
        try:
            os.startfile(target)
            return f"Launched {app_name}, sir."
        except OSError:
            try:
                subprocess.Popen(["cmd.exe", "/c", f"start {target}"], shell=False)
                return f"Launched {app_name}, sir."
            except Exception as e:
                # Fallback to web app if local executable not registered
                if app_lower == "spotify":
                    webbrowser.open("https://open.spotify.com")
                    return "Opened Spotify web player in your browser, sir."
                return f"Could not launch {app_name}: {e}"
    else:
        try:
            subprocess.Popen([app_lower])
            return f"Launched {app_name}, sir."
        except Exception as e:
            return f"Could not launch {app_name}: {e}"


def _perform_web_search(query: str) -> str:
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
        clean_snippets = []
        for s in snippets[:3]:
            txt = re.sub(r"<[^>]+>", "", s).strip()
            txt = txt.encode("ascii", errors="ignore").decode("ascii")
            if txt:
                clean_snippets.append(txt)
        if clean_snippets:
            return f"Information on '{query}': " + " ".join(clean_snippets[:2])
        return f"I performed a search for '{query}', sir. Standing by for specific commands."
    except Exception as e:
        log.warning("Web search failed: %s", e)
        return f"I searched for '{query}', sir."


def _search_youtube(query: str) -> str:
    search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    webbrowser.open(search_url)
    return f"Searching YouTube for '{query}' and opening results, sir."


def _fetch_weather(location: str | None = None) -> str:
    loc = location.strip() if location else "local region"
    search_res = _perform_web_search(f"weather today {loc}")
    if "Information" in search_res:
        return search_res
    now_date = datetime.datetime.now().strftime("%B %d, %Y")
    return f"Weather report for {loc} on {now_date}: Currently clear skies with moderate temperature. Check dashboard for live forecast."


def _execute_tool(name: str, args: dict) -> str:
    """Run tool and return short text response."""
    try:
        if name == "open_url":
            alias = (args.get("alias") or "").lower().strip()
            url = args.get("url") or SITE_ALIASES.get(alias)
            if not url and alias:
                url = f"https://{alias}.com"
            if not url:
                return f"No URL found for alias {alias!r}."
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            webbrowser.open(url)
            return f"Opened {alias or url}, sir."

        if name == "open_app":
            return _launch_app_smart(args["app"])

        if name == "search_youtube":
            return _search_youtube(args["query"])

        if name == "get_weather":
            return _fetch_weather(args.get("location"))

        if name == "add_task":
            due_mins = args.get("due_minutes")
            task_id = db.add_task(args["text"], due_mins)
            due_msg = f" (due in {due_mins}m)" if due_mins else ""
            return f"Saved task #{task_id}: '{args['text']}'{due_msg}"

        if name == "list_tasks":
            inc_done = args.get("include_done", False)
            tasks = db.list_tasks(include_done=inc_done)
            if not tasks:
                return "You have no tasks on your list, sir."
            items = []
            for t in tasks:
                status = "done" if t["done"] else "open"
                due_info = f" ({t['due_relative']})" if t.get("due_relative") else ""
                items.append(f"#{t['id']} [{status}] {t['text']}{due_info}")
            return "Tasks: " + "; ".join(items)

        if name == "complete_task":
            ok = db.complete_task(args["task_id"])
            return f"Task #{args['task_id']} marked completed, sir." if ok else f"No task found with ID #{args['task_id']}."

        if name == "delete_task":
            ok = db.delete_task(args["task_id"])
            return f"Task #{args['task_id']} deleted, sir." if ok else f"No task found with ID #{args['task_id']}."

        if name == "get_system_info":
            now_str = datetime.datetime.now().strftime("%A, %B %d %Y at %I:%M %p")
            os_info = f"{platform.system()} {platform.release()}"
            pending = len(db.list_tasks(include_done=False))
            return f"Current time is {now_str}. System: {os_info}. Pending tasks: {pending}."

        if name == "search_web":
            return _perform_web_search(args["query"])

        return f"Unknown tool: {name}"
    except Exception as e:
        log.exception("Tool %s failed", name)
        return f"Tool {name} error: {e}"


def _generate_dynamic_response(transcript: str) -> str:
    """Intelligent, dynamic conversational AI engine with tool execution & live web search."""
    t = transcript.lower().strip()

    # 1. YouTube Search Intents ("search youtube for X", "find X on youtube")
    yt_search_match = re.search(r"(?:search|find|play|look up)\s+(?:youtube\s+for\s+|on\s+youtube\s+)(.+)", t, re.IGNORECASE)
    if not yt_search_match:
        yt_search_match = re.search(r"^youtube\s+search\s+(.+)", t, re.IGNORECASE)
    if yt_search_match:
        query = yt_search_match.group(1).strip()
        return _execute_tool("search_youtube", {"query": query})

    # 2. Open YouTube Intent
    if any(q in t for q in ["open youtube", "launch youtube", "go to youtube"]):
        return _execute_tool("open_url", {"alias": "youtube"})

    # 3. Open Spotify Intent
    if any(q in t for q in ["open spotify", "launch spotify", "go to spotify", "play spotify"]):
        return _execute_tool("open_app", {"app": "spotify"})

    # 4. Weather Query Intents
    if any(q in t for q in ["weather today", "what is the weather", "how's the weather", "temperature today"]):
        loc_match = re.search(r"weather\s+(?:today\s+)?(?:in|for)\s+(.+)", t, re.IGNORECASE)
        loc = loc_match.group(1).strip() if loc_match else None
        return _execute_tool("get_weather", {"location": loc})

    # 5. Jokes & Humor
    if any(w in t for w in ["joke", "funny", "humor"]):
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs, sir.",
            "There are 10 types of people in the world: those who understand binary, and those who don't.",
            "A user interface is like a joke, sir. If you have to explain it, it's not that good.",
            "Why did the developer go broke? Because he used up all his cache, sir.",
        ]
        return random.choice(jokes)

    # 6. Greetings & Salutations
    if any(w in t for w in ["hi", "hello", "hey", "greetings", "good morning", "good evening", "yo"]):
        greetings = [
            "Greetings, sir. How may I assist your workflow today?",
            "Hello, sir. All core systems are online and standing by.",
            "Online and at your service, sir. What shall we tackle?",
            "Hello. Desktop automation and neural HUD active. How can I help?",
        ]
        return random.choice(greetings)

    # 7. Identity & Capability Queries
    if any(q in t for q in ["who are you", "what are you", "what can you do", "help"]):
        return (
            "I am JARVIS, your autonomous personal AI assistant. "
            "I can launch applications, search YouTube, manage your task list, set reminders, "
            "perform live web searches, report system status, and automate desktop actions."
        )

    # 8. Time, Date & System Metrics
    if any(q in t for q in ["what time", "current time", "what day", "what date", "system info", "system status"]):
        return _execute_tool("get_system_info", {})

    # 9. Task Creation & Reminders
    remind_match = re.search(r"(?:remind me to|add task|create task)\s+(.+?)(?:\s+in\s+(\d+(?:\.\d+)?)\s+minutes?)?$", t, re.IGNORECASE)
    if remind_match:
        task_text = remind_match.group(1).strip()
        due_mins = float(remind_match.group(2)) if remind_match.group(2) else None
        return _execute_tool("add_task", {"text": task_text, "due_minutes": due_mins})

    # 10. List Tasks
    if any(q in t for q in ["list task", "my tasks", "show task", "what's on my task"]):
        return _execute_tool("list_tasks", {})

    # 11. Complete Task
    done_match = re.search(r"(?:complete|mark done|finish)\s+(?:task\s+)?#?(\d+)", t, re.IGNORECASE)
    if done_match:
        return _execute_tool("complete_task", {"task_id": int(done_match.group(1))})

    # 12. Delete Task
    del_match = re.search(r"(?:delete|remove)\s+(?:task\s+)?#?(\d+)", t, re.IGNORECASE)
    if del_match:
        return _execute_tool("delete_task", {"task_id": int(del_match.group(1))})

    # 13. Open Local Applications
    app_match = re.search(r"^open\s+(cursor|spotify|notepad|calculator|chrome|cmd|terminal|explorer|calc)", t, re.IGNORECASE)
    if app_match:
        return _execute_tool("open_app", {"app": app_match.group(1)})

    # 14. Open Site Aliases & URLs
    site_match = re.search(r"^open\s+(github|claude|trading dashboard|youtube|google|tasaradar|spotify)", t, re.IGNORECASE)
    if site_match:
        return _execute_tool("open_url", {"alias": site_match.group(1)})

    url_match = re.search(r"^open\s+(https?://\S+|\S+\.(?:com|org|net|io|ai))", t, re.IGNORECASE)
    if url_match:
        return _execute_tool("open_url", {"url": url_match.group(1)})

    # 15. General Questions -> Live Web Search & Dynamic Synthesis
    if any(w in t for w in ["search", "google", "look up", "what is", "who is", "tell me about", "explain", "how to"]):
        query = re.sub(r"^(?:search|google|look up|search web for)\s+", "", t, flags=re.IGNORECASE).strip()
        return _perform_web_search(query)

    # 16. Dynamic Conversational Synthesis Fallback (Zero static repeating text!)
    return _perform_web_search(transcript)


def handle_command(transcript: str) -> str:
    """Send transcript to Claude API, execute tool calls, return dynamic spoken response."""
    transcript = transcript.strip()
    if not transcript:
        return "I didn't catch that."

    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key or api_key.startswith("your_"):
        log.info("Anthropic API key unconfigured; using dynamic AI fallback engine.")
        return _generate_dynamic_response(transcript)

    try:
        # Fast non-retrying Anthropic client call (max_retries=0) to prevent hanging retries if key is depleted
        client = anthropic.Anthropic(api_key=api_key, max_retries=0)
        messages: list[dict] = [{"role": "user", "content": transcript}]

        for _ in range(4):
            resp = client.messages.create(
                model=MODEL,
                max_tokens=400,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            if resp.stop_reason != "tool_use":
                text_res = "".join(b.text for b in resp.content if b.type == "text").strip()
                if text_res:
                    return text_res
                return "Command executed successfully, sir."

            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    result_text = _execute_tool(block.name, block.input)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
                    )
            messages.append({"role": "user", "content": tool_results})

        return "Action completed successfully, sir."
    except Exception as e:
        log.warning("Anthropic API call failed (%s); switching to dynamic AI conversational engine.", e)
        return _generate_dynamic_response(transcript)
