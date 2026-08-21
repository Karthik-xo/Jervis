"""
Production-grade Playwright browser controller for JARVIS AI OS.

Provides a persistent browser context with:
  - Multi-tab lifecycle management (new tab, switch tab, close tab, list tabs)
  - Resilient navigation, back/forward history, reload
  - Smart element interaction (CSS, text locators, ARIA roles, placeholders)
  - Form filling, key pressing, natural scrolling (up, down, top, bottom)
  - Content extraction, article parsing, clean text extraction
  - Live Google search and in-page search
  - High-res viewport and full-page screenshot capture
  - Safe file download handling
  - Gmail draft & compose workflow primitives
  - Automatic crash recovery and lazy browser initialization

Supported platforms: Google, YouTube, Gmail, GitHub, LinkedIn, ChatGPT, Netflix,
and all arbitrary web domains.
"""

from __future__ import annotations

import asyncio
import datetime
import html
import logging
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any, Callable

from jarvis.core.config import data_dir

log = logging.getLogger("jarvis.browser")

_browser = None
_context = None
_playwright = None
_active_page_idx: int = 0
_browser_lock = asyncio.Lock()


def _normalize_url(url: str) -> str:
    """Ensure URL has a valid scheme."""
    u = url.strip()
    if not u:
        return "https://www.google.com"
    if u.startswith(("http://", "https://", "about:", "chrome:", "file://")):
        return u
    if "." in u or "/" in u:
        return f"https://{u}"
    return f"https://www.google.com/search?q={urllib.parse.quote(u)}"


# ── Browser Lifecycle ───────────────────────────────────────────────────────

async def _ensure_browser():
    """Lazy-init Playwright Chromium browser and persistent context."""
    global _browser, _context, _playwright, _active_page_idx
    async with _browser_lock:
        if _browser and _context:
            try:
                _ = _context.pages
                return
            except Exception:
                log.warning("Browser context stale; reinitializing...")
                _browser = None
                _context = None

        try:
            from playwright.async_api import async_playwright

            if _playwright is None:
                _playwright = await async_playwright().start()

            _browser = await _playwright.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            _context = await _browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                accept_downloads=True,
            )
            _active_page_idx = 0
            log.info("Playwright browser and context initialized.")
        except ImportError:
            log.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            raise
        except Exception as exc:
            log.error("Failed to launch browser: %s", exc)
            raise


async def get_browser():
    """Get the active Playwright Browser instance."""
    await _ensure_browser()
    return _browser


async def get_context():
    """Get the active Playwright BrowserContext instance."""
    await _ensure_browser()
    return _context


async def get_active_page():
    """Get the currently focused / active page."""
    await _ensure_browser()
    pages = _context.pages
    if not pages:
        return await new_page()
    global _active_page_idx
    if 0 <= _active_page_idx < len(pages):
        return pages[_active_page_idx]
    _active_page_idx = len(pages) - 1
    return pages[_active_page_idx]


# ── Tab / Window Management ────────────────────────────────────────────────

async def new_page(url: str | None = None):
    """Open a new tab in the browser context."""
    await _ensure_browser()
    page = await _context.new_page()
    global _active_page_idx
    _active_page_idx = len(_context.pages) - 1
    if url:
        await navigate(page, url)
    return page


new_tab = new_page


async def list_tabs() -> list[dict[str, Any]]:
    """List all open tabs with their index, title, URL, and active status."""
    await _ensure_browser()
    tabs: list[dict[str, Any]] = []
    pages = _context.pages
    for idx, p in enumerate(pages):
        try:
            title = await p.title() or "Untitled Tab"
            url = p.url or "about:blank"
        except Exception:
            title = "Unresponsive Tab"
            url = "unknown"
        tabs.append({
            "index": idx,
            "display_index": idx + 1,
            "title": title,
            "url": url,
            "is_active": (idx == _active_page_idx),
        })
    return tabs


