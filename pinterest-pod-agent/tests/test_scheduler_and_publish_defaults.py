from types import SimpleNamespace
import asyncio
from pathlib import Path

import pytest

from app.automation.pinterest_flow import PinDraft, PinterestFlow
from app.celery_app import _build_beat_schedule
from app.evomap.prompt_evolve import PromptContext
from app.jobs import tasks
from app.workflows import warmup_flow


def test_beat_schedule_does_not_auto_dispatch_by_default(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.celery_app.settings",
        SimpleNamespace(
            scheduler_enabled=True,
            scheduler_auto_dispatch_enabled=False,
            publish_interval_minutes=30,
            scheduler_dry_run=False,
        ),
    )

    schedule = _build_beat_schedule()

    assert "reclaim-stale-tasks" in schedule
    assert "dispatch-publish-jobs" not in schedule


def test_beat_schedule_can_enable_auto_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.celery_app.settings",
        SimpleNamespace(
            scheduler_enabled=True,
            scheduler_auto_dispatch_enabled=True,
            publish_interval_minutes=30,
            scheduler_dry_run=False,
        ),
    )

    schedule = _build_beat_schedule()

    assert "dispatch-publish-jobs" in schedule
    assert schedule["dispatch-publish-jobs"]["kwargs"] == {"dry_run": False}


def test_generated_board_and_topics_have_fallbacks() -> None:
    context = PromptContext(
        product_type="t-shirt",
        niche="pet lovers",
        audience="dog moms",
        season="Mother's Day",
    )

    assert tasks._clean_generated_board("", context) == "Pet Lovers"
    assert tasks._clean_generated_topics([], context) == [
        "Pet Lovers",
        "T-Shirt",
        "Mother'S Day",
        "Gift Ideas",
        "Pinterest Finds",
    ]


def test_publish_pin_skips_tagged_topics(monkeypatch) -> None:
    image_path = Path("unused-pin.png")
    monkeypatch.setattr(Path, "exists", lambda self: True)
    calls: list[str] = []

    class Flow(PinterestFlow):
        def __init__(self) -> None:
            self.page = SimpleNamespace(set_default_timeout=lambda _: None)

        async def _open_pin_creator(self) -> None:
            calls.append("open")

        async def _set_file_input(self, image_path: Path) -> None:
            calls.append("upload")

        async def wait_until_uploaded(self) -> None:
            calls.append("uploaded")

        async def _fill_title(self, title: str) -> None:
            calls.append("title")

        async def _fill_description(self, description: str) -> None:
            calls.append("description")

        async def _select_board(self, board_name: str, *, create_if_missing: bool) -> None:
            calls.append("board")

        async def _ensure_on_creator(self, context: str = "") -> None:
            calls.append("ensure")

        async def _fill_tagged_topics(self, topics: list[str]) -> None:
            calls.append("tagged")

        async def _validate_current_draft(self, draft: PinDraft) -> None:
            calls.append("validate")

        async def _click_publish_button(self) -> None:
            calls.append("publish")

        async def wait_until_published(self) -> str | None:
            return "https://www.pinterest.com/pin/123/"

        async def save_debug_artifacts(self, label: str) -> Path:
            raise AssertionError(label)

    draft = PinDraft(
        title="Title",
        description="Description",
        board_name="Board",
        image_path=image_path,
        tagged_topics=["Pets", "Gifts"],
    )

    result = asyncio.run(Flow().publish_pin(draft))

    assert result.success is True
    assert "tagged" not in calls
    assert calls[-2:] == ["validate", "publish"]


def test_warmup_external_navigation_goes_back() -> None:
    class Page:
        def __init__(self) -> None:
            self.url = "https://www.amazon.com/dp/test"
            self.back_called = False
            self.goto_called = False

        async def go_back(self, **kwargs) -> None:
            self.back_called = True
            self.url = "https://www.pinterest.com/pin/123/"

        async def wait_for_timeout(self, timeout: int) -> None:
            return None

        async def goto(self, url: str, **kwargs) -> None:
            self.goto_called = True
            self.url = url

    page = Page()

    recovered = asyncio.run(warmup_flow._recover_if_external_navigation(page, context="test"))

    assert recovered is True
    assert page.back_called is True
    assert page.goto_called is False
    assert warmup_flow._is_pinterest_url(page.url)


def test_warmup_returns_to_pinterest_home_from_pin_detail() -> None:
    class Page:
        def __init__(self) -> None:
            self.url = "https://www.pinterest.com/pin/123/"

        async def goto(self, url: str, **kwargs) -> None:
            self.url = url

        async def wait_for_timeout(self, timeout: int) -> None:
            return None

    page = Page()

    asyncio.run(warmup_flow._return_to_pinterest_home(page))

    assert page.url == "https://www.pinterest.com/"
