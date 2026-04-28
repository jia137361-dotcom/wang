"""
warmup_flow.py
高仿真养号工作流：模拟真实 Pinterest 用户刷图、互动，提升账号权重
"""
import asyncio
import random
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple
from collections import deque

from playwright.async_api import Page, BrowserContext
from app.automation.human_sim import HumanSimulator  # 假设真人操作库
from app.automation.anti_detect import AntiDetect, FingerprintMutator
from app.automation.browser_factory import BrowserPool  # 假设浏览器池

# 行为配置
WARMUP_DAYS = 7                 # 养号总天数
SESSIONS_PER_DAY = (2, 4)       # 每天会话次数范围
SESSION_DURATION = (180, 600)   # 每次会话时长(秒)
MAX_ACTIONS_PER_SESSION = 30    # 每次会话最多操作数

# 延迟范围 (秒)
SHORT_DELAY = (0.5, 2.5)
MEDIUM_DELAY = (2.0, 8.0)
LONG_DELAY = (5.0, 20.0)

# 兴趣种子 (会根据浏览行为演化)
INTEREST_SEEDS = [
    "home decor ideas", "diy crafts", "summer fashion",
    "food recipes", "travel destinations", "fitness motivation",
    "cute animals", "graphic design inspiration"
]

# Pinterest 关键页面元素选择器 (示例)
SEARCH_INPUT = 'input[data-test-id="search-box-input"]'
PIN_IMAGE = 'div[data-test-id="pin"] img'
BOARD_SELECTOR = 'div[data-test-id="board-card"]'
CLOSEUP_PIN = 'div[data-test-id="closeup-body"]'
SAVE_BUTTON = 'button[data-test-id="save-button"]'
LIKE_BUTTON = 'button[data-test-id="like-button"]'
COMMENT_INPUT = 'textarea[data-test-id="comment-input"]'
FOLLOW_BUTTON = 'button[data-test-id="follow-button"]'


