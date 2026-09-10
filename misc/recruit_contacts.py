"""Department contacts used in admission notifications."""

import json
from pathlib import Path

from fastapi import HTTPException


CONTACTS_FILE = Path(__file__).resolve().parents[1] / "config" / "recruitment.json"
DEPARTMENTS = {"office", "competition", "research", "activity"}


def get_minister_wechat(department: str) -> str:
    if department not in DEPARTMENTS:
        raise HTTPException(status_code=400, detail="请选择有效的录取部门")

    # Read for each admission so contact changes reach every worker immediately.
    try:
        data = json.loads(CONTACTS_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as error:
        raise HTTPException(
            status_code=503, detail="录取通知联系人配置不可用，请联系管理员检查配置文件"
        ) from error

    contacts = data.get("minister_wechat") if isinstance(data, dict) else None
    wechat = contacts.get(department) if isinstance(contacts, dict) else None
    if not isinstance(wechat, str) or not wechat.strip() or any(char.isspace() for char in wechat.strip()):
        raise HTTPException(
            status_code=503, detail="该部门部长微信号尚未正确配置，请联系管理员"
        )
    return wechat.strip()
