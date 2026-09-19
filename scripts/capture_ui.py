"""Render deterministic UI review images without touching real user data."""

from __future__ import annotations

import argparse
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from organizador.classifier import guess_filing
from organizador.config import DEFAULT_THEME, AppConfig
from organizador.db import Database
from organizador.filer import FilingService
from organizador.i18n import _
from organizador.ui.commands import Command, CommandRegistry
from organizador.ui.main_window import MainWindow
from organizador.ui.palette import CommandPalette
from organizador.ui.prompt import FilingPrompt
from organizador.ui.theme import apply_theme, get_theme


def populate(config: AppConfig, database: Database, filer: FilingService) -> int:
    """Populate synthetic review-only content and return one inbox id."""

    calculus = database.add_subject(
        "Cálculo I",
        "MAT101",
        "#087A74",
        ("cálculo", "derivadas", "integrais"),
        filer.subject_folder_name("Cálculo I", "MAT101"),
    )
    physics = database.add_subject(
        "Física Geral",
        "FIS110",
        "#3C64A3",
        ("física", "cinemática", "forças"),
        filer.subject_folder_name("Física Geral", "FIS110"),
    )
    for subject in (calculus, physics):
        filer.ensure_subject_structure(subject)

    for filename, subject, kind, size in (
        ("Aula 06 - Derivadas.pdf", calculus, "Slides", 2_480_000),
        ("Ficha 03 - Cinemática.pdf", physics, "Exercícios", 640_000),
        ("Resumo - Integrais.md", calculus, "Outros", 18_500),
    ):
        inbox_path = config.inbox_dir / filename
        inbox_path.write_bytes(b"review content")
        item = database.add_inbox_item(inbox_path, config.downloads_dir / filename, filename, size)
        destination = config.university_root / subject.folder_name / kind / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        inbox_path.replace(destination)
        database.record_filing(item.id, subject.id, kind, destination)

    pending_path = config.inbox_dir / "MAT101_ficha_04_limites.pdf"
    pending_path.write_bytes(b"pending content")
    pending = database.add_inbox_item(
        pending_path,
        config.downloads_dir / pending_path.name,
        pending_path.name,
        782_000,
    )
    guess = guess_filing(pending.original_name, database.list_subjects())
    database.update_inbox_suggestion(pending.id, guess.subject_id, guess.kind)

    database.add_task(
        "Entregar relatório do laboratório",
        physics.id,
        date.today() + timedelta(days=2),
    )
    database.add_task(
        "Rever ficha de limites",
        calculus.id,
        date.today() + timedelta(days=6),
    )
    return pending.id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--temp-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.temp_dir.mkdir(parents=True, exist_ok=True)

    application = QApplication([])
    apply_theme(application, get_theme(DEFAULT_THEME))
    with tempfile.TemporaryDirectory(prefix="organizador-review-", dir=args.temp_dir) as raw:
        root = Path(raw)
        config = AppConfig(
            data_dir=root / "data",
            university_root=root / "Universidade",
            downloads_dir=root / "Downloads",
            initialized=True,
        )
        config.downloads_dir.mkdir(parents=True)
        config.ensure_directories()
        database = Database(config.database_path)
        database.initialize()
        filer = FilingService(config, database)
        inbox_id = populate(config, database, filer)

        window = MainWindow(database, config)
        window.resize(1180, 760)
        window.refresh_all(watching=True, paused=False)
        window.show()
        application.processEvents()
        if not window.grab().save(str(args.output_dir / "main-window.png")):
            return 1

        for page_key, filename in (
            ("inbox", "inbox.png"),
            ("tarefas", "tasks.png"),
            ("disciplinas", "subjects.png"),
            ("definicoes", "settings.png"),
        ):
            window.show_page(page_key)
            application.processEvents()
            if not window.grab().save(str(args.output_dir / filename)):
                return 1

        item = database.get_inbox_item(inbox_id)
        if item is None:
            return 1
        registry = CommandRegistry()
        for index, (page_key, title) in enumerate(
            (
                ("inicio", _("Início")),
                ("inbox", _("Caixa de Entrada")),
                ("pesquisa", _("Pesquisa")),
                ("tarefas", _("Tarefas")),
                ("disciplinas", _("Disciplinas")),
                ("definicoes", _("Definições")),
            ),
            start=1,
        ):
            registry.register(
                Command(
                    id=f"page.{page_key}",
                    title=title,
                    keywords="ir para página navegar go to page navigate",
                    shortcut=f"Ctrl+{index}",
                )
            )
        palette = CommandPalette(window)
        palette.open_with(registry.commands())
        application.processEvents()
        application.processEvents()
        palette.move(window.frameGeometry().center() - QPoint(palette.rect().center()))
        application.processEvents()
        if not palette.grab().save(str(args.output_dir / "palette.png")):
            return 1
        palette.close()
        palette.deleteLater()
        subjects = database.list_subjects()
        prompt = FilingPrompt()
        prompt.show_item(item, subjects, guess_filing(item.original_name, subjects))
        application.processEvents()
        if not prompt.grab().save(str(args.output_dir / "filing-prompt.png")):
            return 1
        prompt.timer.stop()
        prompt.hide()
        window.allow_close = True
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
