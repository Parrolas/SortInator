"""Persistent, token-addressed Windows notifications for filed documents."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from xml.etree.ElementTree import Element, SubElement, tostring

from organizador.db import Database
from organizador.models import FiledDocument
from organizador.windows_shell import AUMID

LOGGER = logging.getLogger(__name__)
URI_PATTERN = re.compile(r"sortinator://notification/([0-9a-f]{32})\Z")
LIFETIME_SECONDS = 7 * 24 * 60 * 60


def notification_token(uri: str) -> str | None:
    match = URI_PATTERN.fullmatch(uri)
    return match.group(1) if match else None


def save_action(database: Database, documents: list[FiledDocument]) -> str:
    token = uuid4().hex
    targets = [(document.id, document.record_token) for document in documents]
    with database.connect() as connection:
        connection.execute("DELETE FROM notification_actions WHERE expires_at <= ?", (time.time(),))
        connection.execute(
            "INSERT INTO notification_actions VALUES (?, ?, ?)",
            (token, time.time() + LIFETIME_SECONDS, json.dumps(targets)),
        )
        connection.commit()
    return f"sortinator://notification/{token}"


def resolve_action(database: Database, uri: str) -> tuple[list[FiledDocument], bool]:
    """Return current matching records and whether any target is unavailable."""
    token = notification_token(uri)
    if token is None:
        return [], True
    with database.connect() as connection:
        row = connection.execute(
            "SELECT documents_json FROM notification_actions WHERE token = ? AND expires_at > ?",
            (token, time.time()),
        ).fetchone()
    if row is None:
        return [], True
    documents = []
    missing = False
    try:
        for file_id, record_token in json.loads(row[0]):
            document = database.get_file(file_id)
            if (
                document is not None
                and document.record_token == record_token
                and document.current_path.is_file()
            ):
                documents.append(document)
            else:
                missing = True
    except (ValueError, TypeError):
        LOGGER.warning("Invalid local notification record")
        return [], True
    return documents, missing


def toast_xml(title: str, message: str, uri: str) -> str:
    if notification_token(uri) is None:
        raise ValueError("Invalid notification URI")
    root = Element("toast", {"activationType": "protocol", "launch": uri})
    binding = SubElement(SubElement(root, "visual"), "binding", {"template": "ToastGeneric"})
    SubElement(binding, "text").text = title
    SubElement(binding, "text").text = message
    return tostring(root, encoding="unicode")


def show_toast(title: str, message: str, uri: str) -> bool:
    """Send an OS-owned notification; activation is independent of this process."""
    try:
        from winrt.windows.data.xml.dom import XmlDocument
        from winrt.windows.ui.notifications import ToastNotification, ToastNotificationManager

        xml = XmlDocument()
        xml.load_xml(toast_xml(title, message, uri))
        toast = ToastNotification(xml)
        toast.expiration_time = datetime.now(UTC) + timedelta(seconds=LIFETIME_SECONDS)
        token = notification_token(uri)
        assert token is not None
        toast.tag = token[:16]
        toast.group = "filed"
        ToastNotificationManager.create_toast_notifier_with_id(AUMID).show(toast)
        return True
    except Exception:
        LOGGER.warning("Native notification unavailable; using tray fallback", exc_info=True)
        return False
