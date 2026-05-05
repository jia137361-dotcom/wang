from __future__ import annotations

import logging
import json
from dataclasses import asdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from app.automation.ui_decision_agent import UIDecisionAgent, UIDecisionError


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PinterestCredentials:
    email: str
    password: str


@dataclass(frozen=True)
class PinDraft:
    title: str
    description: str
    board_name: str
    image_path: Path
    destination_url: str | None = None
    alt_text: str | None = None
    tagged_topics: list[str] | None = None
    create_board_if_missing: bool = True


@dataclass(frozen=True)
class PublishResult:
    success: bool
    pin_url: str | None = None
    message: str = ""
    debug_artifact_dir: str | None = None
    pin_performance_id: int | None = None


class PinterestFlowError(RuntimeError):
    def __init__(self, message: str, *, debug_artifact_dir: str | None = None) -> None:
        super().__init__(message)
        self.debug_artifact_dir = debug_artifact_dir


class PinterestFlow:
    """Regular Pinterest login and Pin publishing flow.

    This class intentionally avoids anti-detection, fingerprint spoofing, and
    account-warming behavior. It assumes company-owned, authorized accounts.
    """

    def __init__(
        self,
        page: Page,
        *,
        default_timeout_ms: int = 30_000,
        debug_dir: str | Path = "var/debug/pinterest",
    ) -> None:
        self.page = page
        self.default_timeout_ms = default_timeout_ms
        self.debug_dir = Path(debug_dir)
        self.page.set_default_timeout(default_timeout_ms)
        self.ui_decision_agent = UIDecisionAgent()
        self.ai_decision_log_path: Path | None = None

    @classmethod
    async def from_browser(cls, browser: Browser, *, storage_state_path: str | None = None) -> "PinterestFlow":
        context_kwargs = {"storage_state": storage_state_path} if storage_state_path else {}
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        return cls(page)

    @property
    def context(self) -> BrowserContext:
        return self.page.context

    async def login(self, credentials: PinterestCredentials) -> None:
        try:
            logger.info("Opening Pinterest login page")
            await self.page.goto("https://www.pinterest.com/login/", wait_until="domcontentloaded")

            if await self._is_logged_in():
                logger.info("Pinterest session is already authenticated")
                return

            await self._fill_first_available(
                [
                    "input[type='email']",
                    "input[name='id']",
                    "input[name='email']",
                    "input[autocomplete='username']",
                ],
                credentials.email,
            )
            await self._fill_first_available(
                [
                    "input[type='password']",
                    "input[name='password']",
                    "input[autocomplete='current-password']",
                ],
                credentials.password,
            )
            await self._click_first_available(
                [
                    "button[type='submit']",
                    "button:has-text('Log in')",
                    "button:has-text('Log In')",
                ]
            )

            try:
                await self.page.wait_for_url("**/homefeed/**", timeout=self.default_timeout_ms)
            except PlaywrightTimeoutError:
                if not await self._is_logged_in():
                    raise

            logger.info("Pinterest login completed")
        except Exception as exc:
            artifact_dir = await self.save_debug_artifacts("login_failed")
            raise PinterestFlowError("Pinterest login failed", debug_artifact_dir=str(artifact_dir)) from exc

    async def save_storage_state(self, path: str | Path) -> None:
        await self.context.storage_state(path=str(path))

    async def create_board(self, board_name: str, *, secret: bool = False) -> None:
        try:
            await self.page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
            await self._click_first_available(
                [
                    "button:has-text('Create a board')",
                    "button:has-text('Create')",
                    "div[role='button']:has-text('Create')",
                    "[aria-label='Create']",
                ]
            )
            board_menu_item = self.page.get_by_text("Board", exact=True)
            if await board_menu_item.count():
                await board_menu_item.first.click()
            await self._fill_first_available(
                [
                    "input[name='name']",
                    "input[aria-label='Name']",
                    "input[placeholder*='Name' i]",
                    "input",
                ],
                board_name,
            )

            if secret:
                secret_toggle = self.page.get_by_label("Keep this board secret")
                if await secret_toggle.count():
                    await secret_toggle.check()

            await self._click_first_available(["button:has-text('Create')"])
            await self.page.wait_for_load_state("networkidle")
            logger.info("Pinterest board created", extra={"board_name": board_name})
        except Exception as exc:
            artifact_dir = await self.save_debug_artifacts("create_board_failed")
            raise PinterestFlowError("Pinterest board creation failed", debug_artifact_dir=str(artifact_dir)) from exc

    async def publish_pin(self, draft: PinDraft) -> PublishResult:
        if not draft.image_path.exists():
            raise FileNotFoundError(f"Pin image does not exist: {draft.image_path}")

        try:
            await self._open_pin_creator()
            await self._ai_handle_interruptions(
                stage="after_open_creator",
                objective="continue creating a Pinterest pin without installing extensions or changing account settings",
            )

            await self._ai_handle_interruptions(stage="before_upload", objective="upload the Pin image")
            await self._set_file_input(draft.image_path)
            await self.wait_until_uploaded()
            await self._ai_handle_interruptions(stage="after_upload", objective="continue filling the Pin form")

            await self._ai_handle_interruptions(stage="before_fill_title", objective="fill the Pin title")
            await self._fill_title(draft.title)
            await self._ai_handle_interruptions(stage="after_fill_title", objective="continue filling the Pin form")

            await self._fill_description(draft.description)
            await self._ai_handle_interruptions(stage="after_fill_description", objective="continue filling the Pin form")

            if draft.destination_url:
                await self._fill_destination_url(draft.destination_url)
                await self._ai_handle_interruptions(stage="after_fill_link", objective="continue filling the Pin form")

            # TODO: re-enable board selection after tagged topics fix is verified
            # await self._ai_handle_interruptions(stage="before_select_board", objective="select a Pinterest board")
            # await self._select_board(draft.board_name, create_if_missing=draft.create_board_if_missing)
            # await self._ensure_on_creator("after board selection")
            logger.info("Board selection skipped for tagged-topics debugging — board=%s", draft.board_name)

            if draft.alt_text:
                await self._fill_alt_text(draft.alt_text)

            # Tagged topics skipped — user fills manually
            # if draft.tagged_topics:
            #     await self._fill_tagged_topics(draft.tagged_topics)

            # Go straight to publish — skip AI interruptions here because the
            # agent sometimes clicks draft pins in the sidebar instead of the
            # publish button.
            await self._click_publish_button()
            pin_url = await self.wait_until_published()
            return PublishResult(success=True, pin_url=pin_url, message="Pin published")
        except Exception as exc:
            artifact_dir = await self.save_debug_artifacts("publish_pin_failed")
            raise PinterestFlowError("Pinterest pin publish failed", debug_artifact_dir=str(artifact_dir)) from exc

    async def _open_pin_creator(self) -> None:
        creator_urls = [
            "https://www.pinterest.com/pin-creation-tool/",
            "https://www.pinterest.com/pin-builder/",
        ]
        for url in creator_urls:
            await self.page.goto(url, wait_until="domcontentloaded")
            if await self._has_file_input(timeout_ms=20_000):
                await self._wait_for_creator_form()
                return
        await self.page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
        try:
            await self._open_pin_creator_from_create_menu()
            if await self._has_file_input(timeout_ms=20_000):
                await self._wait_for_creator_form()
                return
        except Exception:
            logger.info("Pinterest create menu entry failed after direct creator URLs", exc_info=True)
        raise RuntimeError("Pinterest pin creator did not expose an upload input")

    async def _open_pin_creator_from_create_menu(self) -> None:
        if "/pin/" in self.page.url:
            await self.page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
        await self._click_first_available(
            [
                "button[aria-label='Create']",
                "div[aria-label='Create']",
                "[data-test-id='create-button']",
                "[aria-label='Create']",
                "button:has-text('Create')",
                "div[role='button']:has-text('Create')",
            ]
        )
        await self._click_first_available(
            [
                "#Create-Pin",
                "a#Create-Pin",
                "a[href*='/pin-creation-tool/']",
                "div:has-text('Post your photos or videos')",
                "text=Post your photos or videos",
                "[role='menuitem']:has-text('Pin')",
                "div[role='button']:has-text('Pin')",
                "a:has-text('Pin')",
                "button:has-text('Pin')",
                "text=Pin",
            ]
        )
        try:
            await self.page.wait_for_url("**/pin-creation-tool/**", timeout=10_000)
        except PlaywrightTimeoutError:
            if "/pin/" in self.page.url:
                raise RuntimeError("Pinterest stayed on a Pin detail page after clicking Create Pin")

    async def _wait_for_creator_form(self) -> None:
        form_markers = [
            "text=Create Pin",
            "input[placeholder='Add a title']",
            "textarea[placeholder='Add a detailed description']",
            "text=Choose a file or drag and drop it here",
            "text=Choose a board",
        ]
        last_error: Exception | None = None
        for selector in form_markers:
            try:
                await self.page.locator(selector).first.wait_for(state="visible", timeout=5_000)
                return
            except Exception as exc:
                last_error = exc
        raise RuntimeError("Pinterest creator form did not become visible") from last_error

    async def wait_until_uploaded(self) -> None:
        try:
            await self.page.locator("text=Choose a file or drag and drop it here").wait_for(
                state="detached",
                timeout=20_000,
            )
        except PlaywrightTimeoutError:
            logger.info("Upload placeholder remained visible; continuing with form fill")
        await self.page.wait_for_timeout(1_000)

    async def wait_until_published(self) -> str | None:
        await self.page.wait_for_load_state("networkidle")
        try:
            await self.page.wait_for_url("**/pin/**", timeout=15_000)
        except PlaywrightTimeoutError:
            logger.info("Pin URL transition was not observed; trying result links")
        return await self._extract_created_pin_url()

    async def _ai_handle_interruptions(self, *, stage: str, objective: str) -> None:
        controls = await self.ui_decision_agent.collect_controls(self.page)
        if not self._should_ask_ai(controls):
            return

        decision = await self.ui_decision_agent.decide(
            stage=stage,
            objective=objective,
            controls=controls,
        )
        await self._append_ai_decision_log(stage=stage, objective=objective, controls=controls, decision=decision)
        try:
            handled = await self.ui_decision_agent.execute(self.page, decision, controls)
        except UIDecisionError as exc:
            artifact_dir = await self.save_debug_artifacts(f"ai_ui_decision_blocked_{stage}")
            await self._write_visible_controls(artifact_dir, controls)
            raise PinterestFlowError(
                f"AI UI decision blocked at {stage}: {exc}",
                debug_artifact_dir=str(artifact_dir),
            ) from exc

        if not handled or decision.action == "stop":
            artifact_dir = await self.save_debug_artifacts(f"ai_ui_decision_stopped_{stage}")
            await self._write_visible_controls(artifact_dir, controls)
            raise PinterestFlowError(
                f"AI UI decision stopped at {stage}: {decision.reason}",
                debug_artifact_dir=str(artifact_dir),
            )

    def _should_ask_ai(self, controls: list) -> bool:
        if not controls:
            return False
        dialog_controls = [control for control in controls if control.in_dialog]
        if dialog_controls:
            return True
        risky_overlay_text = " ".join(control.searchable_text for control in controls)
        return any(
            marker in risky_overlay_text
            for marker in [
                "install now",
                "allow notifications",
                "try it",
                "not now",
                "maybe later",
                "continue",
            ]
        )

    async def _append_ai_decision_log(self, *, stage: str, objective: str, controls: list, decision: object) -> None:
        path = self.ai_decision_log_path or (self.debug_dir / "ai_ui_decision.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "created_at": datetime.now(UTC).isoformat(),
            "stage": stage,
            "objective": objective,
            "url": self.page.url,
            "decision": asdict(decision),
            "controls": [asdict(control) for control in controls],
        }
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def _write_visible_controls(self, artifact_dir: Path, controls: list) -> None:
        (artifact_dir / "visible_controls.json").write_text(
            json.dumps([asdict(control) for control in controls], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def save_debug_artifacts(self, label: str) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        artifact_dir = self.debug_dir / f"{timestamp}_{label}"
        self.ai_decision_log_path = artifact_dir / "ai_ui_decision.jsonl"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        try:
            await self.page.screenshot(path=str(artifact_dir / "page.png"), full_page=True)
        except Exception:
            logger.exception("Failed to save Pinterest debug screenshot")
        try:
            (artifact_dir / "page.html").write_text(await self.page.content(), encoding="utf-8")
            (artifact_dir / "url.txt").write_text(self.page.url, encoding="utf-8")
        except Exception:
            logger.exception("Failed to save Pinterest debug HTML")
        return artifact_dir

    async def close(self) -> None:
        await self.context.close()

    async def _is_logged_in(self) -> bool:
        profile_selectors = [
            "[data-test-id='header-profile']",
            "a[href*='/settings/']",
            "button[aria-label='Accounts and more options']",
        ]
        for selector in profile_selectors:
            if await self.page.locator(selector).count():
                return True
        return False

    async def _set_file_input(self, image_path: Path) -> None:
        if "/pin/" in self.page.url and "pin-creation-tool" not in self.page.url and "pin-builder" not in self.page.url:
            raise RuntimeError("Refusing to upload while on a Pin detail page")
        file_input = self.page.locator("input[type='file']").first
        await file_input.wait_for(state="attached", timeout=15_000)
        await file_input.set_input_files(str(image_path))

    async def _fill_title(self, title: str) -> None:
        if len(title) > 100:
            logger.warning("Title truncated from %d to 100 chars", len(title))
            title = title[:100].strip()
        selectors = [
            "input[placeholder='Add a title']",
            "input[placeholder*='Add a title' i]",
            "[aria-label='Title'] input",
            "[data-test-id='pin-draft-title'] textarea",
            "[data-test-id='pin-draft-title'] [contenteditable='true']",
            "textarea[placeholder*='title' i]",
            "input[placeholder*='title' i]",
            "[contenteditable='true'][aria-label*='title' i]",
            "div[role='textbox'][aria-label*='title' i]",
        ]
        await self._fill_first_available(selectors, title)

    async def _fill_description(self, description: str) -> None:
        if len(description) > 800:
            # Try to truncate at the last sentence boundary within limit
            truncated = description[:800]
            for end_char in ('. ', '! ', '? ', '.\n', '!\n', '?\n', '.', '!', '?'):
                last = truncated.rfind(end_char)
                if last > 600:
                    truncated = truncated[:last + len(end_char.rstrip())]
                    break
            else:
                truncated = truncated.rstrip()
            logger.warning("Description truncated from %d to %d chars", len(description), len(truncated))
            description = truncated
        selectors = [
            "textarea[placeholder='Add a detailed description']",
            "textarea[placeholder*='detailed description' i]",
            "div[role='textbox'][aria-label='Description']",
            "[data-test-id='pin-draft-description'] textarea",
            "[data-test-id='pin-draft-description'] [contenteditable='true']",
            "textarea[placeholder*='description' i]",
            "[contenteditable='true'][aria-label*='description' i]",
            "div[role='textbox'][aria-label*='description' i]",
            "div[role='textbox']",
        ]
        await self._fill_first_available(selectors, description)

    async def _fill_destination_url(self, destination_url: str) -> None:
        selectors = [
            "input[placeholder='Add a link']",
            "input[placeholder*='Add a link' i]",
            "input[placeholder*='link' i]",
            "input[aria-label*='link' i]",
            "input[name='link']",
        ]
        await self._fill_first_available(selectors, destination_url)

    async def _ensure_on_creator(self, context: str = "") -> None:
        """Verify we are still on the pin creator; if not, navigate back to it."""
        if "/pin-creation-tool/" in self.page.url or "/pin-builder/" in self.page.url:
            return
        logger.warning("Left pin creator (%s) — url=%s, attempting recovery via go_back", context, self.page.url)
        await self.page.go_back()
        await self.page.wait_for_timeout(1500)
        if "/pin-creation-tool/" not in self.page.url and "/pin-builder/" not in self.page.url:
            raise RuntimeError(
                f"Left pin creator during {context} and could not recover (url={self.page.url})"
            )

    async def _fill_alt_text(self, alt_text: str) -> None:
        alt_button = self.page.get_by_role("button", name="Add alt text")
        if await alt_button.count():
            await alt_button.click()
            await self._fill_first_available(
                ["textarea[aria-label*='alt' i]", "textarea[placeholder*='alt' i]"],
                alt_text,
            )

    async def _fill_tagged_topics(self, topics: list[str]) -> None:
        """Fill tagged topics / interests on the Pin form.

        Pinterest may label the feature 'Topics', 'Tagged topics', or 'Interests'.
        If the toggle button cannot be found, the step is skipped rather than
        failing the entire publish.
        """
        # Try to click the toggle / expander for the topics section
        toggle_clicked = False
        for sel in [
            "button:has-text('Add topics')",
            "div[role='button']:has-text('Add topics')",
            "button:has-text('Topics')",
            "div[role='button']:has-text('Topics')",
            "[data-test-id='tag-selector'] button",
            "[data-test-id='tag-input-toggle']",
            "button:has-text('Tagged topics')",
            "div:has-text('Tagged topics')",
            "button:has-text('Interests')",
            "div:has-text('Interests')",
            "text=Topics",
        ]:
            try:
                loc = self.page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click()
                    toggle_clicked = True
                    await self.page.wait_for_timeout(1200)
                    break
            except Exception:
                continue

        if not toggle_clicked:
            logger.info("Tagged topics toggle not found — topics UI may already be visible, continuing")
            await self.page.wait_for_timeout(500)

        topic_input_selectors = [
            "input[placeholder*='topic' i]",
            "input[aria-label*='topic' i]",
            "input[placeholder*='interest' i]",
            "input[aria-label*='interest' i]",
            "input[placeholder*='Search' i]",
            "[data-test-id='topic-search'] input",
            "[data-test-id='tag-input'] input",
            "[data-test-id='tag-search'] input",
            "[role='combobox'][aria-label*='topic' i]",
            "[role='combobox'][aria-label*='interest' i]",
            "[role='combobox']",
        ]

        for topic in topics:
            if "/pin-creation-tool/" not in self.page.url and "/pin-builder/" not in self.page.url:
                logger.error("Navigated away from pin creator during tagged topics fill")
                break

            # Strategy A: search-type input (type + Enter to select from dropdown)
            try:
                await self._fill_first_available(topic_input_selectors, topic, timeout_ms=4000)
                await self.page.wait_for_timeout(1000)
                await self.page.keyboard.press("Enter")
                await self.page.wait_for_timeout(800)
                # Clear for next topic
                await self._clear_first_available(topic_input_selectors)
                logger.info("Tagged topic added via input: %s", topic)
                continue
            except Exception:
                pass

            # Strategy B: chip/button selection — click a suggested topic
            chip_selectors = [
                f"[role='option']:has-text('{topic}')",
                f"button:has-text('{topic}')",
                f"div[role='button']:has-text('{topic}')",
                f"span:has-text('{topic}'):near(:has-text('topic'))",
            ]
            selected = False
            for csel in chip_selectors:
                try:
                    chip = self.page.locator(csel).first
                    if await chip.count() > 0 and await chip.is_visible():
                        await chip.click()
                        await self.page.wait_for_timeout(800)
                        selected = True
                        logger.info("Tagged topic added via chip: %s", topic)
                        break
                except Exception:
                    continue

            if not selected:
                logger.warning(
                    "Could not fill tagged topic=%s — input and chip selectors both failed, continuing",
                    topic,
                )

    async def _clear_first_available(self, selectors: list[str]) -> None:
        """Clear the first matching input field."""
        for selector in selectors:
            try:
                locator = self.page.locator(selector).first
                if await locator.count() > 0:
                    await locator.clear()
                    return
            except Exception:
                continue

    async def _select_board(self, board_name: str, *, create_if_missing: bool) -> None:
        # Click the board selector — restrict to the pin creator form area so we
        # don't accidentally click draft pins in the sidebar.
        board_trigger_selectors = [
            "[data-test-id='board-dropdown-select-button']",
            "button[data-test-id*='board-selector']",
            "[data-test-id*='board-select'] button",
            "div[role='button']:has-text('Choose a board')",
            "button:has-text('Choose a board')",
            "button:has-text('Select a board')",
            "div[role='button']:has-text('Select a board')",
        ]
        # Try each selector; confirm the clicked element is inside the creator form
        clicked = False
        for sel in board_trigger_selectors:
            try:
                loc = self.page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    # Only click if this element is NOT inside a draft sidebar
                    if await loc.locator("..closest [data-test-id*='pinDraft']").count() == 0:
                        await loc.click()
                        clicked = True
                        break
            except Exception:
                continue

        if not clicked:
            # Last resort: try nearest match to the board section label
            try:
                board_label = self.page.locator("text=Board").first
                if await board_label.is_visible():
                    board_section = board_label.locator("..closest div")
                    btn = board_section.locator("button, [role='button']").first
                    if await btn.is_visible():
                        await btn.click()
                        clicked = True
            except Exception:
                pass

        if not clicked:
            logger.info("Board dropdown trigger not found — board may already be set, continuing")
            return

        # Wait for dropdown to render
        await self.page.wait_for_timeout(1500)
        if await self._click_board_option(board_name):
            return
        if not create_if_missing:
            raise RuntimeError(f"Pinterest board not found: {board_name}")
        await self._create_board_from_dropdown(board_name)
        await self._wait_for_dialog_closed()

    async def _click_board_option(self, board_name: str) -> bool:
        # Only match within board dropdown/menu, not sidebar drafts
        selectors = [
            f"[role='listbox'] [role='option']:has-text('{board_name}')",
            f"[role='menu'] [role='menuitem']:has-text('{board_name}')",
            f"[role='option']:has-text('{board_name}')",
            f"[role='menuitem']:has-text('{board_name}')",
            f"[data-test-id*='board-row']:has-text('{board_name}')",
            f"li:has-text('{board_name}')",
        ]
        for selector in selectors:
            locator = self.page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=3_000)
                await locator.click()
                return True
            except Exception:
                continue
        return False

    async def _create_board_from_dropdown(self, board_name: str) -> None:
        await self._click_first_available(
            [
                "button:has-text('Create board')",
                "button:has-text('Create a board')",
                "div[role='button']:has-text('Create board')",
                "div[role='button']:has-text('Create a board')",
                "text=Create board",
                "text=Create a board",
            ]
        )
        await self._fill_create_board_name(board_name)
        await self._click_create_board_submit()
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeoutError:
            logger.info("Board creation did not reach networkidle; continuing after modal submit")

    async def _fill_create_board_name(self, board_name: str) -> None:
        selectors = [
            "[role='dialog'] input[placeholder*='Places to Go' i]",
            "[role='dialog'] input[placeholder*='Recipes to Make' i]",
            "[role='dialog'] input[aria-label='Name']",
            "[role='dialog'] input[name='name']",
            "[role='dialog'] input",
            "input[placeholder*='Places to Go' i]",
            "input[placeholder*='Recipes to Make' i]",
        ]
        last_error: Exception | None = None
        for selector in selectors:
            locator = self.page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=5_000)
                try:
                    await locator.fill(board_name)
                except Exception:
                    await locator.click()
                    await self.page.keyboard.press("Control+A")
                    await self.page.keyboard.press("Backspace")
                    await self.page.keyboard.type(board_name)
                await self.page.wait_for_timeout(300)
                try:
                    value = await locator.input_value(timeout=1_000)
                except Exception:
                    value = ""
                if value.strip() == board_name:
                    return
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Could not fill Pinterest board name: {board_name}") from last_error

    async def _click_create_board_submit(self) -> None:
        dialog = self.page.locator("[role='dialog']").first
        try:
            create_button = dialog.get_by_role("button", name="Create", exact=True)
            await create_button.wait_for(state="visible", timeout=5_000)
            for _ in range(20):
                if await create_button.is_enabled():
                    await create_button.click()
                    return
                await self.page.wait_for_timeout(250)
        except Exception as exc:
            last_error: Exception | None = exc
        else:
            last_error = None

        if await self._click_enabled_control_in_dialog("Create"):
            return

        selectors = [
            "[role='dialog'] [data-test-id='create-board-submit-button']",
            "[role='dialog'] button:has-text('Create')",
            "[role='dialog'] div[role='button']:has-text('Create')",
        ]
        for selector in selectors:
            locator = self.page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=5_000)
                for _ in range(20):
                    try:
                        if await locator.is_enabled():
                            await locator.click()
                            return
                    except Exception:
                        await locator.click()
                        return
                    await self.page.wait_for_timeout(250)
                await locator.click()
                return
            except Exception as exc:
                last_error = exc
        try:
            await dialog.press("Enter", timeout=2_000)
            return
        except Exception as exc:
            last_error = exc
        raise RuntimeError("Could not submit Pinterest board creation dialog") from last_error

    async def _wait_for_dialog_closed(self) -> None:
        try:
            await self.page.locator("[role='dialog']").first.wait_for(state="hidden", timeout=10_000)
        except PlaywrightTimeoutError:
            logger.info("Pinterest dialog did not close quickly; continuing")

    async def _click_enabled_control_in_dialog(self, text: str) -> bool:
        """Click a visible enabled control inside the active dialog by text.

        Pinterest often changes data-test-id values. This helper lets the
        automation make a bounded decision from the live DOM without clicking
        outside the modal.
        """
        controls = self.page.locator(
            f"[role='dialog'] button:has-text('{text}'), "
            f"[role='dialog'] [role='button']:has-text('{text}')"
        )
        count = await controls.count()
        for index in range(count):
            control = controls.nth(index)
            try:
                if not await control.is_visible():
                    continue
                aria_disabled = await control.get_attribute("aria-disabled")
                disabled = await control.get_attribute("disabled")
                if aria_disabled == "true" or disabled is not None:
                    continue
                try:
                    if not await control.is_enabled():
                        continue
                except Exception:
                    pass
                await control.click()
                return True
            except Exception:
                continue
        return False

    async def _click_publish_button(self) -> None:
        # Ensure we are still on the pin creator before attempting publish
        if "/pin-creation-tool/" not in self.page.url and "/pin-builder/" not in self.page.url:
            raise RuntimeError(f"Cannot click publish — left pin creator (url={self.page.url})")

        selectors = [
            "button:has-text('Publish')",
            "div[role='button']:has-text('Publish')",
            "[data-test-id='publish-button']",
            "[data-test-id='submit-pin']",
            "button:has-text('Create')",
            "div[role='button']:has-text('Create')",
            "button:has-text('Save')",
            "div[role='button']:has-text('Save')",
            "button:has-text('Done')",
            "div[role='button']:has-text('Done')",
        ]
        last_error: Exception | None = None
        for selector in selectors:
            locator = self.page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=8_000)
                # Scroll into view to avoid misclicks on sidebar elements
                await locator.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(300)
                for _ in range(40):
                    try:
                        if await locator.is_enabled():
                            await locator.click()
                            return
                    except Exception:
                        await locator.click()
                        return
                    await self.page.wait_for_timeout(250)
            except Exception as exc:
                last_error = exc
        raise RuntimeError("Could not click Pinterest publish button") from last_error

    async def _extract_created_pin_url(self) -> str | None:
        view_pin = self.page.get_by_role("link", name="View Pin")
        if await view_pin.count():
            href = await view_pin.first.get_attribute("href")
            if href:
                return href if href.startswith("http") else f"https://www.pinterest.com{href}"
        if "/pin/" in self.page.url:
            return self.page.url
        return None

    async def _fill_first_available(self, selectors: list[str], value: str, *, timeout_ms: int = 5_000) -> None:
        last_error: Exception | None = None
        for selector in selectors:
            locator = self.page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=timeout_ms)
                try:
                    await locator.fill(value)
                except Exception:
                    await locator.click()
                    await self.page.keyboard.press("Control+A")
                    await self.page.keyboard.type(value)
                return
            except Exception as exc:  # Playwright selector fallback should keep trying.
                last_error = exc
        raise RuntimeError(f"Could not fill field with selectors: {selectors}") from last_error

    async def _has_file_input(self, *, timeout_ms: int) -> bool:
        deadline = datetime.now(UTC).timestamp() + (timeout_ms / 1000)
        while datetime.now(UTC).timestamp() < deadline:
            try:
                if await self.page.locator("input[type='file']").count() > 0:
                    return True
            except Exception:
                logger.info("File input probe failed while page was changing")
            await self.page.wait_for_timeout(500)
        return False

    async def _click_first_available(self, selectors: list[str]) -> None:
        last_error: Exception | None = None
        for selector in selectors:
            locator = self.page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=5_000)
                await locator.click()
                return
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Could not click selectors: {selectors}") from last_error