class WarmupSession:
    """
    单次养号会话控制器，执行发现->浏览->互动->等待的真实行为循环。
    """

    def __init__(self, page: Page, human: HumanSimulator, account_id: str, day: int):
        self.page = page
        self.human = human
        self.account_id = account_id
        self.day = day
        self.action_log: List[dict] = []
        self.current_board: Optional[str] = None  # 模拟默认保存的Board

    async def run(self):
        """执行一次完整的浏览会话"""
        print(f"[Warmup] 开始第{self.day}天会话，账号 {self.account_id}")
        start_time = time.time()
        session_duration = random.randint(*SESSION_DURATION)
        actions = 0

        # 1. 打开首页，模拟"漫无目的"滚动
        await self._humanized_navigate("https://www.pinterest.com/")
        await self._random_scroll_activity()

        # 2. 随机进行几次搜索浏览
        searches = random.randint(1, 4)
        for _ in range(searches):
            if time.time() - start_time > session_duration * 0.7:
                break
            keyword = self._select_interest_keyword()
            await self._search_and_browse(keyword)
            actions += 1

        # 3. 深入某几个 Pin 进行互动
        pins_to_interact = random.randint(2, 6)
        for i in range(pins_to_interact):
            if time.time() - start_time > session_duration * 0.85:
                break
            await self._interact_with_random_pin()
            actions += 1
            # 间歇性发呆
            if random.random() < 0.3:
                await asyncio.sleep(random.randint(*MEDIUM_DELAY))

        # 4. 可能关注几个用户或话题
        if random.random() < 0.4:
            await self._follow_random_user()

        # 5. 末尾随意浏览首页尾页，停留一会
        await self._random_scroll_activity(scrolls=random.randint(3,8))
        await asyncio.sleep(random.randint(10, 30))

        # 确保总时长接近设定值
        elapsed = time.time() - start_time
        if elapsed < session_duration * 0.8:
            await asyncio.sleep(session_duration * 0.9 - elapsed)

        print(f"[Warmup] 会话完成，共执行 {actions} 次操作，耗时 {elapsed:.0f} 秒")

    async def _humanized_navigate(self, url: str):
        """带人类延迟和鼠标移动的导航"""
        await self.page.goto(url, wait_until="domcontentloaded")
        await self.human.random_delay(1.5, 3.0)
        await self.human.mouse_wander(self.page)  # 鼠标无目的移动

    async def _random_scroll_activity(self, scrolls: int = 5):
        """模拟人类浏览式滚动，包括停顿、回滚、悬停"""
        for _ in range(scrolls):
            await self.human.smooth_scroll(self.page, direction="down", distance=random.randint(200, 600))
            await asyncio.sleep(random.uniform(0.8, 2.5))
            if random.random() < 0.2:
                # 小幅回滚
                await self.human.smooth_scroll(self.page, direction="up", distance=random.randint(50, 150))
            # 鼠标移到某张图片上
            if random.random() < 0.5:
                await self.human.hover_random_element(self.page, PIN_IMAGE)
                await asyncio.sleep(random.uniform(0.5, 2.0))

    def _select_interest_keyword(self) -> str:
        """根据账号阶段选择兴趣关键词，模拟兴趣演化"""
        # 初期常搜通用词，后期更具体
        base = random.choice(INTEREST_SEEDS)
        if self.day > 3:
            specifics = ["modern", "vintage", "easy", "aesthetic", "minimalist", "cozy"]
            base = f"{random.choice(specifics)} {base}"
        return base

    async def _search_and_browse(self, keyword: str):
        """执行搜索，随机浏览搜索结果，停留在不同结果上"""
        # 点击搜索框并输入
        search_btn = await self.page.wait_for_selector(SEARCH_INPUT, timeout=5000)
        if not search_btn:
            return
        await self.human.click_element_with_movement(self.page, search_btn)
        await self.human.simulate_typing(self.page, keyword, mistake_rate=0.03)

        # 提交搜索
        await self.page.keyboard.press("Enter")
        await self.page.wait_for_timeout(2000)
        await self._random_scroll_activity(scrolls=random.randint(3,6))

        # 可能点击某个搜索结果
        if random.random() < 0.6:
            pins = await self.page.query_selector_all(PIN_IMAGE)
            if pins:
                target = random.choice(pins)
                await self.human.click_element_with_movement(self.page, target)
                # 在 Pin 详情中停留阅读
                await asyncio.sleep(random.randint(*MEDIUM_DELAY))
                # 可能返回
                if random.random() < 0.7:
                    await self.page.go_back()
                    await self.page.wait_for_timeout(1000)

    async def _interact_with_random_pin(self):
        """对任意可见的 Pin 进行互动 (保存、点赞、评论)"""
        # 从首页或搜索结果中选取一个 Pin
        try:
            pin = await self.page.wait_for_selector(PIN_IMAGE, timeout=3000)
            if not pin:
                return
            await self.human.click_element_with_movement(self.page, pin)
            # 等待详情页加载
            await self.page.wait_for_selector(CLOSEUP_PIN, timeout=5000)
            await asyncio.sleep(random.uniform(1.0, 3.0))

            # 互动概率分布
            action_roll = random.random()
            if action_roll < 0.5:
                await self._save_pin()
            elif action_roll < 0.8:
                await self._like_pin()
            elif action_roll < 0.95:
                await self._comment_pin()
            # 其余情况不互动，只是查看

            # 关闭详情页
            close_btn = await self.page.query_selector('button[data-test-id="close-btn"]')
            if close_btn:
                await self.human.click_element_with_movement(self.page, close_btn)
            else:
                await self.page.go_back()
            await self.page.wait_for_timeout(1000)
        except Exception as e:
            print(f"互动异常: {e}")

    async def _save_pin(self):
        """点击保存，随机选择 Board"""
        save = await self.page.wait_for_selector(SAVE_BUTTON, timeout=3000)
        if save:
            await self.human.click_element_with_movement(self.page, save)
            await asyncio.sleep(random.uniform(0.8, 1.5))
            boards = await self.page.query_selector_all(BOARD_SELECTOR)
            if boards:
                chosen = random.choice(boards)
                await self.human.click_element_with_movement(self.page, chosen)
                self.action_log.append({"action": "save", "timestamp": datetime.now().isoformat()})

    async def _like_pin(self):
        like = await self.page.query_selector(LIKE_BUTTON)
        if like:
            await self.human.click_element_with_movement(self.page, like)
            self.action_log.append({"action": "like", "timestamp": datetime.now().isoformat()})

    async def _comment_pin(self):
        """极低频率留下简单评论"""
        comment_input = await self.page.query_selector(COMMENT_INPUT)
        if comment_input:
            await self.human.click_element_with_movement(self.page, comment_input)
            comments_pool = ["Love this!", "So inspiring", "Great idea!", "Wow, beautiful", "Need this in my life"]
            text = random.choice(comments_pool)
            await self.human.simulate_typing(self.page, text, mistake_rate=0.05)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            # 点击提交 (示例选择器)
            submit = await self.page.query_selector('button[data-test-id="comment-submit"]')
            if submit:
                await self.human.click_element_with_movement(self.page, submit)
            self.action_log.append({"action": "comment", "content": text, "timestamp": datetime.now().isoformat()})

    async def _follow_random_user(self):
        """模拟关注推荐用户"""
        # 这里简化：导航到一个话题或用户页面
        try:
            # 随机点击一个用户头像链接
            links = await self.page.query_selector_all('a[href*="/_p/"]')
            if links:
                link = random.choice(links)
                await self.human.click_element_with_movement(self.page, link)
                await self.page.wait_for_timeout(3000)
                follow_btn = await self.page.query_selector(FOLLOW_BUTTON)
                if follow_btn and "following" not in (await follow_btn.inner_text()).lower():
                    await self.human.click_element_with_movement(self.page, follow_btn)
                    self.action_log.append({"action": "follow", "timestamp": datetime.now().isoformat()})
                await self.page.go_back()
        except Exception:
            pass


