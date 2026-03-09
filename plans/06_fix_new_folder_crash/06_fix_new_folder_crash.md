# Plan 06 — Fix Crash When Creating New Folder in Output Directory Picker

## Goal

Prevent the application from crashing with an access violation when the user clicks
"New folder" inside the output-directory browser dialog on Windows.

---

## Root Cause

`_browse_outdir` in [src/main_window.py](../../src/main_window.py) calls:

```python
QFileDialog.getExistingDirectory(
    self, "Select Output Directory", self._outdir_edit.text() or ""
)
```

No `options` argument is supplied. On Windows, Qt6 therefore uses the **native Windows
shell folder-picker** (`IFileOpenDialog` COM API) by default. There is a known Qt6/PyQt6
bug on Windows where the native shell dialog triggers an **access violation** when the user
activates "New folder" — Qt's internal COM event callback tries to read the shell item for
the newly-created folder before the shell has finished creating it, producing a null-pointer
dereference inside `Qt6Widgets.dll`.

This is a Qt-level bug, not something in our Python code, so the only reliable workaround
is to opt out of the native dialog on Windows.

---

## Technical Approach

### Change — `src/main_window.py`, `_browse_outdir`

Replace the bare static call with one that passes
`QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.ShowDirsOnly`:

```python
def _browse_outdir(self) -> None:
    directory = QFileDialog.getExistingDirectory(
        self,
        "Select Output Directory",
        self._outdir_edit.text() or "",
        QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog,
    )
    if directory:
        self._outdir_edit.setText(directory)
```

`ShowDirsOnly` is the Qt default for `getExistingDirectory` on most platforms, but
must be stated explicitly when supplying any other option flag.

`DontUseNativeDialog` forces Qt's own cross-platform folder-picker widget, which
handles "New folder" safely because the folder-creation logic lives entirely in Qt's
own model — no COM reentrancy.

### Why not patch the Qt version?

The project pins `PyQt6>=6.4.0`. The bug is present across Qt 6.4–6.8 on Windows and
has no scheduled fix at the time of writing. Bumping the Qt version would not help Alex
(developer) or Jordan (end-user with the installed binary).

### Files changed

| File | Change |
|------|--------|
| `src/main_window.py` | Add option flags to `_browse_outdir` |
| `tests/test_ui_outdir_browse.py` | New test file (see Testing section) |

---

## Dependency and Compatibility Impact

- No new dependencies.
- `DontUseNativeDialog` is available on all PyQt6 versions ≥ 6.4.
- The Qt cross-platform dialog looks consistent with the existing app stylesheet on
  Windows 10/11 — no visual regression expected.
- macOS and Linux are unaffected; the flag is a no-op on those platforms for
  `getExistingDirectory` (they already use the Qt dialog by default when no native
  hook is available).

---

## Edge Cases

| Case | Handling |
|------|----------|
| User creates a new folder and immediately selects it | Qt cross-platform dialog handles this correctly — the new folder appears in the tree and can be selected before closing the dialog. |
| User cancels the dialog | `getExistingDirectory` returns `""` — the existing `if directory:` guard is already correct. |
| `_outdir_edit` contains a path that no longer exists | Qt dialog opens at the desktop/home fallback — same behaviour as before. |
| Path contains non-ASCII characters | Qt cross-platform dialog handles Unicode paths; the native dialog has historically had encoding issues on some Windows locales, so `DontUseNativeDialog` is actually an improvement here. |

---

## Testing Strategy

### New test file: `tests/test_ui_outdir_browse.py`

All tests use `pytest-qt` (`qtbot`) with `unittest.mock.patch` to avoid spawning a
real dialog.

#### Test 1 — `DontUseNativeDialog` flag is set

Patch `QFileDialog.getExistingDirectory`, capture the `options` argument, and assert
that `QFileDialog.Option.DontUseNativeDialog` is present in the flags passed.

```python
def test_browse_outdir_uses_non_native_dialog(qtbot, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    captured = {}
    def fake_dialog(parent, title, start_dir, options=None):
        captured["options"] = options
        return ""
    monkeypatch.setattr(
        "src.main_window.QFileDialog.getExistingDirectory", fake_dialog
    )
    window._browse_outdir()
    assert QFileDialog.Option.DontUseNativeDialog in captured["options"]
```

#### Test 2 — Selected directory is written to the output edit

Same patch pattern, but return a real path string; assert `_outdir_edit.text()` is
updated.

#### Test 3 — Cancelled dialog (empty return) does not clear existing text

Pre-populate `_outdir_edit`, patch to return `""`, assert text is unchanged.

---

## Persona Impact

### Jordan (non-technical end user)

- **Before:** clicking "New folder" in the Browse dialog hard-crashes the app with
  no error message — frightening and data-losing if a transcription was in progress.
- **After:** "New folder" works as expected. Jordan can create an organised output
  folder without leaving the app. The dialog looks slightly different (Qt vs Windows
  shell style) but is immediately familiar.
- **Risk:** None — Jordan never knew it was the "native" dialog.

### Alex (developer / contributor)

- The change is a one-liner with a clear comment explaining why
  `DontUseNativeDialog` is required. Easy to understand and audit.
- Tests are straightforward mock-based assertions — no exotic setup.
- The `DontUseNativeDialog` flag is well-documented in the Qt docs.
