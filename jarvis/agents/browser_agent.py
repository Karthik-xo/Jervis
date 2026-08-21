"""
Autonomous Browser Agent for JARVIS AI OS.

Integrates Playwright-powered general browser automation:
  - Any website navigation & search
  - Multi-tab management (open, close, switch, list)
  - Natural page navigation (back, forward, refresh, scroll up/down/top/bottom)
  - DOM interaction (smart clicks, form filling, key pressing)
  - Webpage reading & AI-synthesized concise summarization
  - Full-page & viewport screenshot capture
  - File download handling
  - Permission-controlled Gmail / browser-based email workflows
  - YouTube search/playback delegation
  - Bilingual English & Tamil support
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from jarvis.core.config import SITE_ALIASES
from jarvis.services.language_service import Language, detect_language
from jarvis.services.permission_service import permission_manager, PermissionCategory

log = logging.getLogger("jarvis.browser_agent")


# ── Gmail / Email Handler ──────────────────────────────────────────────────

async def handle_email_workflow(text: str) -> str:
    """
    Handle email composition and sending requests with security confirmation.
    Example: 'send an email to John with subject Meeting and body See you tomorrow'
    """
    raw = text.strip()
    lang = detect_language(raw)
    lower = raw.lower()

    # Extract recipient (e.g., 'send email to john@example.com', 'email to Sarah', 'to: boss')
    recipient = ""
    to_m = re.search(r"\bto\s+([a-zA-Z0-9_\.\+-]+(?:@[a-zA-Z0-9-]+\.[a-zA-Z0-9-\.]+)?|[a-zA-Z]+)", raw, re.I)
    if to_m:
        candidate = to_m.group(1).strip()
        if candidate.lower() not in ("the", "a", "an", "send", "draft", "email", "mail"):
            recipient = candidate

    # Extract subject
    subject = ""
    subj_m = re.search(r"(?:with\s+)?subject\s+[\"']?([^\"'\n\r,]+)[\"']?", raw, re.I)
    if subj_m:
        subject = subj_m.group(1).strip()

    # Extract body / message
    body = ""
    body_m = re.search(r"(?:with\s+)?(?:body|message|saying)\s+[\"']?([^\"'\n\r]+)[\"']?", raw, re.I)
    if body_m:
        body = body_m.group(1).strip()

    if not recipient:
        if lang == Language.TAMIL:
            return "சார், இந்த மின்னஞ்சலை யாருக்கு அனுப்ப வேண்டும் என்று கூறுங்கள்."
        return "Sir, who would you like to send this email to? Please provide the recipient."

    # Draft the email in Gmail first
    from jarvis.automation.browser import open_gmail_compose, send_gmail_draft
    draft_result = await open_gmail_compose(recipient=recipient, subject=subject, body=body)

    if not draft_result.get("success"):
        err = draft_result.get("error", "Unknown error")
        return f"Sir, I opened Gmail, but could not complete the draft automatically ({err})."

    # Security check: Sending email is a sensitive action
    allowed, prompt = await permission_manager.request_action_permission(
        PermissionCategory.EMAIL_SEND,
        f"I have drafted an email to {recipient} with subject '{subject or '(no subject)'}'. Shall I send it now?",
        {"recipient": recipient, "subject": subject, "body": body},
    )

    if not allowed:
        return prompt

    # If already permitted or confirmed
    page = draft_result.get("page")
    sent = await send_gmail_draft(page)
    if sent:
        log.info("Email verified sent to %s", recipient)
        if lang == Language.TAMIL:
            return f"மின்னஞ்சல் {recipient} என்பவருக்கு வெற்றிகரமாக அனுப்பப்பட்டது, சார்."
        return f"Email sent successfully to {recipient}, Sir."
    else:
        log.warning("Email send could not be verified in browser DOM.")
        return f"Sir, the email to {recipient} was drafted, but I could not verify that it was sent. Please confirm in the open browser window."


# ── Webpage Reading & Summarization ────────────────────────────────────────

async def handle_summarize_page() -> str:
    """Extract readable text from current browser tab and summarize it with AI."""
    from jarvis.automation.browser import extract_article_content
    article = await extract_article_content()
    title = article.get("title", "this webpage")
    content = article.get("content", "")

    if not content or len(content) < 30:
        return "Sir, there is not enough readable text content on the active webpage to summarize."

    from jarvis.services.llm_service import chat
    prompt = (
        f"You are JARVIS. Summarize the key information from this webpage concisely for the user.\n"
        f"Page Title: {title}\n"
        f"Page Content:\n{content[:3000]}\n\n"
        "Instructions: Provide a clear, natural 2-3 sentence spoken summary. "
        "Do not read raw URLs, markdown formatting, or HTML tags aloud."
    )
    summary = await chat(prompt)
    return summary


# ── Master Browser Automation Dispatcher ───────────────────────────────────

async def handle_automation(text: str) -> str:
    """Handle general browser automation, search, tabs, forms, navigation, and reading."""
    raw = text.strip()
    lang = detect_language(raw)
    lower = raw.lower()

    # 1. YouTube Intent Delegation
    if any(w in lower for w in ["on youtube", "in youtube", "youtube search", "play youtube", "youtube-la", "யூடியூப்"]):
        from jarvis.agents.youtube_agent import handle_youtube
        return await handle_youtube(raw)

    # 2. Email / Gmail Workflow
    if any(w in lower for w in ["send email", "draft email", "send an email", "compose email", "mail anupu", "மின்னஞ்சல்"]):
        return await handle_email_workflow(raw)

    from jarvis.automation import browser

    # 3. Webpage Reading / Summarization
    if any(w in lower for w in [
        "summarize this page", "summarize webpage", "summarize website", "read this page",
        "what is on this page", "explain this page", "summarize this", "பக்கத்தை சுருக்கு",
    ]):
        return await handle_summarize_page()

    # 4. Webpage Screenshot
    if any(w in lower for w in ["screenshot of page", "webpage screenshot", "screenshot this site", "browser screenshot"]):
        try:
            path = await browser.screenshot()
            if lang == Language.TAMIL:
                return f"இணையப்பக்க ஸ்கிரீன்ஷாட் எடுக்கப்பட்டது, சார்: {path}"
            return f"Captured webpage screenshot, Sir: {path}"
        except Exception as exc:
            return f"Could not capture webpage screenshot: {exc}"

    # 5. Tab Management
    if "new tab" in lower or "open tab" in lower or "புதிய தாவல்" in lower:
        target_url = None
        for word in raw.split():
            if "." in word or word.startswith("http"):
                target_url = word
                break
        await browser.new_page(target_url)
        return "Opened a new tab, Sir."

    if "close tab" in lower or "close this tab" in lower or "தாவலை மூடு" in lower:
        res = await browser.close_page()
        return res

    switch_m = re.search(r"switch\s+(?:to\s+)?tab\s+(\d+|[a-zA-Z0-9_\.-]+)", lower)
    if switch_m:
        target_id = switch_m.group(1).strip()
        await browser.switch_tab(target_id)
        return f"Switched to tab '{target_id}', Sir."

    if any(w in lower for w in ["list tabs", "show tabs", "open tabs"]):
        tabs = await browser.list_tabs()
        if not tabs:
            return "No tabs currently open, Sir."
        tab_list = ", ".join(f"Tab {t['display_index']}: {t['title'][:30]}" for t in tabs[:5])
        return f"Active tabs: {tab_list}, Sir."

    # 6. Page Scrolling
    if any(w in lower for w in ["scroll down", "கீழே உருட்டு"]):
        return await browser.scroll(direction="down", amount=600)
    if any(w in lower for w in ["scroll up", "மேலே உருட்டு"]):
        return await browser.scroll(direction="up", amount=600)
    if any(w in lower for w in ["scroll to top", "scroll to the top", "go to top"]):
        return await browser.scroll(direction="top")
    if any(w in lower for w in ["scroll to bottom", "scroll to the bottom", "go to bottom"]):
        return await browser.scroll(direction="bottom")

    # 7. Navigation History
    if any(w in lower for w in ["go back", "previous page", "பின்செல்"]):
        return await browser.go_back()
    if any(w in lower for w in ["go forward", "next page", "முன்செல்"]):
        return await browser.go_forward()
    if any(w in lower for w in ["refresh page", "reload page", "refresh", "மீண்டும் ஏற்று"]):
        return await browser.reload_page()

    # 8. Clicks on Webpage
    click_m = re.search(r"click\s+(?:on\s+)?(?:the\s+)?[\"']?([^\"'\n\r]+)[\"']?", raw, re.I)
    if click_m and not any(w in lower for w in ["open", "go to", "search"]):
        target = click_m.group(1).strip()
        try:
            await browser.click(selector_or_text=target)
            return f"Clicked on '{target}', Sir."
        except Exception as exc:
            return f"Could not click '{target}', Sir: {exc}"

    # 9. Type or Fill Inputs
    fill_m = re.search(r"(?:type|enter|fill)\s+[\"']([^\"']+)[\"']\s+(?:in|into|as)\s+(?:the\s+)?[\"']?([^\"'\n\r]+)[\"']?", raw, re.I)
    if fill_m:
        val = fill_m.group(1).strip()
        field = fill_m.group(2).strip()
        try:
            await browser.fill(selector_or_label=field, value=val)
            return f"Filled '{val}' into {field}, Sir."
        except Exception as exc:
            return f"Could not fill '{field}', Sir: {exc}"

    # 10. Open Website + In-Site Action (Multi-Step)
    open_and = re.search(r"(?:open|go to)\s+(\w+[\.\w+]*)\s+and\s+(.+)", lower)
    if open_and:
        site = open_and.group(1).strip()
        action = open_and.group(2).strip()
        url = SITE_ALIASES.get(site, site if "." in site else f"https://{site}.com")
        try:
            page = await browser.new_page(url)
            await asyncio.sleep(2.0)

            # In-site search action
            if any(w in action for w in ["search", "find", "look for"]):
                search_q = re.sub(r"^(?:search|find|look)\s+(?:for\s+)?", "", action, flags=re.I).strip()
                res = await browser.search_in_page(page, search_q)
                return f"Opened {site} and searched for '{search_q}', Sir."

            # Summarize action
            if any(w in action for w in ["summarize", "explain", "read"]):
                return await handle_summarize_page()

            return f"Opened {site}, Sir. Action '{action}' requires specific target elements."
        except Exception as exc:
            log.warning("Multi-step browser action failed: %s", exc)
            return f"Opened {site}, Sir. Could not complete '{action}': {exc}"

    # 11. Google Search
    google_search_m = re.search(r"(?:search|google)\s+(?:for\s+)?(.+?)(?:\s+on\s+google|\s+in\s+google|\s+google-la)?$", raw, re.I)
    if google_search_m and any(k in lower for k in ["google", "search"]):
        query = google_search_m.group(1).strip()
        if query:
            try:
                await browser.search_google(query)
                return f"Searched Google for '{query}', Sir."
            except Exception as exc:
                return f"Google search error: {exc}"

    # 12. Direct URL or Site Opening
    open_url_m = re.search(r"^(?:open|go to|navigate to|திற)\s+(https?://\S+|\S+\.(?:com|org|net|io|ai|dev|gov|edu)|\w+)", raw, re.I)
    if open_url_m:
        target = open_url_m.group(1).strip()
        url = SITE_ALIASES.get(target.lower(), target)
        try:
            await browser.new_page(url)
            if lang == Language.TAMIL:
                return f"சரி சார், {target} திறக்கப்பட்டது."
            return f"Opened {target}, Sir."
        except Exception as exc:
            return f"Could not open {target}, Sir: {exc}"

    # Fallback to AI Brain to interpret complex natural language browser instructions
    from jarvis.services.llm_service import chat
    return await chat(raw)