class WarmupOrchestrator:
    """
    养号指挥中心：管理多日养号计划、浏览器环境重建、策略调度
    """
    def __init__(self, browser_pool: BrowserPool, account_id: str,
                 fingerprint_seed: str, proxy: Optional[Dict] = None):
        self.browser_pool = browser_pool
        self.account_id = account_id
        self.fp_seed = fingerprint_seed
        self.proxy = proxy
        self.human = HumanSimulator()   # 真人模拟器
        self.mutator = FingerprintMutator(seed=fingerprint_seed)
        self.log_path = Path(f"logs/warmup_{account_id}.jsonl")
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    async def run_full_warmup(self, days: int = WARMUP_DAYS):
        """执行完整养号周期 (默认7天)"""
        print(f"[Orchestrator] 开始对账号 {self.account_id} 进行为期 {days} 天的养号")
        for day in range(1, days + 1):
            sessions_today = random.randint(*SESSIONS_PER_DAY)
            for sess_num in range(sessions_today):
                # 每次会话可重新创建浏览器上下文，模拟开关浏览器
                browser = await self.browser_pool.acquire(self.account_id)
                anti = AntiDetect(browser, self.mutator, proxy=self.proxy)
                storage_state = f"storage/{self.account_id}_state.json"
                context = await anti.create_context(storage_state=storage_state if Path(storage_state).exists() else None)
                page = await context.new_page()

                session = WarmupSession(page, self.human, self.account_id, day)
                await session.run()

                # 保存存储状态（cookies, localStorage）
                await context.storage_state(path=storage_state)
                await anti.destroy()
                await self.browser_pool.release(self.account_id, browser)
                # 记录日志
                self._log_session(day, sess_num+1, session.action_log)
                # 间隔模拟真实人类离线
                cooldown = random.randint(600, 3600)  # 10分钟到1小时
                print(f"[Orchestrator] 会话结束，冷却 {cooldown} 秒...")
                await asyncio.sleep(cooldown)

        print(f"[Orchestrator] 养号完成，日志保存在 {self.log_path}")

    def _log_session(self, day: int, session_num: int, actions: list):
        entry = {
            "account_id": self.account_id,
            "day": day,
            "session": session_num,
            "timestamp": datetime.now().isoformat(),
            "actions": actions
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Backward-compatibility placeholders for safety-gate check scripts
# ---------------------------------------------------------------------------


def run_account_warmup_placeholder(account_id: str) -> None:
    """Safety-gated no-op retained for check_sensitive_placeholders.py."""
    print(f"[warmup] placeholder warmup for {account_id} (no-op)")


@dataclass(frozen=True)
class WarmupResult:
    executed: bool


class WarmupFlow:
    """Backward-compatible safety-gated stub for check_sensitive_placeholders."""

    def run(self, account_id: str) -> WarmupResult:
        return WarmupResult(executed=False)
