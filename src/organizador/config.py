"""Application configuration and Windows known-folder discovery."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - only relevant outside Windows
    winreg = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)

APP_NAME = "SortInator"
LEGACY_APP_NAME = "Organizador"
DOWNLOADS_GUID = "{374DE290-123F-4565-9164-39C4925E467B}"
MANUAL_IMPORT_BATCH_LIMIT = 25
DEFAULT_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".ipynb",
    ".md",
    ".txt",
    ".csv",
    ".one",
)
TEMPORARY_SUFFIXES = (
    ".crdownload",
    ".part",
    ".partial",
    ".tmp",
    ".download",
    ".opdownload",
)
NAME_TEMPLATE_TOKENS: tuple[str, ...] = (
    "{disciplina}",
    "{codigo}",
    "{tipo}",
    "{nome_original}",
    "{data}",
    "{ano}",
    "{mes}",
    "{dia}",
)
DEFAULT_FILENAME_TEMPLATE = "{nome_original}"
THEME_IDS: tuple[str, ...] = ("escuro", "claro", "oceano", "sepia", "contraste")
DEFAULT_THEME = "escuro"
LANGUAGE_IDS: tuple[str, ...] = ("pt", "en", "es", "fr")
DEFAULT_LANGUAGE = "pt"


def _known_folder(value_name: str, fallback: Path) -> Path:
    """Resolve a Windows user-shell folder while retaining a safe fallback."""

    if winreg is None:
        return fallback
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
    except OSError:
        return fallback
    return Path(os.path.expandvars(str(value))).expanduser()


def default_data_dir() -> Path:
    """Return the per-user application-data directory."""

    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / APP_NAME


def migrate_legacy_data_dir(data_dir: Path) -> str | None:
    """Move a pre-rename data directory to the new product name once.

    Returns ``None`` when there is nothing to do or the move succeeded, or a
    message describing why the move failed. A failed move leaves the legacy
    directory untouched and creates nothing, so the next launch retries it.
    After a successful move a directory junction keeps the legacy path
    working, so an older binary restored by a rollback still finds its data.
    """

    if os.name != "nt":
        return None
    legacy = data_dir.parent / LEGACY_APP_NAME
    if data_dir.exists() or data_dir.is_symlink():
        return None
    if not legacy.is_dir() or legacy.is_symlink():
        return None
    try:
        legacy.rename(data_dir)
    except OSError as exc:
        LOGGER.error("Could not migrate the legacy data directory", exc_info=True)
        return str(exc) or type(exc).__name__
    for child in sorted(data_dir.iterdir()):
        if not child.is_file() or child.is_symlink():
            continue
        if child.name.startswith(f"{LEGACY_APP_NAME.casefold()}."):
            suffix = child.name[len(LEGACY_APP_NAME) + 1 :]
            with suppress(OSError):
                child.rename(data_dir / f"{APP_NAME.casefold()}.{suffix}")
    _create_legacy_data_junction(legacy, data_dir)
    return None


def _create_legacy_data_junction(legacy: Path, target: Path) -> None:
    """Best-effort junction so pre-rename binaries still reach the data."""

    if legacy.exists() or legacy.is_symlink():
        return
    try:
        import _winapi

        _winapi.CreateJunction(str(target.resolve()), str(legacy))
    except Exception:  # pragma: no cover - compatibility nicety
        LOGGER.warning("Could not create the legacy data junction", exc_info=True)


def default_downloads_dir() -> Path:
    """Return the configured Windows Downloads known folder."""

    return _known_folder(DOWNLOADS_GUID, Path.home() / "Downloads")


def default_documents_dir() -> Path:
    """Return the configured Windows Documents known folder."""

    return _known_folder("Personal", Path.home() / "Documents")


@dataclass(slots=True)
class AppConfig:
    """Persistent application settings."""

    data_dir: Path = field(default_factory=default_data_dir)
    university_root: Path = field(default_factory=lambda: default_documents_dir() / "Universidade")
    downloads_dir: Path = field(default_factory=default_downloads_dir)
    allowed_extensions: tuple[str, ...] = DEFAULT_EXTENSIONS
    minimum_file_size: int = 512
    watch_enabled: bool = True
    launch_at_login: bool = False
    prompt_timeout_seconds: int = 45
    prompt_timeout_enabled: bool = False
    reminder_lead_days: int = 2
    filename_template: str = DEFAULT_FILENAME_TEMPLATE
    theme: str = DEFAULT_THEME
    language: str = DEFAULT_LANGUAGE
    check_updates_on_launch: bool = True
    ocr_enabled: bool = True
    quiet_intake: bool = False
    initialized: bool = False

    @property
    def settings_path(self) -> Path:
        """Path to the JSON settings file."""

        return self.data_dir / "settings.json"

    @property
    def database_path(self) -> Path:
        """Path to the local SQLite database."""

        return self.data_dir / "sortinator.db"

    @property
    def log_path(self) -> Path:
        """Path to the rotating application log."""

        return self.data_dir / "sortinator.log"

    @property
    def updates_dir(self) -> Path:
        """Directory holding update transaction state and results (never serialized)."""

        return self.data_dir / "updates"

    @property
    def inbox_dir(self) -> Path:
        """Folder holding downloaded files awaiting classification."""

        return self.university_root / "_Caixa de Entrada"

    def ensure_directories(self) -> None:
        """Create application and university directories if absent."""

        self.validate()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.university_root.mkdir(parents=True, exist_ok=True)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        """Reject settings that could cause the watcher to reprocess its own files."""

        # Imported lazily: organizador.i18n depends on this module.
        from organizador.i18n import _

        downloads = _resolve_managed_folder(self.downloads_dir, "Downloads")
        university = _resolve_managed_folder(self.university_root, "Universidade")
        try:
            data_dir = self.data_dir.resolve()
        except (OSError, RuntimeError) as exc:
            raise ValueError(_("A pasta de dados da aplicação não pôde ser validada.")) from exc
        if _paths_overlap(university, downloads):
            raise ValueError(
                _(
                    "As pastas Universidade e Downloads não podem coincidir nem "
                    "ficar uma dentro da outra."
                )
            )
        if _paths_overlap(university, data_dir) or _paths_overlap(downloads, data_dir):
            raise ValueError(
                _(
                    "As pastas Universidade e Downloads não podem coincidir nem "
                    "ficar dentro da pasta de dados da aplicação."
                )
            )
        if self.minimum_file_size < 0:
            raise ValueError(_("O tamanho mínimo não pode ser negativo."))
        if self.prompt_timeout_seconds < 10:
            raise ValueError(_("O tempo do popup deve ser de pelo menos 10 segundos."))
        if not 0 <= self.reminder_lead_days <= 30:
            raise ValueError(_("O aviso de prazos deve estar entre 0 e 30 dias."))
        _validate_name_template(self.filename_template)
        if self.theme not in THEME_IDS:
            raise ValueError(_("O tema escolhido não existe: {theme}").format(theme=self.theme))
        if self.language not in LANGUAGE_IDS:
            raise ValueError(
                _("O idioma escolhido não existe: {language}").format(language=self.language)
            )

    def accepts(self, path: Path) -> bool:
        """Return whether a file has an eligible, non-temporary suffix."""

        lowered = path.name.casefold()
        if any(lowered.endswith(suffix) for suffix in TEMPORARY_SUFFIXES):
            return False
        return path.suffix.casefold() in self.allowed_extensions

    def save(self) -> None:
        """Persist settings atomically to avoid a partially written JSON file."""

        self.validate()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        payload["data_dir"] = str(self.data_dir)
        payload["university_root"] = str(self.university_root)
        payload["downloads_dir"] = str(self.downloads_dir)
        payload["allowed_extensions"] = list(self.allowed_extensions)
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=self.data_dir, prefix="settings-", suffix=".tmp", text=True
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                handle.write(text)
            Path(temporary_name).replace(self.settings_path)
        finally:
            Path(temporary_name).unlink(missing_ok=True)

    @classmethod
    def load(cls, data_dir: Path | None = None) -> AppConfig:
        """Load settings, returning defaults before first launch."""

        target_dir = data_dir or default_data_dir()
        settings_path = target_dir / "settings.json"
        if not settings_path.exists():
            return cls(data_dir=target_dir)
        try:
            decoded: Any = json.loads(settings_path.read_text(encoding="utf-8"))
            if not isinstance(decoded, dict):
                raise TypeError("o conteúdo deve ser um objeto JSON")
            raw: dict[str, Any] = decoded
            if "data_dir" in raw and not isinstance(raw["data_dir"], str):
                raise TypeError("data_dir deve ser texto")
            extensions_value = raw.get("allowed_extensions", [])
            if not isinstance(extensions_value, list) or not all(
                isinstance(value, str) for value in extensions_value
            ):
                raise TypeError("allowed_extensions deve ser uma lista de textos")
            extensions = tuple(_normalise_extension(value) for value in extensions_value)
            config = cls(
                data_dir=target_dir,
                university_root=_path_setting(
                    raw,
                    "university_root",
                    default_documents_dir() / "Universidade",
                ),
                downloads_dir=_path_setting(raw, "downloads_dir", default_downloads_dir()),
                allowed_extensions=extensions or DEFAULT_EXTENSIONS,
                minimum_file_size=_int_setting(raw, "minimum_file_size", 512),
                watch_enabled=_bool_setting(raw, "watch_enabled", True),
                launch_at_login=_bool_setting(raw, "launch_at_login", False),
                prompt_timeout_seconds=_int_setting(raw, "prompt_timeout_seconds", 45),
                prompt_timeout_enabled=_bool_setting(raw, "prompt_timeout_enabled", False),
                reminder_lead_days=_int_setting(raw, "reminder_lead_days", 2),
                filename_template=_str_setting(raw, "filename_template", DEFAULT_FILENAME_TEMPLATE),
                theme=_str_setting(raw, "theme", DEFAULT_THEME),
                language=_str_setting(raw, "language", DEFAULT_LANGUAGE),
                check_updates_on_launch=_bool_setting(raw, "check_updates_on_launch", True),
                ocr_enabled=_bool_setting(raw, "ocr_enabled", True),
                quiet_intake=_bool_setting(raw, "quiet_intake", False),
                initialized=_bool_setting(raw, "initialized", False),
            )
            config.validate()
            return config
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Não foi possível ler as definições em {settings_path}: {exc}"
            ) from exc


def _normalise_extension(value: str) -> str:
    """Normalise one user-entered file extension."""

    cleaned = re.sub(r"\s+", "", value.casefold())
    if not cleaned:
        return ""
    return cleaned if cleaned.startswith(".") else f".{cleaned}"


def _resolve_managed_folder(path: Path, label: str) -> Path:
    # Imported lazily: organizador.i18n depends on this module.
    from organizador.i18n import _

    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError(
            _("A pasta {label} tem de ser um caminho absoluto e não pode estar vazia.").format(
                label=label
            )
        )
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(_("A pasta {label} não pôde ser validada.").format(label=label)) from exc
    if resolved.parent == resolved:
        raise ValueError(_("A pasta {label} não pode ser a raiz do disco.").format(label=label))
    return resolved


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def _path_setting(raw: dict[str, Any], key: str, default: Path) -> Path:
    if key not in raw:
        return default
    value = raw[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} deve ser texto")
    return Path(value).expanduser()


def _int_setting(raw: dict[str, Any], key: str, default: int) -> int:
    if key not in raw:
        return default
    value = raw[key]
    if type(value) is not int:
        raise TypeError(f"{key} deve ser um número inteiro")
    return value


def _str_setting(raw: dict[str, Any], key: str, default: str) -> str:
    if key not in raw:
        return default
    value = raw[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} deve ser texto")
    return value


def _validate_name_template(template: str) -> None:
    # Imported lazily: organizador.i18n depends on this module.
    from organizador.i18n import _

    cleaned = template.strip()
    if not cleaned:
        raise ValueError(_("O modelo do nome não pode estar vazio."))
    if len(cleaned) > 120:
        raise ValueError(_("O modelo do nome é demasiado longo (máximo 120 caracteres)."))
    if cleaned.count("{") != cleaned.count("}"):
        raise ValueError(_("O modelo do nome tem chaves por fechar."))
    for token in re.findall(r"\{[^{}]*\}", cleaned):
        if token not in NAME_TEMPLATE_TOKENS:
            raise ValueError(_("Token desconhecido no modelo do nome: {token}").format(token=token))


def _bool_setting(raw: dict[str, Any], key: str, default: bool) -> bool:
    if key not in raw:
        return default
    value = raw[key]
    if not isinstance(value, bool):
        raise TypeError(f"{key} deve ser verdadeiro ou falso")
    return value


def parse_extensions(value: str) -> tuple[str, ...]:
    """Parse comma, semicolon or whitespace-separated extensions."""

    extensions = {_normalise_extension(item) for item in re.split(r"[,;\s]+", value)}
    extensions.discard("")
    return tuple(sorted(extensions))
