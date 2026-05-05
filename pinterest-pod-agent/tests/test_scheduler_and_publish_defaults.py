from types import SimpleNamespace
import asyncio
from pathlib import Path

import pytest

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.automation.pinterest_flow import PinDraft, PinterestFlow, PinterestFlowError
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

        async def _upload_file_with_retry(self, image_path: Path) -> None:
            await self._set_file_input(image_path)
            await self.wait_until_uploaded()

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

        async def wait_until_published(self) -> dict[str, object]:
            return {
                "success_signal": True,
                "success_source": "pin_url",
                "pin_url": "https://www.pinterest.com/pin/123/",
                "final_url": "https://www.pinterest.com/pin/123/",
            }

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


def test_publish_pin_accepts_success_signal_without_pin_url(monkeypatch) -> None:
    image_path = Path("unused-pin.png")
    monkeypatch.setattr(Path, "exists", lambda self: True)

    class Flow(PinterestFlow):
        def __init__(self) -> None:
            self.page = SimpleNamespace(set_default_timeout=lambda _: None)

        async def _open_pin_creator(self) -> None:
            return None

        async def _upload_file_with_retry(self, image_path: Path) -> None:
            return None

        async def _fill_title(self, title: str) -> None:
            return None

        async def _fill_description(self, description: str) -> None:
            return None

        async def _select_board(self, board_name: str, *, create_if_missing: bool) -> None:
            return None

        async def _ensure_on_creator(self, context: str = "") -> None:
            return None

        async def _validate_current_draft(self, draft: PinDraft) -> None:
            return None

        async def _click_publish_button(self) -> None:
            return None

        async def wait_until_published(self) -> dict[str, object]:
            return {
                "success_signal": True,
                "success_source": "Your Pin was published",
                "pin_url": None,
                "final_url": "https://www.pinterest.com/pin-creation-tool/",
            }

        async def save_debug_artifacts(self, label: str) -> Path:
            raise AssertionError(label)

    result = asyncio.run(
        Flow().publish_pin(
            PinDraft(
                title="Title",
                description="Description",
                board_name="Board",
                image_path=image_path,
            )
        )
    )

    assert result.success is True
    assert result.pin_url is None
    assert result.publish_evidence["success_signal"] is True


def test_publish_pin_rejects_draft_only_result(monkeypatch) -> None:
    image_path = Path("unused-pin.png")
    monkeypatch.setattr(Path, "exists", lambda self: True)

    class Flow(PinterestFlow):
        def __init__(self) -> None:
            self.page = SimpleNamespace(set_default_timeout=lambda _: None)

        async def _open_pin_creator(self) -> None:
            return None

        async def _upload_file_with_retry(self, image_path: Path) -> None:
            return None

        async def _fill_title(self, title: str) -> None:
            return None

        async def _fill_description(self, description: str) -> None:
            return None

        async def _select_board(self, board_name: str, *, create_if_missing: bool) -> None:
            return None

        async def _ensure_on_creator(self, context: str = "") -> None:
            return None

        async def _validate_current_draft(self, draft: PinDraft) -> None:
            return None

        async def _click_publish_button(self) -> None:
            return None

        async def wait_until_published(self) -> dict[str, object]:
            return {
                "success_signal": False,
                "success_source": None,
                "pin_url": None,
                "final_url": "https://www.pinterest.com/pin-creation-tool/",
            }

        async def save_debug_artifacts(self, label: str) -> Path:
            return Path(".")

    with pytest.raises(PinterestFlowError):
        asyncio.run(
            Flow().publish_pin(
                PinDraft(
                    title="Title",
                    description="Description",
                    board_name="Board",
                    image_path=image_path,
                )
            )
        )


def test_wait_until_published_uses_success_text_without_pin_url() -> None:
    class Page:
        url = "https://www.pinterest.com/pin-creation-tool/"

        async def wait_for_load_state(self, *args, **kwargs) -> None:
            return None

        async def wait_for_url(self, *args, **kwargs) -> None:
            raise PlaywrightTimeoutError("timeout")

        def set_default_timeout(self, timeout: int) -> None:
            return None

    class Flow(PinterestFlow):
        async def _extract_created_pin_url(self) -> str | None:
            return None

        async def _detect_publish_success_signal(self) -> str | None:
            return "Your Pin was published"

    evidence = asyncio.run(Flow(Page()).wait_until_published())

    assert evidence == {
        "success_signal": True,
        "success_source": "Your Pin was published",
        "pin_url": None,
        "final_url": "https://www.pinterest.com/pin-creation-tool/",
    }


def test_upload_file_with_retry_retries_once() -> None:
    class Page:
        def set_default_timeout(self, timeout: int) -> None:
            return None

        async def wait_for_timeout(self, timeout: int) -> None:
            return None

    class Flow(PinterestFlow):
        def __init__(self) -> None:
            super().__init__(Page())
            self.attempts = 0

        async def _set_file_input(self, image_path: Path) -> None:
            self.attempts += 1

        async def wait_until_uploaded(self) -> None:
            raise RuntimeError("upload_failed")

    flow = Flow()

    with pytest.raises(RuntimeError, match="upload_failed after retry"):
        asyncio.run(flow._upload_file_with_retry(Path("unused.png")))

    assert flow.attempts == 2


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