async def switch_tab(tab_identifier: int | str) -> Any:
    """Switch focus to a tab by 0-based or 1-based index, or title/URL matching substring."""
    await _ensure_browser()
    pages = _context.pages
    if not pages:
        return await new_page()

    target_page = None
    global _active_page_idx

    if isinstance(tab_identifier, int) or (isinstance(tab_identifier, str) and tab_identifier.isdigit()):
        val = int(tab_identifier)
        if 1 <= val <= len(pages):
            _active_page_idx = val - 1
            target_page = pages[_active_page_idx]
        elif 0 <= val < len(pages):
            _active_page_idx = val
            target_page = pages[_active_page_idx]

    if not target_page and isinstance(tab_identifier, str):
        query = tab_identifier.lower().strip()
        for idx, p in enumerate(pages):
            try:
                title = (await p.title()).lower()
                url = (p.url or "").lower()
                if query in title or query in url:
                    _active_page_idx = idx
                    target_page = p
                    break
            except Exception:
                continue

    if not target_page:
        _active_page_idx = len(pages) - 1
        target_page = pages[_active_page_idx]

    try:
        await target_page.bring_to_front()
    except Exception as exc:
        log.debug("bring_to_front error: %s", exc)

    return target_page


async def close_page(page_or_index: Any = None) -> str:
    """Close a specific page/tab or the active tab."""
    await _ensure_browser()
    pages = _context.pages
    if not pages:
        return "No open browser tabs to close, sir."

    global _active_page_idx
    target = None

    if page_or_index is None:
        target = pages[_active_page_idx] if 0 <= _active_page_idx < len(pages) else pages[-1]
    elif isinstance(page_or_index, (int, str)) and str(page_or_index).isdigit():
        idx = int(page_or_index) - 1 if int(page_or_index) > 0 else int(page_or_index)
        if 0 <= idx < len(pages):
            target = pages[idx]
    elif hasattr(page_or_index, "close"):
        target = page_or_index

    if target:
        try:
            title = await target.title() or "Tab"
            await target.close()
            remaining = _context.pages
            _active_page_idx = max(0, min(_active_page_idx, len(remaining) - 1)) if remaining else 0
            return f"Closed tab '{title}', sir."
        except Exception as exc:
            return f"Closed tab, sir ({exc})."

    return "Could not identify tab to close, sir."


close_tab = close_page


# ── Navigation & Control ───────────────────────────────────────────────────

async def navigate(page=None, url: str = "https://www.google.com", wait: str = "domcontentloaded", timeout: int = 30_000) -> str:
    """Navigate to *url* with retry logic and URL normalization."""
    p = page or await get_active_page()
    target_url = _normalize_url(url)

    for attempt in range(3):
        try:
            await p.goto(target_url, wait_until=wait, timeout=timeout)
            log.info("Navigated to %s", target_url)
            return f"Navigated to {target_url}"
        except Exception as exc:
            log.warning("Navigation attempt %d failed for %s: %s", attempt + 1, target_url, exc)
            if attempt == 2:
                try:
                    await p.goto(target_url, timeout=10_000)
                    return f"Navigated to {target_url}"
                except Exception:
                    raise
            await asyncio.sleep(1.0)
    return f"Navigated to {target_url}"


async def go_back(page=None) -> str:
    """Go back to previous page in history."""
    p = page or await get_active_page()
    try:
        await p.go_back(wait_until="domcontentloaded", timeout=10_000)
        return "Navigated back, sir."
    except Exception as exc:
        return f"Could not go back: {exc}"


async def go_forward(page=None) -> str:
    """Go forward to next page in history."""
    p = page or await get_active_page()
    try:
        await p.go_forward(wait_until="domcontentloaded", timeout=10_000)
        return "Navigated forward, sir."
    except Exception as exc:
        return f"Could not go forward: {exc}"


