# SortInator Design System

## Direction

The interface uses a **campus filing docket**: incoming documents are visible
records moving from intake to a subject, rather than abstract dashboard
metrics. It avoids a generic card grid and treats the inbox row and filing
prompt as the product's signature moments.

Direction seed: `0268781f`, grounded candidate seven.

## Use Scene

A student uses the app throughout a normal Windows workday and late study
sessions, often with several browser and document windows open. A deep navy
canvas reduces glare while elevated blue-charcoal records keep dense filenames
easy to scan. The navigation remains the darkest anchor when restored from the
tray.

## Palette

| Role | Value | Use |
|---|---:|---|
| Institutional ink | `#08111D` | Sidebar, icon tile, deepest structure |
| Night canvas | `#0E1622` | Main application ground |
| Raised docket | `#151F2D` | Inputs and individual records |
| Rule | `#2B3949` | One-pixel boundaries |
| Filing teal | `#49CFC0` | Focus, links and current proposal |
| Teal action | `#0E7E77` | Primary and selected controls |
| Teal wash | `#123A39` | Active intake state |
| Body | `#E8EEF5` | Main text |
| Muted | `#9BAABD` | Metadata and supporting copy |
| Danger | `#FF818B` | Destructive action and overdue state |
| Warning | `#F1BB68` | Paused watcher and due-today state |

Colour is semantic. Subject colours appear only as small identity swatches;
every state also has explicit copy.

## Typography

Windows supplies Segoe UI / Segoe UI Variable. Product copy uses one workhorse
family with a compact scale:

- Page title: 28 px, weight 700
- Section title: 17 px, weight 650
- Row and action title: 14 px, weight 600
- Body: 14 px
- Metadata: 12 px

Portuguese diacritics and long file names must be tested at the shipping DPI.

## Layout

- Main window: 1180 × 760 default, 980 × 660 minimum.
- Sidebar: fixed 224 px; content is fluid.
- Page inset: 34 px horizontal, 28 px top.
- Home: one state strip, then a capped preview of the newest five documents
  (with a quiet link to the full search) beside the next five deadlines in a
  3:2 column split. The page scrolls invisibly only as a fallback for
  unusual scaling; long file names elide with the full name in a tooltip.
- Lists: 9 px between records; no enclosing card around a list of cards.
- Filing prompt: fixed 570 px, positioned 18 px above the bottom-left of the
  cursor's Windows work area so native notifications cannot cover it.

## Components

- **Navigation:** text-first, filled active state, persistent watcher status.
- **Docket row:** filename/task first, metadata second, actions aligned right.
- **Primary button:** teal fill, white label, reserved for the next committed
  action.
- **Quiet action:** text on transparent surface for opening/revealing content.
- **Danger action:** red text and pale border; never the default focus.
- **Subject/type chip:** selected by filled teal state and keyboard shortcut.
- **Input:** inset navy surface, one-pixel cool rule, two-pixel teal focus.
- **Switch:** settings use a painted `ToggleSwitch` (teal fill on state) with
  the same checkbox contract; Space toggles and changes still require an
  explicit save.
- **Empty state:** explains what will appear and the next useful action.
- **Inbox import:** a heading action opens a count-bearing, default-cancel
  confirmation and disables itself while the capped batch is checked.

## Settings Organization

The Definições page is one scrollable body divided by one-pixel rules into
four titled groups — *Pastas e ficheiros*, *Vigilância e notificações*,
*Aparência e idioma* and *Cópias de segurança* — each with its own
`SectionTitle` and form rows. Boolean settings render as switches inside their
group; feedback copy stays with the group it belongs to. The save button,
persistence feedback and version line stay fixed below the scrolling body,
outside it, so saving is always reachable without scrolling.

## Tasks Calendar

The Tarefas page leads with the task list; a 300px calendar panel sits to its
right and clamps its height. Below a 1120px window width the calendar folds
behind a labeled `Calendário` toggle so the task list keeps its space.
Weekend headers and dates render in the regular text colour (no grey weekend
tint), while deadline days keep their overdue/today/upcoming/done marks. Click
a day to filter the list to that date; clicking again or "Ver todas" clears.

## Command Palette

`Ctrl+K` opens a frameless 560px palette card over the main window, bounded to
the monitor work area. The controller registers every action in a
`CommandRegistry` each time it opens, so titles reflect the live state (for
example "Pausar vigilância" becomes "Retomar vigilância" while the watcher is
paused; the pause entry only exists while watching is running). Registered
actions: the six pages, notes search, import from Downloads, pause/resume
watching, undo the last filing, check for updates, open the University folder
and create a backup now. Row hints show the matching shortcut
(`Ctrl+1`–`Ctrl+6`, `Ctrl+F`).

Typing runs an accent- and case-folded match (title prefix, then title
containment, then keywords) on a worker thread with a 150ms debounce; only the
queued result handler touches the list, and stale answers are discarded.
Up/Down move the selection, Enter runs the selected command, Escape closes,
clicking a row runs it. Commands run through the same controller methods the
rest of the interface uses, so journaling and transfer-queue rules apply.
The card keeps a bounded 140ms upward entrance, instant in Contraste.

## States And Motion

Controls include hover, focus, pressed, disabled and error states. Motion is
capped by one shared budget: `theme.animation_ms()` returns 140 ms (the filing
prompt entrance, the palette entrance, ≤120 ms switch thumb travel) and 0 for
Contraste, where every state change is instant. Content is visible before any
animation and remains static afterward; animation only moves position or an
already-updated state, never reveals or hides information.

Native Windows checkboxes and spin controls preserve familiar state marks.
Disabled deadline controls change both colour and interaction.
Manual import progress stays in the Inbox page. Its completion copy distinguishes
imported, skipped and failed files and states that remaining files stayed in
Downloads.

## Accessibility

- Primary workflows are operable with Tab, Enter and Escape.
- Number keys 1–9 select prompt subjects.
- `Ctrl+K` opens the command palette; `Ctrl+F` focuses search; `Ctrl+1`
  through `Ctrl+6` navigate pages.
- Focus uses a visible two-pixel teal boundary.
- No status depends on colour alone.
- Errors identify both the failure and recovery action.

## Review Evidence

UI review captures are generated locally under `.impeccable/review/`. They are
gitignored and are not published with the repository. Regenerate them with:

```powershell
.\.venv\Scripts\python.exe .\scripts\capture_ui.py `
    --output-dir .impeccable\review `
    --temp-dir $env:TEMP
```

Captures include `palette.png` for the command palette card; tests cover the
settings groups and switches, the calendar fold breakpoint, weekend-neutral
text, palette matching/debounce and the palette lifecycle through the
controller.

The shipping application carries one committed raster asset: the supplied
brand mark (`assets/icon.png`), processed by `scripts/generate_icon.py` into
`icon-square.png` and the multi-size `icon.ico`. The fallback icon is drawn
programmatically in `src/organizador/ui/icons.py`.
