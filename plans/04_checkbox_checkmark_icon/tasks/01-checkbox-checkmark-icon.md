# Task 04-01: Add White Checkmark to Checked Checkbox Indicator

- **Plan:** [plans/04_checkbox_checkmark_icon/04_checkbox_checkmark_icon.md](../04_checkbox_checkmark_icon.md)
- **Agent type:** UI
- **MAKER race:** Yes (dual-agent)
- **Depends on:** none
- **Files to modify:** `src/main_window.py`
- **Files to create:** none *(unless Option A fails — see fallback*\*)

---

## What to Implement

The `STYLESHEET` constant in `src/main_window.py` has a `QCheckBox::indicator:checked` block that currently only sets `background-color` and `border-color`. Update it to also render a white checkmark.

### Primary approach — Option A (inline SVG data URI)

Replace this block (lines ~212–215):

```css
QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}
```

With:

```css
QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
    image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M3.5 8.5 L6.5 11.5 L12.5 4.5' stroke='white' stroke-width='2.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
}
```

### Fallback — Option B (programmatic QPixmap) — use only if Option A fails

If the inline SVG data URI does not render on Windows (Qt stylesheet parser limitation), implement a helper function `_create_check_icon() -> str` that:

1. Creates a 16×16 `QPixmap` with transparent background.
2. Draws a white `V`-path checkmark with antialiased RoundCap/RoundJoin pen.
3. Saves it to `tempfile.gettempdir() / "rt_check.png"` (forward-slash path).
4. Returns the path string.

Call `_create_check_icon()` once during `MainWindow.__init__` and inject the path into `STYLESHEET` before calling `setStyleSheet`.

See [plans/04_checkbox_checkmark_icon.md](../04_checkbox_checkmark_icon.md) for the full Option B code sample.

---

## Tests to Write

Write in `tests/test_checkbox_icon.py`.

| # | Test | Red trigger |
|---|------|------------|
| 1 | `STYLESHEET` string contains `image:` inside the `QCheckBox::indicator:checked` block | Missing `image:` property |
| 2 | The icon definition references `stroke='white'` or stores a file called `rt_check.png` | Wrong colour or wrong file |
| 3 | A `QCheckBox` widget can be instantiated with the full `STYLESHEET` applied without raising | Stylesheet parse error crashes Qt |
| 4 | After checking and unchecking a `QCheckBox` in a `qtbot` session, `isChecked()` toggles correctly (baseline behaviour survives the change) | Style change accidentally broke checkbox logic |

Tests 1 and 2 are pure string/file assertions — no display needed.
Tests 3 and 4 require `pytest-qt` (`qtbot` fixture).

---

## Acceptance Criteria

1. Checked checkboxes display a visible white checkmark on the blue `#89b4fa` background.
2. Unchecked checkboxes show no checkmark (dark `#313244` fill).
3. The style applies automatically to all `QCheckBox` instances — format checkboxes (`.srt`, `.vtt`, `.txt`) and any future checkboxes added to the same window (e.g. diarization in Plan 03).
4. No new external image files are committed to the repository (Option A), **OR** Option B creates the icon at runtime and injects the path correctly before `setStyleSheet` is called.
5. All 4 new tests pass.
6. All pre-existing tests continue to pass.

---

## Red-Flag Triggers

Stop and escalate if:

- Option A renders no visible checkmark **and** Option B also fails to produce a visible icon — may indicate a Qt version or platform rendering gap; escalate to Architect.
- The SVG or QPixmap approach requires a new package not already in `requirements.txt`.
- Any change to `STYLESHEET` inadvertently alters the appearance of non-checkbox widgets (check via visual inspection or stylesheet string assertions).
- A test requires mocking Qt's style engine at the C++ level — that's a test design problem; re-scope the test instead of patching Qt internals.

---

## Notes

- This task is intentionally small (~1 TDD cycle). Reach K=3 by writing the failing test, implementing Option A, then verifying and refactoring the test assertions to cover Option B detection as well.
- Plan execution order is 04 → 02 → 01 → 03. This task has no dependencies and no downstream tasks depend on it, so it can race immediately.