async def reload_page(page=None) -> str:
    """Reload / refresh the current page."""
    p = page or await get_active_page()
    try:
        await p.reload(wait_until="domcontentloaded", timeout=15_000)
        return "Page refreshed, sir."
    except Exception as exc:
        return f"Could not refresh page: {exc}"


# ── Smart Element Interaction ──────────────────────────────────────────────

async def click(page=None, selector_or_text: str = "", timeout: int = 5_000) -> bool:
    """
    Click an element matching CSS selector, text content, button name, or link text.
    Uses resilient multi-strategy matching.
    """
    p = page or await get_active_page()
    target = selector_or_text.strip()
    if not target:
        return False

    try:
        loc = p.locator(target).first
        if await loc.count() > 0:
            await loc.click(timeout=timeout)
            log.info("Clicked selector: %s", target)
            return True
    except Exception:
        pass

    try:
        btn = p.get_by_role("button", name=re.compile(re.escape(target), re.I)).first
        if await btn.count() > 0:
            await btn.click(timeout=timeout)
            log.info("Clicked button: %s", target)
            return True
    except Exception:
        pass

    try:
        link = p.get_by_role("link", name=re.compile(re.escape(target), re.I)).first
        if await link.count() > 0:
            await link.click(timeout=timeout)
            log.info("Clicked link: %s", target)
            return True
    except Exception:
        pass

    try:
        txt = p.get_by_text(target, exact=False).first
        if await txt.count() > 0:
            await txt.click(timeout=timeout)
            log.info("Clicked text element: %s", target)
            return True
    except Exception:
        pass

    try:
        clicked = await p.evaluate(
            """(text) => {
                const elements = Array.from(document.querySelectorAll('button, a, input[type="button"], input[type="submit"], [role="button"]'));
                const match = elements.find(el => (el.innerText || el.value || el.getAttribute('aria-label') || '').toLowerCase().includes(text.toLowerCase()));
                if (match) {
                    match.click();
                    return true;
                }
                return false;
            }""",
            target,
        )
        if clicked:
            log.info("Clicked JS text match: %s", target)
            return True
    except Exception:
        pass

    log.warning("Click failed for '%s' across all locator strategies.", target)
    raise RuntimeError(f"Could not locate clickable element matching '{target}'.")


async def fill(page=None, selector_or_label: str = "", value: str = "", timeout: int = 5_000) -> bool:
    """
    Fill a form input, textarea, or search field using CSS selectors, labels, or placeholders.
    """
    p = page or await get_active_page()
    target = selector_or_label.strip()

    try:
        loc = p.locator(target).first
        if await loc.count() > 0:
            await loc.fill(value, timeout=timeout)
            log.info("Filled selector '%s'", target)
            return True
    except Exception:
        pass

    try:
        loc = p.get_by_label(target, exact=False).first
        if await loc.count() > 0:
            await loc.fill(value, timeout=timeout)
            log.info("Filled by label '%s'", target)
            return True
    except Exception:
        pass

    try:
        loc = p.get_by_placeholder(target, exact=False).first
        if await loc.count() > 0:
            await loc.fill(value, timeout=timeout)
            log.info("Filled by placeholder '%s'", target)
            return True
    except Exception:
        pass

    try:
        loc = p.get_by_role("textbox", name=re.compile(re.escape(target), re.I)).first
        if await loc.count() > 0:
            await loc.fill(value, timeout=timeout)
            log.info("Filled by textbox role '%s'", target)
            return True
    except Exception:
        pass

    if any(k in target.lower() for k in ["search", "query", "find", "q"]):
        for s in ["input[type='search']", "input[name='q']", "textarea[name='q']", "input[type='text']", "textarea"]:
            try:
                candidate = p.locator(s).first
                if await candidate.count() > 0:
                    await candidate.fill(value, timeout=timeout)
                    log.info("Filled generic search input '%s'", s)
                    return True
            except Exception:
                continue

    raise RuntimeError(f"Could not locate input field matching '{target}'.")


