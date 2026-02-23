import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

PRIORITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
STATUS_EMOJI = {"todo": "📋", "in_progress": "🔄", "done": "✅", "cancelled": "❌"}


@dataclass
class Ticket:
    id: str
    title: str
    description: str = ""
    status: str = "todo"
    priority: str = "medium"
    due_date: Optional[str] = None
    created: str = ""
    updated: str = ""
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        now = datetime.now().isoformat(timespec="seconds")
        self.created = self.created or now
        self.updated = self.updated or now

    def to_task_line(self) -> str:
        cb = "[x]" if self.status == "done" else "[ ]"
        parts = [f"- {cb} {self.title}"]
        if self.due_date:
            parts.append(f"📅 {self.due_date}")
        if self.status == "done":
            parts.append(f"✅ {date.today().isoformat()}")
        return " ".join(parts)

    def to_meta_line(self) -> str:
        meta = f"id:{self.id}"
        if self.priority != "medium":
            meta += f" p:{self.priority}"
        return f"%%{meta}%%"


class ObsidianVault:
    _RE_TASK = re.compile(r"^\s*-\s+\[([ xX])\]\s+(.*)")
    _RE_META = re.compile(r"%%id:(T-[\w-]+)(?:\s+p:(\w+))?%%")
    _RE_DUE = re.compile(r"📅\s*(\d{4}-\d{2}-\d{2})")
    _RE_DONE = re.compile(r"✅\s*(\d{4}-\d{2}-\d{2})")

    def __init__(self, vault_path: str, inbox_dir: str = "Входящие"):
        self.vault_path = Path(vault_path)
        self.inbox_path = self.vault_path / inbox_dir
        self.inbox_path.mkdir(parents=True, exist_ok=True)

    def _daily_path(self, dt: Optional[date] = None) -> Path:
        return self.inbox_path / f"{(dt or date.today()).isoformat()}.md"

    def _ensure_daily(self, dt: Optional[date] = None) -> Path:
        path = self._daily_path(dt)
        if not path.exists():
            path.touch()
        return path

    def _parse_task_at(self, lines: List[str], i: int) -> Optional[dict]:
        m = self._RE_TASK.match(lines[i])
        if not m:
            return None

        if i + 1 >= len(lines):
            return None
        meta_m = self._RE_META.search(lines[i + 1])
        if not meta_m:
            return None

        done = m.group(1).lower() == "x"
        body = m.group(2)
        due_m = self._RE_DUE.search(body)

        title = body
        for rx in (self._RE_DUE, self._RE_DONE):
            title = rx.sub("", title)
        title = re.sub(r"\s{2,}", " ", title).strip()

        return dict(
            id=meta_m.group(1),
            title=title,
            done=done,
            priority=meta_m.group(2) or "medium",
            due_date=due_m.group(1) if due_m else None,
        )

    def _scan_all(self) -> List[Ticket]:
        tickets: List[Ticket] = []
        for fp in sorted(self.inbox_path.glob("*.md")):
            lines = fp.read_text(encoding="utf-8").split("\n")
            i = 0
            while i < len(lines):
                info = self._parse_task_at(lines, i)
                if info:
                    tickets.append(
                        Ticket(
                            id=info["id"],
                            title=info["title"],
                            status="done" if info["done"] else "todo",
                            priority=info["priority"],
                            due_date=info["due_date"],
                        )
                    )
                    i += 2  # задача + мета
                else:
                    i += 1
        return tickets

    # ── CRUD ──

    def create_ticket(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        due_date: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Ticket:
        tid = f"T-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:4]}"
        ticket = Ticket(
            id=tid,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date or date.today().isoformat(),
            tags=tags or [],
        )

        fp = self._ensure_daily()
        content = fp.read_text(encoding="utf-8")
        if content and not content.endswith("\n"):
            content += "\n"
        content += ticket.to_task_line() + "\n"
        content += ticket.to_meta_line() + "\n"
        fp.write_text(content, encoding="utf-8")

        logger.info("Created ticket %s: %s", tid, title)
        return ticket

    def get_all_tickets(self, status: Optional[str] = None) -> List[Ticket]:
        ts = self._scan_all()
        if status:
            ts = [t for t in ts if t.status == status]
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        ts.sort(key=lambda t: (order.get(t.priority, 2), t.due_date or "9999"))
        return ts

    def get_active_tickets(self) -> List[Ticket]:
        return [t for t in self.get_all_tickets() if t.status == "todo"]

    def get_today_tickets(self) -> List[Ticket]:
        today = date.today().isoformat()
        return [
            t
            for t in self.get_active_tickets()
            if not t.due_date or t.due_date <= today
        ]

    def get_overdue_tickets(self) -> List[Ticket]:
        today = date.today().isoformat()
        return [
            t for t in self.get_active_tickets() if t.due_date and t.due_date < today
        ]

    def _mutate(self, tid: str, fn: Callable) -> bool:
        for fp in self.inbox_path.glob("*.md"):
            lines = fp.read_text(encoding="utf-8").split("\n")
            for i in range(len(lines)):
                info = self._parse_task_at(lines, i)
                if not info or info["id"] != tid:
                    continue
                ticket = Ticket(
                    id=info["id"],
                    title=info["title"],
                    status="done" if info["done"] else "todo",
                    priority=info["priority"],
                    due_date=info["due_date"],
                )
                fn(ticket, lines, i)
                fp.write_text("\n".join(lines), encoding="utf-8")
                return True
        return False

    def update_status(self, ticket_id: str, new_status: str) -> bool:
        def fn(t, lines, i):
            t.status = new_status
            lines[i] = t.to_task_line()

        ok = self._mutate(ticket_id, fn)
        if ok:
            logger.info("Ticket %s → %s", ticket_id, new_status)
        return ok

    def update_ticket(
        self,
        ticket_id: str,
        priority: Optional[str] = None,
        due_date: Optional[str] = None,
        description: Optional[str] = None,
    ) -> bool:
        def fn(t, lines, i):
            if priority:
                t.priority = priority
            if due_date:
                t.due_date = due_date
            lines[i] = t.to_task_line()
            if i + 1 < len(lines) and self._RE_META.search(lines[i + 1]):
                lines[i + 1] = t.to_meta_line()

        return self._mutate(ticket_id, fn)

    def delete_ticket(self, ticket_id: str) -> bool:
        def fn(t, lines, i):
            # сначала мета (i+1), потом задачу (i)
            if i + 1 < len(lines) and self._RE_META.search(lines[i + 1]):
                lines.pop(i + 1)
            lines.pop(i)

        ok = self._mutate(ticket_id, fn)
        if ok:
            logger.info("Deleted ticket %s", ticket_id)
        return ok

    def find_ticket(self, ticket_id: str) -> Optional[Ticket]:
        return next((t for t in self._scan_all() if t.id == ticket_id), None)

    @staticmethod
    def format_ticket_short(t: Ticket) -> str:
        p = PRIORITY_EMOJI.get(t.priority, "⚪")
        s = STATUS_EMOJI.get(t.status, "📋")
        due = f" | 📅 {t.due_date}" if t.due_date else ""
        return f"{s} {p} {t.title}\n   `{t.id}` | {t.priority}{due}"

    @staticmethod
    def format_ticket_full(t: Ticket) -> str:
        p = PRIORITY_EMOJI.get(t.priority, "⚪")
        s = STATUS_EMOJI.get(t.status, "📋")
        lines = [
            f"{s} {p} **{t.title}**",
            f"ID: `{t.id}`",
            f"Статус: {t.status} | Приоритет: {t.priority}",
        ]
        if t.due_date:
            lines.append(f"📅 Дедлайн: {t.due_date}")
        if t.tags:
            lines.append(f"🏷 Теги: {', '.join(t.tags)}")
        if t.description:
            lines.append(f"\n📝 {t.description}")
        lines.append(f"\n🕐 Создан: {t.created[:16]}")
        return "\n".join(lines)
