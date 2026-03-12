# Plan 04 — Checkbox Checkmark Icon

## Status
Complete

## Goal
Show a visible white checkmark (`✓`) inside the checkbox when it is checked, so the checked vs. unchecked state is immediately obvious.

## Current Behaviour
- Unchecked: dark fill (`#313244`) with a subtle border (`#45475a`).
- Checked: solid accent fill (`#89b4fa`) with matching border — **no checkmark symbol**. The only visual difference is the fill color, which is hard to notice at a glance.

## Current Stylesheet (relevant section)
```css
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #45475a;
    border-radius: 3px;
    background-color: #313244;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}
```

## Approach — Unicode Checkmark via `image` or Painted Text
Qt stylesheets for `QCheckBox::indicator:checked` do **not** support the `content` CSS property (it's not real CSS — it's Qt Stylesheet). The two clean options:

### Option A — Inline SVG Data URI (Recommended)
Embed a tiny SVG checkmark directly in the stylesheet using a `data:` URI. No external file needed:

```css
QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M3.5 8.5 L6.5 11.5 L12.5 4.5' stroke='white' stroke-width='2.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
}
```

**Note:** Qt's stylesheet parser can be picky with inline SVGs. If the data URI doesn't work reliably across platforms, fall back to Option B.

### Option B — Generated QPixmap (Fallback)
Create the checkmark icon programmatically and save it as a temp file (or use `addSearchPath`):

```python
from PyQt6.QtCore import QDir, QTemporaryDir
from PyQt6.QtGui import QPainter, QPen, QPixmap
from PyQt6.QtCore import Qt

def _create_check_icon(size=16) -> str:
    """Create a white checkmark pixmap and return path to it."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    pen = QPen(Qt.GlobalColor.white)
    pen.setWidth(2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Draw checkmark path
    painter.drawLine(3, 8, 6, 11)
    painter.drawLine(6, 11, 12, 4)
    painter.end()
    path = os.path.join(tempfile.gettempdir(), "rt_check.png")
    pixmap.save(path)
    return path.replace("\\", "/")
```

Then inject the path into the stylesheet:
```python
check_path = _create_check_icon()
STYLESHEET = STYLESHEET.replace(
    "QCheckBox::indicator:checked {",
    f"QCheckBox::indicator:checked {{\n    image: url({check_path});"
)
```

### Recommended: Try Option A first, fall back to Option B if needed.

## Changes Required

### 1. `src/main_window.py` — `STYLESHEET` constant
Replace the `QCheckBox::indicator:checked` block:

```css
QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M3.5 8.5 L6.5 11.5 L12.5 4.5' stroke='white' stroke-width='2.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
}
```

If testing shows the data URI doesn't render on Windows, switch to Option B (programmatic pixmap).

## Testing
1. Launch app → output format checkboxes (`.txt`, `.srt`, `.vtt`) should show a white `✓` on blue when checked.
2. Uncheck a format → checkmark disappears, returns to dark fill.
3. Diarization checkbox (added in Plan 03) should also get the same styling automatically since it uses the same `QCheckBox` class.
4. Verify on Windows (primary target) and optionally on Linux/macOS.
