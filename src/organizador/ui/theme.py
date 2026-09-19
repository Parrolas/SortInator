"""Switchable colour palettes and the stylesheet built from them."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from organizador.config import DEFAULT_THEME, THEME_IDS


@dataclass(frozen=True, slots=True)
class Theme:
    """One named palette; every colour used by the UI is a token."""

    id: str
    display_name: str
    dark: bool
    ink: str
    ink_hover: str
    canvas: str
    paper: str
    border: str
    text: str
    muted: str
    teal: str
    teal_fill: str
    teal_hover: str
    teal_soft: str
    warning: str
    warning_soft: str
    danger: str
    danger_soft: str
    danger_border: str
    success: str
    primary_fg: str
    sidebar_text: str
    sidebar_text_active: str
    sidebar_checked_bg: str
    brand_detail: str
    row_hover: str
    row_hover_border: str
    intake_border: str
    warning_border: str
    button_hover: str
    button_hover_border: str
    pressed: str
    disabled_fg: str
    disabled_bg: str
    disabled_border: str
    chip_bg: str
    sunken: str
    input_border: str
    input_hover_border: str
    scrollbar_handle: str
    scrollbar_hover: str
    tooltip_bg: str
    tooltip_border: str
    mid: str
    midlight: str
    palette_dark: str
    palette_light: str
    placeholder: str
    status_ok: str
    status_warn: str
    status_off: str
    status_text: str
    onboarding_text: str
    onboarding_muted: str
    cal_mark_overdue: str
    cal_mark_today: str
    cal_mark_upcoming: str
    cal_mark_done: str


THEMES: dict[str, Theme] = {
    "escuro": Theme(
        id="escuro",
        display_name="Escuro",
        dark=True,
        ink="#08111D",
        ink_hover="#10263A",
        canvas="#0E1622",
        paper="#151F2D",
        border="#2B3949",
        text="#E8EEF5",
        muted="#9BAABD",
        teal="#49CFC0",
        teal_fill="#0E7E77",
        teal_hover="#14827A",
        teal_soft="#123A39",
        warning="#F1BB68",
        warning_soft="#352A18",
        danger="#FF818B",
        danger_soft="#331D25",
        danger_border="#6B3941",
        success="#75D5A6",
        primary_fg="#FFFFFF",
        sidebar_text="#C2CFDC",
        sidebar_text_active="#FFFFFF",
        sidebar_checked_bg="#17344B",
        brand_detail="#A8B7C8",
        row_hover="#182535",
        row_hover_border="#405267",
        intake_border="#285C58",
        warning_border="#6D5430",
        button_hover="#1B2939",
        button_hover_border="#46586C",
        pressed="#111A27",
        disabled_fg="#667586",
        disabled_bg="#111A25",
        disabled_border="#1F2B39",
        chip_bg="#182433",
        sunken="#101A27",
        input_border="#334456",
        input_hover_border="#53677C",
        scrollbar_handle="#3A4B5D",
        scrollbar_hover="#52667A",
        tooltip_bg="#1B2939",
        tooltip_border="#405267",
        mid="#344659",
        midlight="#405267",
        palette_dark="#263548",
        palette_light="#52667A",
        placeholder="#718195",
        status_ok="#35C08A",
        status_warn="#E6A53A",
        status_off="#8EA1B1",
        status_text="#AFC0CF",
        onboarding_text="#C6D4DF",
        onboarding_muted="#9EB2C2",
        cal_mark_overdue="#4A262E",
        cal_mark_today="#4A3520",
        cal_mark_upcoming="#1E4D46",
        cal_mark_done="#222F3E",
    ),
    "claro": Theme(
        id="claro",
        display_name="Claro",
        dark=False,
        ink="#E8EDF4",
        ink_hover="#D8E2EE",
        canvas="#EEF2F7",
        paper="#FFFFFF",
        border="#D5DEE8",
        text="#16233B",
        muted="#5A6B80",
        teal="#0E7E77",
        teal_fill="#0E7E77",
        teal_hover="#0B6B65",
        teal_soft="#D9EFED",
        warning="#9A6A12",
        warning_soft="#FBF0D8",
        danger="#C43D3D",
        danger_soft="#FBE5E5",
        danger_border="#E5B8B8",
        success="#1F8A5A",
        primary_fg="#FFFFFF",
        sidebar_text="#44546A",
        sidebar_text_active="#16233B",
        sidebar_checked_bg="#D3E2F2",
        brand_detail="#5A6B80",
        row_hover="#F0F5FB",
        row_hover_border="#C2CFDE",
        intake_border="#9FD3CE",
        warning_border="#E3CD9B",
        button_hover="#EDF2F9",
        button_hover_border="#B9C7D9",
        pressed="#E2E9F2",
        disabled_fg="#93A1B3",
        disabled_bg="#F2F5F9",
        disabled_border="#E1E7EF",
        chip_bg="#F1F5FA",
        sunken="#F5F8FC",
        input_border="#C6D2E0",
        input_hover_border="#9FB2C8",
        scrollbar_handle="#C3CEDB",
        scrollbar_hover="#A6B5C7",
        tooltip_bg="#FFFFFF",
        tooltip_border="#C2CFDE",
        mid="#D9E2EC",
        midlight="#E5ECF4",
        palette_dark="#C6D2E0",
        palette_light="#FFFFFF",
        placeholder="#93A1B3",
        status_ok="#1F8A5A",
        status_warn="#B07818",
        status_off="#7A8A9C",
        status_text="#44546A",
        onboarding_text="#3A4A5E",
        onboarding_muted="#6B7C90",
        cal_mark_overdue="#F6D7D7",
        cal_mark_today="#F8EAC9",
        cal_mark_upcoming="#D6ECE9",
        cal_mark_done="#E6EBF2",
    ),
    "oceano": Theme(
        id="oceano",
        display_name="Oceano",
        dark=True,
        ink="#081018",
        ink_hover="#12233C",
        canvas="#0A1424",
        paper="#0F1E36",
        border="#23406B",
        text="#DCE9F7",
        muted="#8AA3C4",
        teal="#5BC8E8",
        teal_fill="#14719C",
        teal_hover="#1A85B5",
        teal_soft="#123450",
        warning="#F1BB68",
        warning_soft="#3A3320",
        danger="#FF8A93",
        danger_soft="#3F2136",
        danger_border="#6E3A50",
        success="#7BD8AC",
        primary_fg="#FFFFFF",
        sidebar_text="#9FB6D4",
        sidebar_text_active="#FFFFFF",
        sidebar_checked_bg="#123A5C",
        brand_detail="#8AA3C4",
        row_hover="#12233C",
        row_hover_border="#2B4E7E",
        intake_border="#2B6478",
        warning_border="#6D5C30",
        button_hover="#132844",
        button_hover_border="#2E567F",
        pressed="#0E1D33",
        disabled_fg="#5F7A9E",
        disabled_bg="#0E1C31",
        disabled_border="#1B3352",
        chip_bg="#122540",
        sunken="#0C1930",
        input_border="#24466E",
        input_hover_border="#35618F",
        scrollbar_handle="#274B74",
        scrollbar_hover="#35618F",
        tooltip_bg="#132844",
        tooltip_border="#2B4E7E",
        mid="#1E3A5F",
        midlight="#29507C",
        palette_dark="#16304F",
        palette_light="#35618F",
        placeholder="#6E8BB0",
        status_ok="#3FC493",
        status_warn="#E6A53A",
        status_off="#7E97B8",
        status_text="#9FB6D4",
        onboarding_text="#B7D0E8",
        onboarding_muted="#7E97B8",
        cal_mark_overdue="#3A2038",
        cal_mark_today="#3A3320",
        cal_mark_upcoming="#123C55",
        cal_mark_done="#14263F",
    ),
    "sepia": Theme(
        id="sepia",
        display_name="Sépia",
        dark=False,
        ink="#EFE7D8",
        ink_hover="#E4D8C2",
        canvas="#F3EDDF",
        paper="#FCF9F1",
        border="#DDD2BC",
        text="#3B3226",
        muted="#7A6E5C",
        teal="#A0622D",
        teal_fill="#A0622D",
        teal_hover="#8D5324",
        teal_soft="#F1E2D0",
        warning="#9A6A12",
        warning_soft="#F5EAD2",
        danger="#B84A3C",
        danger_soft="#F7E2DD",
        danger_border="#E0BFB6",
        success="#5F7D3F",
        primary_fg="#FFFFFF",
        sidebar_text="#6B5E48",
        sidebar_text_active="#3B3226",
        sidebar_checked_bg="#E7DAC1",
        brand_detail="#7A6E5C",
        row_hover="#F3ECDD",
        row_hover_border="#CFC2A6",
        intake_border="#D9BFA0",
        warning_border="#D9C08A",
        button_hover="#F1E9D8",
        button_hover_border="#C9BA9C",
        pressed="#E9DFC9",
        disabled_fg="#A79A82",
        disabled_bg="#F5F0E4",
        disabled_border="#E5DCC8",
        chip_bg="#F4EDDC",
        sunken="#F7F1E3",
        input_border="#D3C6A9",
        input_hover_border="#B8A67F",
        scrollbar_handle="#CFC2A6",
        scrollbar_hover="#B8A67F",
        tooltip_bg="#FCF9F1",
        tooltip_border="#CFC2A6",
        mid="#E2D7BE",
        midlight="#EAE0CB",
        palette_dark="#D3C6A9",
        palette_light="#FCF9F1",
        placeholder="#A79A82",
        status_ok="#5F7D3F",
        status_warn="#9A6A12",
        status_off="#8D8270",
        status_text="#6B5E48",
        onboarding_text="#4A4132",
        onboarding_muted="#7A6E5C",
        cal_mark_overdue="#F2DCD4",
        cal_mark_today="#F1E5C4",
        cal_mark_upcoming="#EADFC8",
        cal_mark_done="#E9E1CE",
    ),
    "contraste": Theme(
        id="contraste",
        display_name="Alto contraste",
        dark=True,
        ink="#000000",
        ink_hover="#1A1A1A",
        canvas="#000000",
        paper="#0D0D0D",
        border="#FFFFFF",
        text="#FFFFFF",
        muted="#E0E0E0",
        teal="#FFD400",
        teal_fill="#FFD400",
        teal_hover="#E6BF00",
        teal_soft="#3A3400",
        warning="#FFD400",
        warning_soft="#3A3400",
        danger="#FF7070",
        danger_soft="#4A1414",
        danger_border="#FF7070",
        success="#6BFF9E",
        primary_fg="#000000",
        sidebar_text="#FFFFFF",
        sidebar_text_active="#FFD400",
        sidebar_checked_bg="#262600",
        brand_detail="#E0E0E0",
        row_hover="#1A1A1A",
        row_hover_border="#FFFFFF",
        intake_border="#FFD400",
        warning_border="#FFD400",
        button_hover="#262626",
        button_hover_border="#FFFFFF",
        pressed="#333333",
        disabled_fg="#808080",
        disabled_bg="#0D0D0D",
        disabled_border="#4D4D4D",
        chip_bg="#1A1A1A",
        sunken="#000000",
        input_border="#FFFFFF",
        input_hover_border="#FFD400",
        scrollbar_handle="#666666",
        scrollbar_hover="#999999",
        tooltip_bg="#262626",
        tooltip_border="#FFFFFF",
        mid="#4D4D4D",
        midlight="#666666",
        palette_dark="#333333",
        palette_light="#999999",
        placeholder="#B3B3B3",
        status_ok="#6BFF9E",
        status_warn="#FFD400",
        status_off="#B3B3B3",
        status_text="#FFFFFF",
        onboarding_text="#FFFFFF",
        onboarding_muted="#E0E0E0",
        cal_mark_overdue="#4A1414",
        cal_mark_today="#3A3400",
        cal_mark_upcoming="#3A3400",
        cal_mark_done="#1A1A1A",
    ),
}

assert set(THEMES) == set(THEME_IDS), "config.THEME_IDS and ui themes disagree"
assert DEFAULT_THEME in THEMES

_active: Theme = THEMES[DEFAULT_THEME]


def get_theme(theme_id: str) -> Theme:
    """Return a theme by id, falling back to the default."""

    return THEMES.get(theme_id, THEMES[DEFAULT_THEME])


def current() -> Theme:
    """Return the theme applied most recently."""

    return _active


def animation_ms() -> int:
    """Return the short-motion budget; Contraste keeps every change instant."""

    return 0 if _active.id == "contraste" else 140


def build_stylesheet(theme: Theme) -> str:
    """Build the full application stylesheet from one theme's tokens."""

    return f"""
QWidget {{
    color: {theme.text};
    font-family: "Segoe UI Variable", "Segoe UI";
    font-size: 14px;
}}
QMainWindow, QDialog, QWidget#Canvas, QStackedWidget {{
    background: {theme.canvas};
}}
QWidget#Sidebar {{
    background: {theme.ink};
}}
QLabel#Brand {{
    color: {theme.sidebar_text_active};
    font-size: 21px;
    font-weight: 700;
}}
QLabel#BrandDetail {{
    color: {theme.brand_detail};
    font-size: 12px;
}}
QLabel#PageTitle {{
    color: {theme.text};
    font-size: 28px;
    font-weight: 700;
}}
QLabel#PageSubtitle {{
    color: {theme.muted};
    font-size: 14px;
}}
QLabel#SectionTitle {{
    color: {theme.text};
    font-size: 17px;
    font-weight: 650;
}}
QLabel#RowTitle {{
    color: {theme.text};
    font-size: 14px;
    font-weight: 600;
}}
QLabel#Muted {{
    color: {theme.muted};
    font-size: 12px;
}}
QLabel#ErrorText {{
    color: {theme.danger};
    font-size: 12px;
}}
QLabel#SuccessText {{
    color: {theme.success};
    font-size: 12px;
}}
QFrame#Panel, QFrame#ListRow, QFrame#PromptCard {{
    background: {theme.paper};
    border: 1px solid {theme.border};
    border-radius: 10px;
}}
QFrame#PromptCard {{
    border-radius: 13px;
}}
QFrame#ListRow:hover {{
    background: {theme.row_hover};
    border-color: {theme.row_hover_border};
}}
QFrame#IntakeStrip {{
    background: {theme.teal_soft};
    border: 1px solid {theme.intake_border};
    border-radius: 8px;
}}
QFrame#Hairline {{
    background: {theme.border};
    min-height: 1px;
    max-height: 1px;
    border: none;
}}
QLineEdit#PaletteInput {{
    min-height: 40px;
    padding: 0 12px;
    border-radius: 7px;
    background: {theme.sunken};
    border: 1px solid {theme.input_border};
    font-size: 15px;
}}
QLineEdit#PaletteInput:focus {{
    border: 2px solid {theme.teal};
}}
QListWidget#PaletteList {{
    background: transparent;
    border: none;
    outline: 0;
}}
QListWidget#PaletteList::item {{
    min-height: 40px;
    border-radius: 6px;
    border: 1px solid transparent;
    color: {theme.text};
}}
QListWidget#PaletteList::item:hover {{
    background: {theme.row_hover};
}}
QListWidget#PaletteList::item:selected {{
    background: {theme.row_hover};
    border-color: {theme.teal};
    color: {theme.text};
}}
QFrame#WarningStrip {{
    background: {theme.warning_soft};
    border: 1px solid {theme.warning_border};
    border-radius: 8px;
}}
QPushButton {{
    min-height: 36px;
    padding: 0 15px;
    border: 1px solid {theme.border};
    border-radius: 7px;
    background: {theme.paper};
    color: {theme.text};
    font-weight: 600;
}}
QPushButton:hover {{
    background: {theme.button_hover};
    border-color: {theme.button_hover_border};
}}
QPushButton:pressed {{
    background: {theme.pressed};
}}
QPushButton:focus {{
    border: 2px solid {theme.teal};
}}
QPushButton:disabled {{
    color: {theme.disabled_fg};
    background: {theme.disabled_bg};
    border-color: {theme.disabled_border};
}}
QPushButton[variant="primary"] {{
    color: {theme.primary_fg};
    background: {theme.teal_fill};
    border-color: {theme.teal_fill};
}}
QPushButton[variant="primary"]:hover {{
    background: {theme.teal_hover};
    border-color: {theme.teal_hover};
}}
QPushButton[variant="quiet"] {{
    background: transparent;
    border-color: transparent;
    color: {theme.teal};
}}
QPushButton[variant="quiet"]:hover {{
    background: {theme.teal_soft};
}}
QPushButton[variant="danger"] {{
    background: transparent;
    border-color: {theme.danger_border};
    color: {theme.danger};
}}
QPushButton[variant="danger"]:hover {{
    background: {theme.danger_soft};
}}
QPushButton[nav="true"] {{
    min-height: 43px;
    padding: 0 15px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: {theme.sidebar_text};
    text-align: left;
    font-size: 14px;
    font-weight: 550;
}}
QPushButton[nav="true"]:hover {{
    background: {theme.ink_hover};
    color: {theme.sidebar_text_active};
}}
QPushButton[nav="true"]:checked {{
    background: {theme.sidebar_checked_bg};
    color: {theme.sidebar_text_active};
}}
QPushButton[chip="true"] {{
    min-height: 38px;
    padding: 0 13px;
    border-radius: 7px;
    background: {theme.chip_bg};
    border: 1px solid {theme.border};
}}
QPushButton[chip="true"]:checked {{
    color: {theme.primary_fg};
    background: {theme.teal_fill};
    border-color: {theme.teal_fill};
}}
QPushButton#PromptClose {{
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    padding: 0;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: {theme.muted};
    font-size: 16px;
}}
QPushButton#PromptClose:hover {{
    background: {theme.button_hover};
    color: {theme.text};
}}
QLineEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox {{
    min-height: 38px;
    padding: 0 10px;
    background: {theme.sunken};
    border: 1px solid {theme.input_border};
    border-radius: 7px;
    selection-background-color: {theme.teal_fill};
    selection-color: {theme.primary_fg};
}}
QTextEdit {{
    padding: 9px 10px;
}}
QLineEdit:hover, QTextEdit:hover, QComboBox:hover, QDateEdit:hover, QSpinBox:hover {{
    border-color: {theme.input_hover_border};
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus {{
    border: 2px solid {theme.teal};
}}
QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled,
QDateEdit:disabled, QSpinBox:disabled {{
    color: {theme.disabled_fg};
    background: {theme.disabled_bg};
    border-color: {theme.disabled_border};
}}
QComboBox::drop-down, QDateEdit::drop-down {{
    border: 0;
    width: 28px;
}}
QComboBox QAbstractItemView {{
    background: {theme.paper};
    border: 1px solid {theme.border};
    selection-background-color: {theme.teal_soft};
    selection-color: {theme.text};
    outline: 0;
}}
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator:unchecked {{
    background: {theme.sunken};
    border: 1px solid {theme.input_hover_border};
    border-radius: 2px;
}}
QCheckBox::indicator:unchecked:hover {{
    border-color: {theme.teal};
}}
QCheckBox:disabled {{
    color: {theme.disabled_fg};
}}
QCalendarWidget QWidget {{
    alternate-background-color: {theme.sunken};
}}
QCalendarWidget QAbstractItemView:enabled {{
    color: {theme.text};
    background: {theme.paper};
    selection-color: {theme.primary_fg};
    selection-background-color: {theme.teal_fill};
}}
QCalendarWidget QToolButton {{
    color: {theme.text};
    background: transparent;
    border-color: transparent;
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: transparent;
}}
QCalendarWidget QToolButton:hover {{
    color: {theme.text};
    background: {theme.ink_hover};
}}
QCalendarWidget QAbstractItemView {{
    font-size: 14px;
}}
QScrollArea {{
    border: 0;
    background: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    width: 10px;
    margin: 2px;
    background: transparent;
}}
QScrollBar::handle:vertical {{
    min-height: 30px;
    border-radius: 4px;
    background: {theme.scrollbar_handle};
}}
QScrollBar::handle:vertical:hover {{
    background: {theme.scrollbar_hover};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: transparent;
}}
QMenu {{
    background: {theme.paper};
    border: 1px solid {theme.border};
    padding: 6px;
}}
QMenu::item {{
    min-height: 30px;
    padding: 2px 28px 2px 10px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background: {theme.teal_soft};
    color: {theme.text};
}}
QMenu::separator {{
    height: 1px;
    margin: 5px 8px;
    background: {theme.border};
}}
QToolTip {{
    color: {theme.text};
    background: {theme.tooltip_bg};
    border: 1px solid {theme.tooltip_border};
    padding: 5px 7px;
}}
"""


