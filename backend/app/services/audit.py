"""Riwayat perubahan yang tidak bisa diubah diam-diam (hash chain).

Setiap kejadian penting (kebun didaftarkan, batas disahkan, status diputuskan, paket ekspor dibuat)
dicatat beserta pelakunya. Hash setiap baris dihitung dari isi baris + hash baris sebelumnya,
seperti buku besar: mengubah atau menghapus satu baris di tengah membuat seluruh rantai sesudahnya
tidak cocok, dan `verify_chain` menunjukkan di mana rantai putus.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditEvent

GENESIS = "0" * 64


def _digest(prev: str, at: datetime, actor: str, role: str, action: str, entity: str, entity_id: int | None,
            summary: str, data: Any) -> str:
    body = json.dumps(
        {"at": at.isoformat(timespec="seconds"), "actor": actor, "role": role, "action": action, "entity": entity,
         "entity_id": entity_id, "summary": summary, "data": data},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str,
    )
    return hashlib.sha256((prev + body).encode("utf-8")).hexdigest()


def log(db: Session, actor: str, role: str, action: str, entity: str, entity_id: int | None, summary: str,
        data: dict | None = None, at: datetime | None = None) -> AuditEvent:
    at = (at or datetime.now()).replace(microsecond=0)
    last = db.scalar(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1))
    prev = last.hash if last else GENESIS
    ev = AuditEvent(at=at, actor=actor, role=role, action=action, entity=entity, entity_id=entity_id,
                    summary=summary[:300], data=data, prev_hash=prev,
                    hash=_digest(prev, at, actor, role, action, entity, entity_id, summary[:300], data))
    db.add(ev)
    db.flush()
    return ev


def log_user(db: Session, user, action: str, entity: str, entity_id: int | None, summary: str,
             data: dict | None = None) -> AuditEvent:
    return log(db, user.display_name if user else "sistem", user.role if user else "sistem", action, entity,
               entity_id, summary, data)


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    n = 0
    for ev in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        n += 1
        expect = _digest(prev, ev.at, ev.actor, ev.role, ev.action, ev.entity, ev.entity_id, ev.summary, ev.data)
        if ev.prev_hash != prev or ev.hash != expect:
            return {"ok": False, "events": n, "broken_at": ev.id,
                    "message": f"Rantai riwayat tidak cocok mulai kejadian #{ev.id}: ada data yang diubah atau dihapus."}
        prev = ev.hash
    return {"ok": True, "events": n, "broken_at": None, "head": prev,
            "message": f"{n} kejadian tercatat, rantai hash utuh."}


def event_dict(ev: AuditEvent) -> dict:
    return {"id": ev.id, "at": ev.at.isoformat(timespec="seconds"), "actor": ev.actor, "role": ev.role,
            "action": ev.action, "entity": ev.entity, "entity_id": ev.entity_id, "summary": ev.summary,
            "hash": ev.hash[:12]}


def for_entity(db: Session, entity: str, entity_id: int, limit: int = 50) -> list[dict]:
    rows = db.scalars(select(AuditEvent).where(AuditEvent.entity == entity, AuditEvent.entity_id == entity_id)
                      .order_by(AuditEvent.id.desc()).limit(limit))
    return [event_dict(e) for e in rows]
