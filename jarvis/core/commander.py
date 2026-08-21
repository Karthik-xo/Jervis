"""
Central JARVIS Core / Commander.

The single central controller responsible for:
  - Intent classification (CHAT, SEARCH, RESEARCH, YOUTUBE, BROWSER, SYSTEM, CODING, TASK, MEMORY, VISION, CONVERSATION)
  - Bilingual understanding (English & Tamil)
  - Security & Permission checks
  - Routing work strictly to the designated agent
  - Context retention & session memory
  - Producing the final response to speak or display
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

from jarvis.core.event_bus import bus
from jarvis.core import memory
from jarvis.core.state_manager import state_manager, JarvisState
from jarvis.services.language_service import (
    Language,
    detect_language,
    normalize_for_intent,
    build_bilingual_response,
)

log = logging.getLogger("jarvis.commander")


class Intent(str, Enum):
    CHAT = "CHAT"
    SEARCH = "SEARCH"
    RESEARCH = "RESEARCH"
    YOUTUBE = "YOUTUBE"
    BROWSER = "BROWSER"
    SYSTEM = "SYSTEM"
    CODING = "CODING"
    TASK = "TASK"
    REMINDER = "REMINDER"
    MEMORY = "MEMORY"
    VISION = "VISION"
    CONVERSATION = "CONVERSATION"

    # Backward-compatibility aliases
    COMMAND = "SYSTEM"
    AUTOMATION = "BROWSER"


# ── Pattern tables ──────────────────────────────────────────────────────────

_CONVERSATION_START_PATTERNS = [
    re.compile(r"(?:let'?s\s+talk|start\s+conversation|start\s+chat|பேசலாம்|பேசு)", re.I),
]

_CONVERSATION_END_PATTERNS = [
    re.compile(r"(?:stop\s+conversation|go\s+to\s+standby|stop\s+talking|exit\s+chat|standby|பேச்சு\s+நிறுத்து|நிறுத்து)", re.I),
]

_EMAIL_PATTERNS = [
    re.compile(r"\b(?:send\s+(?:an\s+)?email|draft\s+(?:an\s+)?email|compose\s+(?:an\s+)?email|email\s+to\b|mail\s+anupu|மின்னஞ்சல்)\b", re.I),
]

_TASK_PATTERNS = [
    re.compile(r"(?:remind\s+me|add\s+task|create\s+task|new\s+task|set\s+reminder|add\s+reminder|டாஸ்க்|நினைவூட்டு)", re.I),
    re.compile(r"(?:list|show|view|check)\s+(?:my\s+)?(?:tasks?|reminders?|to-?do)", re.I),
    re.compile(r"(?:complete|finish|mark\s+done|done|முடிந்தது)\s+(?:task|#?\d+)", re.I),
    re.compile(r"(?:delete|remove|நீக்கு)\s+(?:task|#?\d+)", re.I),
]

_YOUTUBE_EXPLICIT_PATTERNS = [
    re.compile(r"(?:play|search|find|open|look\s+up)\s+(?:.+?\s+)?(?:on\s+youtube|in\s+youtube|youtube\s+for|யூடியூப்)", re.I),
    re.compile(r"(?:search|play|open|find)\s+youtube\b", re.I),
    re.compile(r"\byoutube\b\s+(?:search|play|open|video|song|for)", re.I),
    re.compile(r"^(?:open|play)\s+youtube\b", re.I),
    re.compile(r"^யூடியூப்\s+(?:திற|இயக்கு)", re.I),
    re.compile(r".+\s+(?:on\s+youtube|in\s+youtube)$", re.I),
]

_RESEARCH_PATTERNS = [
    re.compile(r"(?:search|google)\s+.+?\s+(?:and\s+)?(?:explain|summarize|tell\s+me)", re.I),
    re.compile(r"^(?:search|google|look up|search web|search for|research|தேடு|ஆராய்ச்சி)\b", re.I),
    re.compile(r"(?:latest|recent|current|today'?s?)\s+(?:news|updates|headlines|ai\s+news|weather|whether|scores?)", re.I),
    re.compile(r"^what (?:is|are|was|were) (?:the )?(?:latest|newest|current)", re.I),
    re.compile(r"\b(?:today\s+weather|weather\s+today|today\s+whether|what\s+is\s+the\s+weather)\b", re.I),
]

_CODING_PATTERNS = [
    re.compile(r"(?:code|python|javascript|react|bug|debug|function|api|refactor|error|fix\s+code|analyze\s+project|analyze\s+my\s+project|analyze\s+my\s+python\s+project|நிரல்|கோடிங்)", re.I),
    re.compile(r"(?:write\s+a\s+script|create\s+a\s+function|explain\s+this\s+code)", re.I),
]

_SYSTEM_PATTERNS = [
    re.compile(r"(?:take|capture)\s+(?:a\s+)?(?:screenshot|screen\s?shot|ஸ்கிரீன்ஷாட்)", re.I),
    re.compile(r"(?:system|device)\s+(?:info|status|stats?|health|diagnostics?|நிலைமை)", re.I),
    re.compile(r"(?:what time|current time|what date|what day|நேரம்|மணி)", re.I),
    re.compile(r"(?:battery|cpu|memory|ram|disk)\s*(?:usage|level|status|info)?", re.I),
    re.compile(r"(?:volume\s+(?:up|down|mute|unmute)|mute|unmute|சத்தம்)", re.I),
    re.compile(r"(?:lock\s+(?:pc|computer|screen|workstation)|shutdown|restart|reboot|பூட்டு)", re.I),
    re.compile(r"^(?:open|launch|start|close|quit|focus|go to)\s+(?:chrome|vs\s?code|cursor|antigravity|whatsapp|telegram|calculator|explorer|notepad|terminal|dashboard|settings)", re.I),
]

_BROWSER_PATTERNS = [
    re.compile(r"^(?:open|go to|navigate to|திற)\s+(?:https?://|www\.|\w+\.(?:com|org|net|io|ai|dev|gov|edu))", re.I),
    re.compile(r"^(?:open|go to)\s+(?:gmail|netflix|chatgpt|claude|spotify|linkedin|github|reddit|wikipedia|google)", re.I),
    re.compile(r"(?:open|go to)\s+\S+\s+and\s+(?:search|type|fill|click|draft|send|summarize)", re.I),
    re.compile(r"\b(?:new\s+tab|close\s+tab|switch\s+tab|list\s+tabs|next\s+tab|previous\s+tab|தாவல்)\b", re.I),
    re.compile(r"\b(?:scroll\s+down|scroll\s+up|scroll\s+to\s+top|scroll\s+to\s+bottom|refresh\s+page|reload\s+page|go\s+back|go\s+forward)\b", re.I),
    re.compile(r"\b(?:summarize\s+this\s+page|summarize\s+webpage|summarize\s+website|read\s+this\s+page|what\s+is\s+on\s+this\s+page|explain\s+this\s+page)\b", re.I),
    re.compile(r"\b(?:screenshot\s+(?:of\s+)?(?:page|webpage|site|browser))\b", re.I),
]

_YOUTUBE_GENERAL_PATTERNS = [
    re.compile(r"\b(?:play\s+song|play\s+music|play\s+video|play\s+track|பாடலை\s+இயக்கு|பாடல்\s+போடு)\b", re.I),
    re.compile(r"\b(?:play|song|songs|video|videos|பாடலை|பாடல்|பாடல்கள்|இயக்கு|போடு)\b", re.I),
]

_MEMORY_PATTERNS = [
    re.compile(r"(?:remember that|note that|save note|save preference|நினைவில்\s+வை)", re.I),
    re.compile(r"(?:what is my preference|list notes|recall note)", re.I),
]

_CHAT_PATTERNS = [
    re.compile(r"^(?:hi|hello|hey|greetings|good\s+(?:morning|evening|afternoon|night)|வணக்கம்|ஹலோ)\b", re.I),
    re.compile(r"^(?:how are you|what'?s up|who are you|what can you do|help|thank you|thanks|எப்படி இருக்கிறாய்)", re.I),
    re.compile(r"(?:tell me a joke|say something funny|make me laugh)", re.I),
]


# ── Classifier ─────────────────────────────────────────────────────────────

def classify(text: str) -> tuple[Intent, dict[str, Any]]:
    """Determine intent from user request."""
    t = text.strip()
    if not t:
        return Intent.CHAT, {}

    normalized = normalize_for_intent(t)
    lower = normalized.lower()

    # 1. Conversation Mode Start / End
    for pat in _CONVERSATION_START_PATTERNS:
        if pat.search(lower):
            return Intent.CONVERSATION, {"action": "start", "raw": t}
    for pat in _CONVERSATION_END_PATTERNS:
        if pat.search(lower):
            return Intent.CONVERSATION, {"action": "stop", "raw": t}

    # 2. Email Actions
    for pat in _EMAIL_PATTERNS:
        if pat.search(lower):
            return Intent.BROWSER, {"action": "email", "raw": t}

    # 3. Tasks & Reminders
    for pat in _TASK_PATTERNS:
        if pat.search(lower):
            return Intent.TASK, {"raw": t}

    # 4. Explicit YouTube Requests
    for pat in _YOUTUBE_EXPLICIT_PATTERNS:
        if pat.search(lower):
            return Intent.YOUTUBE, {"raw": t}

    # 5. Research / Web Search Intent
    for pat in _RESEARCH_PATTERNS:
        if pat.search(lower):
            query = pat.sub("", lower).strip() or t
            return Intent.RESEARCH, {"query": query, "raw": t}

    # 6. Coding Specialist Intent
    for pat in _CODING_PATTERNS:
        if pat.search(lower):
            return Intent.CODING, {"raw": t}

    # 7. System & Desktop Control Intent
    for pat in _SYSTEM_PATTERNS:
        if pat.search(lower):
            open_m = re.match(r"^(open|launch|start|close|focus|go to)\s+(.+)", lower)
            if open_m:
                return Intent.SYSTEM, {"action": open_m.group(1), "target": open_m.group(2).strip(), "raw": t}
            return Intent.SYSTEM, {"raw": t}

    # 8. Browser & Website Intent
    for pat in _BROWSER_PATTERNS:
        if pat.search(lower):
            open_m = re.match(r"^(open|go to|navigate to)\s+(.+)", lower)
            target = open_m.group(2).strip() if open_m else ""
            return Intent.BROWSER, {"action": "open", "target": target, "raw": t}

    # 9. General YouTube / Music Intent
    for pat in _YOUTUBE_GENERAL_PATTERNS:
        if pat.search(lower):
            return Intent.YOUTUBE, {"raw": t}

    # 10. Memory & Notes Intent
    for pat in _MEMORY_PATTERNS:
        if pat.search(lower):
            return Intent.MEMORY, {"raw": t}

    # 11. Conversational Chat Intent
    for pat in _CHAT_PATTERNS:
        if pat.search(lower):
            return Intent.CHAT, {"raw": t}

    # Default fallback
    return Intent.CHAT, {"raw": t}


# ── High-Level Commander Dispatch ──────────────────────────────────────────

async def dispatch(text: str) -> str:
    """Classify request, coordinate agent network, and return synthesized reply."""
    raw_text = text.strip()
    if not raw_text:
        return "I am listening, Sir."

    lang = detect_language(raw_text)
    intent, meta = classify(raw_text)

    log.info("Commander Intent: %s | Language: %s | Raw: '%s'", intent.value, lang.value, raw_text)
    await bus.emit("commander:intent", {"intent": intent.value, "language": lang.value, "text": raw_text})

    # Save to persistent history
    memory.add_history("user", raw_text)

    reply: str = ""

    # Route based on Intent
    if intent == Intent.CONVERSATION:
        action = meta.get("action", "start")
        if action == "start":
            state_manager.start_conversation()
            if lang == Language.TAMIL:
                reply = "நிச்சயமாக சார். நான் கேட்கிறேன், உரையாடலை தொடரலாம்."
            else:
                reply = "Certainly Sir. I'm listening. We can converse freely."
        else:
            state_manager.end_conversation()
            if lang == Language.TAMIL:
                reply = "சரி சார், ஸ்டாண்ட்பை மோடுக்கு மாறுகிறேன்."
            else:
                reply = "Understood Sir. Returning to silent standby."

    elif intent == Intent.YOUTUBE:
        from jarvis.agents.youtube_agent import handle_youtube
        reply = await handle_youtube(raw_text)

    elif intent == Intent.CODING:
        from jarvis.agents.coding_agent import handle_coding
        reply = await handle_coding(raw_text)

    elif intent == Intent.RESEARCH or intent == Intent.SEARCH:
        from jarvis.agents.research_agent import handle_search
        query = meta.get("query", raw_text)
        reply = await handle_search(query)

    elif intent == Intent.TASK or intent == Intent.REMINDER:
        from jarvis.agents.task_agent import handle_task
        reply = await handle_task(raw_text)

    elif intent == Intent.SYSTEM:
        from jarvis.agents.system_agent import handle_command, handle_system
        if "action" in meta and "target" in meta:
            reply = await handle_command(meta)
        else:
            reply = await handle_system(meta)

    elif intent == Intent.BROWSER:
        from jarvis.agents.browser_agent import handle_automation
        reply = await handle_automation(raw_text)

    elif intent == Intent.MEMORY:
        from jarvis.agents.memory_agent import store_note, list_notes
        if "list" in raw_text.lower():
            reply = await list_notes()
        else:
            reply = await store_note(raw_text)

    else:  # CHAT
        from jarvis.services.llm_service import chat
        reply = await chat(raw_text)

    # Log action & save assistant response
    memory.add_history("assistant", reply)
    memory.log_action(intent.value)
    await bus.emit("commander:reply", {"intent": intent.value, "reply": reply})

    return reply