def apply_theme(application: QApplication, theme: Theme) -> None:
    """Install one theme globally and remember it for token readers."""

    global _active
    _active = theme
    application.setStyle("Fusion")
    application.styleHints().setColorScheme(
        Qt.ColorScheme.Dark if theme.dark else Qt.ColorScheme.Light
    )
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(theme.canvas))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.Base, QColor(theme.paper))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme.sunken))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme.tooltip_bg))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.Text, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.Button, QColor(theme.paper))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.Light, QColor(theme.palette_light))
    palette.setColor(QPalette.ColorRole.Midlight, QColor(theme.midlight))
    palette.setColor(QPalette.ColorRole.Mid, QColor(theme.mid))
    palette.setColor(QPalette.ColorRole.Dark, QColor(theme.palette_dark))
    palette.setColor(QPalette.ColorRole.Shadow, QColor(theme.ink))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(theme.danger))
    palette.setColor(QPalette.ColorRole.Link, QColor(theme.teal))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.teal_fill))
    palette.setColor(QPalette.ColorRole.Accent, QColor(theme.teal_fill))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.primary_fg))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(theme.placeholder))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(theme.disabled_fg)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(theme.disabled_fg)
    )
    application.setPalette(palette)
    application.setStyleSheet(build_stylesheet(theme))