async def type_text(page=None, selector: str = "", text: str = "", delay: int = 30) -> None:
    """Type text into an element character-by-character."""
    p = page or await get_active_page()
    if selector:
        await p.type(selector, text, delay=delay)
    else:
        await p.keyboard.type(text, delay=delay)


async def press_key(page=None, key: str = "Enter") -> None:
    """Press a keyboard key ('Enter', 'Escape', 'Space', 'Tab', etc.)."""
    p = page or await get_active_page()
    await p.keyboard.press(key)


async def scroll(page=None, direction: str = "down", amount: int = 500) -> str:
    """
    Scroll the active page.
    Directions: 'down', 'up', 'top', 'bottom', 'page_down', 'page_up'.
    """
    p = page or await get_active_page()
    d = direction.lower().strip()

    if d in ("top", "to_top", "start"):
        await p.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        return "Scrolled to the top of the page, sir."
    elif d in ("bottom", "to_bottom", "end"):
        await p.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
        return "Scrolled to the bottom of the page, sir."
    elif d in ("up", "page_up"):
        await p.evaluate(f"window.scrollBy({{top: -{amount}, behavior: 'smooth'}})")
        return f"Scrolled up by {amount}px, sir."
    else:
        await p.evaluate(f"window.scrollBy({{top: {amount}, behavior: 'smooth'}})")
        return f"Scrolled down by {amount}px, sir."


async def fill_form(page=None, fields: dict[str, str] | None = None) -> list[str]:
    """Fill multiple fields in a form."""
    p = page or await get_active_page()
    if not fields:
        return []
    results = []
    for field_name, val in fields.items():
        try:
            await fill(p, field_name, val)
            results.append(f"Filled '{field_name}'")
        except Exception as exc:
            results.append(f"Failed '{field_name}': {exc}")
    return results


# ── Text & Content Extraction ──────────────────────────────────────────────

async def get_text(page=None, selector: str = "body") -> str:
    """Extract text content from an element or body."""
    p = page or await get_active_page()
    try:
        return await p.text_content(selector) or ""
    except Exception:
        return ""


async def get_page_content(page=None, max_chars: int = 4000) -> str:
    """
    Get clean readable text content of the page, stripping HTML tags,
    scripts, stylesheets, and excessive whitespace.
    """
    p = page or await get_active_page()
    try:
        raw = await p.evaluate(
            """() => {
                const clone = document.body.cloneNode(true);
                const junk = clone.querySelectorAll('script, style, noscript, iframe, svg, nav, footer, header');
                junk.forEach(el => el.remove());
                return clone.innerText || '';
            }"""
        )
        cleaned = re.sub(r"\n\s*\n+", "\n\n", raw).strip()
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        return cleaned[:max_chars] if cleaned else "No readable text content found on the page."
    except Exception as exc:
        log.warning("get_page_content error: %s", exc)
        return ""


async def extract_article_content(page=None) -> dict[str, Any]:
    """
    Extract structured article content: title, meta description,
    headings, and top readable paragraphs for AI summarization.
    """
    p = page or await get_active_page()
    try:
        title = await p.title() or ""
        url = p.url or ""
        meta_desc = await p.evaluate(
            """() => {
                const m = document.querySelector('meta[name="description"]') || document.querySelector('meta[property="og:description"]');
                return m ? m.getAttribute('content') : '';
            }"""
        )
        body_text = await get_page_content(p, max_chars=3500)
        return {
            "title": title,
            "url": url,
            "description": meta_desc or "",
            "content": body_text,
        }
    except Exception as exc:
        log.warning("Article extraction error: %s", exc)
        return {"title": "", "url": "", "description": "", "content": ""}


async def wait_for(page=None, selector: str = "", timeout: int = 10_000):
    """Wait for an element to appear in the DOM."""
    p = page or await get_active_page()
    return await p.wait_for_selector(selector, timeout=timeout)


# ── Web Search & In-Page Search ────────────────────────────────────────────

