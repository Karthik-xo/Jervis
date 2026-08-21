"""
Vision service — screen capture and analysis.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

log = logging.getLogger("jarvis.vision")


async def capture_screen(save_path: Path | None = None) -> Path:
    """Capture primary screen to a PNG file and return its path."""
    from jarvis.core.config import data_dir
    import datetime

    path = save_path or data_dir() / "screenshots" / f"screen_{datetime.datetime.now():%Y%m%d_%H%M%S}.png"
    path.parent.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_running_loop()

    def _capture():
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                img = sct.grab(monitor)
                mss.tools.to_png(img.rgb, img.size, output=str(path))
        except ImportError:
            # Fallback using PIL if mss not available
            try:
                from PIL import ImageGrab
                screenshot = ImageGrab.grab()
                screenshot.save(str(path))
            except ImportError:
                log.warning("Neither mss nor PIL available for screenshots.")
                raise RuntimeError("No screenshot library available. Install mss or Pillow.")

    await loop.run_in_executor(None, _capture)
    log.info("Screenshot saved: %s", path)
    return path
