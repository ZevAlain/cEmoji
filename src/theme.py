from PySide6.QtGui import QPalette


COLORS = {
    "dark": {
        "window": "#11161d",
        "window_top": "#171d26",
        "window_bottom": "#0f141b",
        "panel": "rgba(31, 38, 49, 218)",
        "panel_alt": "rgba(43, 52, 66, 230)",
        "panel_solid": "#1f2631",
        "border": "rgba(150, 164, 184, 58)",
        "border_strong": "rgba(183, 197, 216, 104)",
        "text": "#f3f7fb",
        "muted": "#a8b3c2",
        "accent": "#6aa9ff",
        "accent_hover": "#8fc0ff",
        "accent_soft": "rgba(75, 137, 222, 62)",
        "danger": "#ff6b86",
        "item_hover": "rgba(255, 255, 255, 34)",
        "item_selected": "rgba(82, 142, 220, 76)",
        "scroll": "rgba(180, 193, 212, 118)",
        "scroll_hover": "rgba(218, 228, 241, 190)",
        "empty": "#96a3b5",
    },
    "light": {
        "window": "#f4f8fc",
        "window_top": "#fbfdff",
        "window_bottom": "#edf3f9",
        "panel": "rgba(255, 255, 255, 226)",
        "panel_alt": "rgba(242, 247, 252, 238)",
        "panel_solid": "#ffffff",
        "border": "rgba(123, 139, 161, 78)",
        "border_strong": "rgba(83, 102, 130, 118)",
        "text": "#1f2937",
        "muted": "#64748b",
        "accent": "#2563eb",
        "accent_hover": "#1d4ed8",
        "accent_soft": "rgba(37, 99, 235, 42)",
        "danger": "#dc3f5d",
        "item_hover": "rgba(37, 99, 235, 24)",
        "item_selected": "rgba(37, 99, 235, 46)",
        "scroll": "rgba(100, 116, 139, 96)",
        "scroll_hover": "rgba(71, 85, 105, 160)",
        "empty": "#64748b",
    },
}


def colors(mode):
    return COLORS["dark" if mode == "dark" else "light"]


def system_theme_mode(palette):
    return "dark" if palette.color(QPalette.ColorRole.Window).lightness() < 128 else "light"


def window_stylesheet(mode):
    color = colors(mode)
    return f"""
        QWidget {{
            background: {color["window"]};
            color: {color["text"]};
        }}
        QWidget#ImageViewer {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {color["window_top"]}, stop:1 {color["window_bottom"]});
        }}
        QFrame {{
            background: transparent;
            border: none;
        }}
        QFrame#ShortcutFrame {{
            background: {color["panel"]};
            border: 1px solid {color["border"]};
            border-radius: 11px;
        }}
        QPushButton, QKeySequenceEdit {{
            background: {color["panel"]};
            border: 1px solid {color["border"]};
            border-radius: 9px;
            padding: 7px 11px;
            min-height: 22px;
            color: {color["text"]};
        }}
        QPushButton:hover, QKeySequenceEdit:hover {{
            background: {color["panel_alt"]};
            border-color: {color["border_strong"]};
        }}
        QPushButton:pressed {{
            background: {color["accent_soft"]};
            border-color: {color["accent"]};
        }}
        QPushButton:checked {{
            background: {color["accent_soft"]};
            border-color: {color["accent"]};
            color: {color["accent_hover"]};
        }}
        QPushButton::menu-indicator {{
            width: 0;
            image: none;
        }}
        QTabBar#EmojiFilterTabs {{
            background: transparent;
        }}
        QTabBar#EmojiFilterTabs::tab {{
            background: {color["panel"]};
            border: 1px solid {color["border"]};
            border-radius: 9px;
            color: {color["muted"]};
            margin-right: 6px;
            padding: 7px 18px;
            min-width: 92px;
        }}
        QTabBar#EmojiFilterTabs::tab:hover {{
            background: {color["panel_alt"]};
            color: {color["text"]};
            border-color: {color["border_strong"]};
        }}
        QTabBar#EmojiFilterTabs::tab:selected {{
            background: {color["accent_soft"]};
            color: {color["accent_hover"]};
            border-color: {color["accent"]};
        }}
        QLineEdit {{
            background: {color["panel"]};
            border: 1px solid {color["border"]};
            border-radius: 10px;
            padding: 8px 11px;
            color: {color["text"]};
            selection-background-color: {color["accent"]};
        }}
        QLineEdit:hover {{
            border-color: {color["border_strong"]};
        }}
        QLineEdit:focus {{
            border-color: {color["accent"]};
            background: {color["panel_alt"]};
        }}
        QLineEdit::placeholder {{
            color: {color["muted"]};
        }}
        QCheckBox {{
            background: transparent;
            color: {color["text"]};
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 5px;
            border: 1px solid {color["border_strong"]};
            background: {color["panel"]};
        }}
        QCheckBox::indicator:checked {{
            background: {color["accent"]};
            border-color: {color["accent"]};
        }}
        QLabel {{
            background: transparent;
            color: {color["text"]};
        }}
        QLabel#CopyTipLabel, QLabel#HotkeyStatusLabel {{
            color: {color["muted"]};
        }}
        QLabel#UpdateLink {{
            color: {color["accent"]};
        }}
        QMenu {{
            background: {color["panel"]};
            border: 1px solid {color["border"]};
            border-radius: 10px;
            padding: 6px;
            color: {color["text"]};
        }}
        QMenu::item {{
            padding: 7px 24px 7px 10px;
            border-radius: 6px;
        }}
        QMenu::item:selected {{
            background: {color["accent_soft"]};
            color: {color["text"]};
        }}
        QMenu::separator {{
            height: 1px;
            background: {color["border"]};
            margin: 6px 4px;
        }}
        QMessageBox {{
            background: {color["window"]};
        }}
    """


def emoji_view_stylesheet(mode):
    color = colors(mode)
    return f"""
        QListView {{
            background: {color["panel"]};
            border: 1px solid {color["border"]};
            border-radius: 11px;
            outline: 0;
            padding: 4px;
        }}
        QListView::item {{
            color: {color["text"]};
            padding: 5px;
            border-radius: 9px;
        }}
        QListView::item:hover {{
            background: {color["item_hover"]};
        }}
        QListView::item:selected {{
            background: {color["item_selected"]};
            color: {color["text"]};
            border: 1px solid {color["accent"]};
        }}
        QListView::item:selected:hover {{
            background: {color["item_selected"]};
            color: {color["text"]};
            border: 1px solid {color["accent"]};
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 5px 2px 5px 0;
        }}
        QScrollBar::handle:vertical {{
            background: {color["scroll"]};
            border-radius: 4px;
            min-height: 36px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {color["scroll_hover"]};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            background: transparent;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 8px;
            margin: 0 5px 2px 5px;
        }}
        QScrollBar::handle:horizontal {{
            background: {color["scroll"]};
            border-radius: 4px;
            min-width: 36px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {color["scroll_hover"]};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
            background: transparent;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}
    """