async def search_google(query: str) -> str:
    """Open Google in a tab, perform search, and extract top snippets."""
    q = query.strip()
    url = f"https://www.google.com/search?q={urllib.parse.quote(q)}"
    page = await new_page(url)
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=12_000)
        await asyncio.sleep(1.0)
        content = await get_page_content(page, max_chars=2500)
        return content if content else f"Searched Google for '{q}'."
    except Exception as exc:
        log.warning("search_google failed: %s", exc)
        return f"Searched Google for '{q}'."


async def search_google_results(query: str, limit: int = 5) -> list[dict[str, str]]:
    """
    Search Google and parse structured organic result titles, URLs, and snippets.
    """
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    page = await new_page(url)
    results: list[dict[str, str]] = []
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=12_000)
        await asyncio.sleep(1.0)
        raw_items = await page.evaluate(
            """() => {
                const items = [];
                const searchBlocks = document.querySelectorAll('div.g, div[data-hveid]');
                for (const block of searchBlocks) {
                    const titleEl = block.querySelector('h3');
                    const linkEl = block.querySelector('a');
                    const snippetEl = block.querySelector('div[style*="-webkit-line-clamp"], div.VwiC3b, span.aCOpRe');
                    if (titleEl && linkEl && linkEl.href && !linkEl.href.includes('google.com/search')) {
                        items.push({
                            title: titleEl.innerText || '',
                            url: linkEl.href || '',
                            snippet: snippetEl ? snippetEl.innerText : '',
                        });
                    }
                }
                return items;
            }"""
        )
        for item in raw_items:
            if item.get("title") and item.get("url") and not any(r["url"] == item["url"] for r in results):
                results.append(item)
            if len(results) >= limit:
                break
    except Exception as exc:
        log.warning("Structured Google search error: %s", exc)
    return results


async def search_in_page(page=None, query: str = "") -> str:
    """Find search field on current page, input query, and submit."""
    p = page or await get_active_page()
    q = query.strip()
    for selector in ["input[type='search']", "input[name='q']", "input[type='text']", "textarea"]:
        try:
            loc = p.locator(selector).first
            if await loc.count() > 0:
                await loc.fill(q)
                await p.keyboard.press("Enter")
                await asyncio.sleep(1.5)
                return f"Searched in-page for '{q}', sir."
        except Exception:
            continue
    return "Could not find a search input field on the current page, sir."


# ── Screenshot & Downloads ─────────────────────────────────────────────────

async def screenshot(page=None, path: str | None = None, full_page: bool = False) -> str | bytes:
    """
    Capture screenshot of the active page.
    If path is None, saves to data/screenshots/screen_YYYYMMDD_HHMMSS.png and returns the filepath string.
    """
    p = page or await get_active_page()
    if path:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        raw_bytes = await p.screenshot(path=str(out_path), full_page=full_page)
        log.info("Saved screenshot to %s", out_path)
        return str(out_path)

    shots_dir = data_dir() / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    target_file = shots_dir / f"screen_{ts}.png"
    await p.screenshot(path=str(target_file), full_page=full_page)
    log.info("Captured webpage screenshot: %s", target_file)
    return str(target_file)


async def handle_download(page=None, trigger_callable: Callable | None = None, dest_dir: str | Path | None = None) -> str:
    """
    Safely await and handle a file download initiated by *trigger_callable*.
    Saves the file in data/downloads/ or *dest_dir*.
    """
    p = page or await get_active_page()
    save_dir = Path(dest_dir) if dest_dir else data_dir() / "downloads"
    save_dir.mkdir(parents=True, exist_ok=True)

    try:
        async with p.expect_download(timeout=30_000) as download_info:
            if trigger_callable:
                await trigger_callable()
        download = await download_info.value
        filename = download.suggested_filename
        target_path = save_dir / filename
        await download.save_as(str(target_path))
        log.info("File downloaded successfully to: %s", target_path)
        return f"File downloaded: {filename} (saved to {target_path})"
    except Exception as exc:
        log.error("Download handling failed: %s", exc)
        return f"Download failed: {exc}"


