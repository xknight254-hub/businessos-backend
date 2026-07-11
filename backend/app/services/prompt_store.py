"""Prompt management (Phase 5 — M5.5).

DB-backed, versioned prompt templates. Creating a prompt with an
existing (business_id, key) bumps the version and deactivates the
prior active version, so prompts are editable + tracked.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Prompt
from app.core.database import get_session_factory


class PromptStore:
    def __init__(self, db: AsyncSession, business_id: str) -> None:
        self.db = db
        self.business_id = business_id

    async def create(
        self, *, key: str, title: str, template: str,
        model: str = "gpt-4o-mini", task: str = "insight",
    ) -> Prompt:
        # deactivate current active version for this key
        res = await self.db.execute(
            select(Prompt).where(
                Prompt.business_id == self.business_id,
                Prompt.key == key,
                Prompt.is_active == True,  # noqa: E712
            )
        )
        current = res.scalars().first()
        version = (current.version + 1) if current else 1
        if current:
            current.is_active = False
        prompt = Prompt(
            business_id=self.business_id, key=key, version=version,
            title=title, template=template, model=model, task=task,
            is_active=True,
        )
        self.db.add(prompt)
        await self.db.flush()
        return prompt

    async def get_active(self, key: str) -> Prompt | None:
        res = await self.db.execute(
            select(Prompt).where(
                Prompt.business_id == self.business_id,
                Prompt.key == key,
                Prompt.is_active == True,  # noqa: E712
            )
        )
        return res.scalars().first()

    async def list_(self) -> list[Prompt]:
        res = await self.db.execute(
            select(Prompt).where(Prompt.business_id == self.business_id)
            .order_by(Prompt.key, Prompt.version.desc())
        )
        return list(res.scalars().all())

    async def render(self, key: str, **kwargs: str) -> tuple[str, str, str]:
        """Return (template_text, model, task) for a key, rendered with kwargs."""
        p = await self.get_active(key)
        if not p:
            return ("", "gpt-4o-mini", "insight")
        return (p.template.format(**kwargs), p.model, p.task)