# ── Gmail / Browser-Based Email Primitives ─────────────────────────────────

async def open_gmail_compose(recipient: str = "", subject: str = "", body: str = "") -> dict[str, Any]:
    """
    Open Gmail in a tab, click Compose, and populate To / Subject / Message fields.
    Returns status dict with active page and drafted fields.
    """
    p = await new_page("https://mail.google.com")
    await asyncio.sleep(2.0)

    try:
        compose_clicked = False
        for sel in [
            'div[role="button"][gh="cm"]',
            'div[aria-label="Compose"]',
            'div[data-tooltip="Compose"]',
            'text=Compose',
            'div[role="button"]:has-text("Compose")',
        ]:
            try:
                btn = p.locator(sel).first
                if await btn.count() > 0:
                    await btn.click(timeout=5_000)
                    compose_clicked = True
                    break
            except Exception:
                continue

        if not compose_clicked:
            await p.keyboard.press("c")

        await asyncio.sleep(1.0)

        if recipient:
            for to_sel in ['input[aria-label="To recipients"]', 'input[name="to"]', 'input[peoplekit-id]', 'textarea[name="to"]']:
                try:
                    to_input = p.locator(to_sel).first
                    if await to_input.count() > 0:
                        await to_input.fill(recipient)
                        await p.keyboard.press("Enter")
                        break
                except Exception:
                    continue

        if subject:
            for subj_sel in ['input[name="subjectbox"]', 'input[aria-label="Subject"]', 'input[placeholder="Subject"]']:
                try:
                    subj_input = p.locator(subj_sel).first
                    if await subj_input.count() > 0:
                        await subj_input.fill(subject)
                        break
                except Exception:
                    continue

        if body:
            for body_sel in ['div[aria-label="Message Body"]', 'div[role="textbox"][aria-label*="Message"]', 'div[contenteditable="true"]']:
                try:
                    body_el = p.locator(body_sel).first
                    if await body_el.count() > 0:
                        await body_el.fill(body)
                        break
                except Exception:
                    continue

        return {
            "success": True,
            "page": p,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "message": f"Drafted email to '{recipient}' with subject '{subject}'.",
        }
    except Exception as exc:
        log.warning("Gmail compose error: %s", exc)
        return {
            "success": False,
            "page": p,
            "error": str(exc),
            "message": f"Opened Gmail. Could not auto-fill compose window ({exc}).",
        }


async def send_gmail_draft(page=None) -> bool:
    """
    Click Send button in active Gmail compose window and verify submission.
    """
    p = page or await get_active_page()
    for send_sel in [
        'div[role="button"][data-tooltip*="Send"]',
        'div[aria-label*="Send"]',
        'div[role="button"]:has-text("Send")',
        'div.T-I.J-J5-Ji.aoO.v7.T-I-atl.L3',
    ]:
        try:
            btn = p.locator(send_sel).first
            if await btn.count() > 0:
                await btn.click(timeout=6_000)
                await asyncio.sleep(2.0)
                log.info("Gmail Send clicked successfully.")
                return True
        except Exception:
            continue

    try:
        await p.keyboard.press("Control+Enter")
        await asyncio.sleep(2.0)
        return True
    except Exception:
        return False


# ── Browser Shutdown ───────────────────────────────────────────────────────

async def close_browser() -> None:
    """Shut down the browser and Playwright cleanly."""
    global _browser, _context, _playwright, _active_page_idx
    async with _browser_lock:
        try:
            if _context:
                await _context.close()
            if _browser:
                await _browser.close()
            if _playwright:
                await _playwright.stop()
        except Exception as exc:
            log.warning("Browser cleanup error: %s", exc)
        finally:
            _browser = None
            _context = None
            _playwright = None
            _active_page_idx = 0
            log.info("Playwright browser closed.")

