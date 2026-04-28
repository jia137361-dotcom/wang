"""
anti_detect.py
高级浏览器指纹混淆与反检测模块
针对 Pinterest 真实用户行为测试工程优化
"""
import random
import json
import hashlib
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

class FingerprintMutator:
    """
    动态指纹突变器：基于种子生成一套稳定且合理的虚拟指纹参数。
    种子可由 AdsPower 环境 ID 或账号 ID 生成，保证同一账号指纹一致。
    """

    def __init__(self, seed: str = "default"):
        self.seed = seed
        self.rng = random.Random(seed)
        self._generate_fingerprints()

    def _generate_fingerprints(self):
        """生成 Canvas、WebGL、Audio 等核心指纹参数"""
        # Canvas hash 替换值
        self.canvas_noise = self.rng.randint(1, 1000) / 10000.0
        # WebGL 渲染器/厂商伪装
        webgl_vendors = ["Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0)", "Mesa DRI Intel(R) UHD Graphics 620 (KBL GT2)"]
        self.webgl_vendor = self.rng.choice(webgl_vendors)
        self.webgl_renderer = self.webgl_vendor.split("(")[0].strip() if "(" in self.webgl_vendor else self.webgl_vendor
        # AudioContext 随机偏移
        self.audio_noise = self.rng.randint(10, 50) / 1000.0
        # 屏幕参数
        self.width = self.rng.choice([1366, 1440, 1536, 1680, 1920])
        self.height = self.rng.choice([768, 900, 864, 1050, 1080])
        # 可用屏幕大小（略小）
        self.avail_width = self.width
        self.avail_height = self.height - self.rng.randint(40, 80)
        # 色彩深度
        self.color_depth = self.rng.choice([24, 30])
        # 平台 / 系统
        self.platform = self.rng.choice(["Win32", "MacIntel", "Linux x86_64"])
        # 语言
        languages = [["en-US", "en"], ["en-GB", "en"], ["en-CA", "en"], ["en-AU", "en"]]
        self.languages = self.rng.choice(languages)
        # 时区偏移 (美国境内)
        self.timezone_offset = self.rng.choice([-480, -420, -360, -300])  # PST, MST, CST, EST
        timezone_ids = { -480: "America/Los_Angeles", -420: "America/Denver", -360: "America/Chicago", -300: "America/New_York" }
        self.timezone_id = timezone_ids[self.timezone_offset]

        # 硬件并发数
        self.hardware_concurrency = self.rng.choice([4, 8, 12, 16])
        # 设备内存
        self.device_memory = self.rng.choice([4, 8, 16])
        # 触摸支持 (桌面用户通常无)
        self.max_touch_points = 0

        # 插件列表伪装
        self.plugins = [
            {"name": "Chrome PDF Plugin", "filename": "internal-pdf-viewer"},
            {"name": "Chrome PDF Viewer", "filename": "mhjfbmdgcfjbbpaeojofohoefgiehjai"},
            {"name": "Native Client", "filename": "internal-nacl-plugin"},
        ]
        # 字体列表 (常见字体的一部分，减少指纹唯一性)
        self.fonts = ["Arial", "Courier New", "Georgia", "Times New Roman", "Trebuchet MS", "Verdana", "Segoe UI"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "screen": {"width": self.width, "height": self.height,
                       "availWidth": self.avail_width, "availHeight": self.avail_height,
                       "colorDepth": self.color_depth},
            "platform": self.platform,
            "languages": self.languages,
            "timezone": {"offset": self.timezone_offset, "id": self.timezone_id},
            "hardwareConcurrency": self.hardware_concurrency,
            "deviceMemory": self.device_memory,
            "maxTouchPoints": self.max_touch_points,
            "canvasNoise": self.canvas_noise,
            "webglVendor": self.webgl_vendor,
            "webglRenderer": self.webgl_renderer,
            "audioNoise": self.audio_noise,
            "plugins": self.plugins,
            "fonts": self.fonts
        }


class AntiDetect:
    """
    反检测浏览器上下文管理器
    负责创建已混淆指纹的 Playwright BrowserContext，并植入持续运行的补丁脚本。
    """

    def __init__(self, browser: Browser, fingerprint: FingerprintMutator, proxy: Optional[Dict[str, str]] = None):
        self.browser = browser
        self.fp = fingerprint
        self.proxy = proxy
        self.context: Optional[BrowserContext] = None

    async def create_context(self, storage_state: Optional[str] = None) -> BrowserContext:
        """创建具备完整指纹混淆的浏览器上下文"""
        fp_dict = self.fp.to_dict()
        viewport = {"width": fp_dict["screen"]["width"], "height": fp_dict["screen"]["height"]}

        context_options = {
            "viewport": viewport,
            "screen": viewport,
            "user_agent": await self._generate_user_agent(),
            "locale": fp_dict["languages"][0],
            "timezone_id": fp_dict["timezone"]["id"],
            "permissions": ["geolocation"],
            "geolocation": {"latitude": 37.7749 + self.fp.rng.uniform(-0.5, 0.5),
                            "longitude": -122.4194 + self.fp.rng.uniform(-0.5, 0.5)},
            "color_scheme": "light",
            "extra_http_headers": self._extra_headers(),
        }
        if self.proxy:
            context_options["proxy"] = self.proxy

        # 若有持久化状态，则复用（保持登录）
        if storage_state and Path(storage_state).exists():
            context_options["storage_state"] = storage_state

        self.context = await self.browser.new_context(**context_options)

        # 注入初始化脚本，每次新页面都会执行
        await self.context.add_init_script(self._build_init_script())
        # 对已有的 page 也执行一次（上下文创建后会自动应用到新页面）
        return self.context

    async def _generate_user_agent(self) -> str:
        """生成与指纹平台匹配的最新 Chrome UA"""
        if "Win32" in self.fp.platform:
            os = "Windows NT 10.0; Win64; x64"
        elif "MacIntel" in self.fp.platform:
            os = "Macintosh; Intel Mac OS X 10_15_7"
        else:
            os = "X11; Linux x86_64"
        chrome_version = f"{self.fp.rng.randint(110, 125)}.0.{self.fp.rng.randint(5000,6000)}.{self.fp.rng.randint(100,200)}"
        return (f"Mozilla/5.0 ({os}) AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{chrome_version} Safari/537.36")

    def _extra_headers(self) -> Dict[str, str]:
        return {
            "Accept-Language": f"{','.join(self.fp.languages)};q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Ch-Ua": f'"Chromium";v="{random.randint(110,125)}", "Not.A/Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": f'"{self.fp.platform}"',
        }

    def _build_init_script(self) -> str:
        """
        核心反检测脚本：重写浏览器 API，消除自动化痕迹并随机化指纹。
        此脚本在页面加载前注入，作用于所有帧。
        """
        fp = self.fp
        # 将 Python 生成的指纹参数转为 JavaScript 变量
        js_fp = {
            "canvasNoise": fp.canvas_noise,
            "webglVendor": fp.webgl_vendor,
            "webglRenderer": fp.webgl_renderer,
            "audioNoise": fp.audio_noise,
            "plugins": fp.plugins,
            "fonts": fp.fonts,
            "languages": fp.languages,
            "platform": fp.platform,
            "hardwareConcurrency": fp.hardware_concurrency,
            "deviceMemory": fp.device_memory,
            "maxTouchPoints": fp.max_touch_points,
        }

        return f"""
        // ===== 高仿真指纹混淆脚本 =====
        (() => {{
            const fp = {json.dumps(js_fp)};
            
            // 1. 移除 webdriver 标记
            Object.defineProperty(navigator, 'webdriver', {{ get: () => false }});
            
            // 2. 覆盖 plugins 和 mimeTypes
            Object.defineProperty(navigator, 'plugins', {{
                get: () => {{
                    const arr = fp.plugins.map((p, idx) => {{
                        const plugin = {{
                            name: p.name,
                            filename: p.filename,
                            length: 1,
                            0: {{ type: 'application/pdf', suffixes: 'pdf' }}
                        }};
                        return plugin;
                    }});
                    arr.refresh = false;
                    arr.item = i => arr[i];
                    arr.namedItem = name => arr.find(p => p.name === name);
                    return arr;
                }}
            }});
            Object.defineProperty(navigator, 'mimeTypes', {{
                get: () => {{
                    const arr = [{{
                        type: 'application/pdf',
                        suffixes: 'pdf',
                        description: ''
                    }}];
                    arr.refresh = false;
                    arr.item = i => arr[i];
                    arr.namedItem = name => arr[0];
                    return arr;
                }}
            }});
            
            // 3. 语言欺骗
            Object.defineProperty(navigator, 'language', {{ get: () => fp.languages[0] }});
            Object.defineProperty(navigator, 'languages', {{ get: () => fp.languages }});
            
            // 4. 平台
            Object.defineProperty(navigator, 'platform', {{ get: () => fp.platform }});
            
            // 5. 硬件属性
            Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => fp.hardwareConcurrency }});
            Object.defineProperty(navigator, 'deviceMemory', {{ get: () => fp.deviceMemory }});
            Object.defineProperty(navigator, 'maxTouchPoints', {{ get: () => fp.maxTouchPoints }});
            
            // 6. 修复权限查询
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({{ state: Notification.permission }}):
                    originalQuery(parameters)
            );
            
            // 7. Canvas 指纹随机化
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {{
                const context = this.getContext('2d');
                if (context) {{
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imageData.data.length; i += 4) {{
                        imageData.data[i] ^= (fp.canvasNoise * 255) & 0xFF;
                    }}
                    context.putImageData(imageData, 0, 0);
                }}
                return originalToDataURL.apply(this, arguments);
            }};
            
            // 8. WebGL 指纹伪装
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) {{
                    return fp.webglVendor;  // UNMASKED_VENDOR_WEBGL
                }}
                if (parameter === 37446) {{
                    return fp.webglRenderer;  // UNMASKED_RENDERER_WEBGL
                }}
                return getParameter.call(this, parameter);
            }};
            
            // 9. AudioContext 指纹混淆
            const originalGetChannelData = AudioBuffer.prototype.getChannelData;
            AudioBuffer.prototype.getChannelData = function(channel) {{
                const data = originalGetChannelData.call(this, channel);
                for (let i = 0; i < data.length; i++) {{
                    data[i] += (fp.audioNoise * (Math.random() - 0.5)) * 0.0001;
                }}
                return data;
            }};
            
            // 10. 屏幕属性
            Object.defineProperty(screen, 'width', {{ get: () => {fp.width} }});
            Object.defineProperty(screen, 'height', {{ get: () => {fp.height} }});
            Object.defineProperty(screen, 'availWidth', {{ get: () => {fp.avail_width} }});
            Object.defineProperty(screen, 'availHeight', {{ get: () => {fp.avail_height} }});
            Object.defineProperty(screen, 'colorDepth', {{ get: () => {fp.color_depth} }});
            
            // 11. 移除 chrome 对象自动化标记
            if (window.chrome) {{
                window.chrome.runtime = {{}};
                window.navigator.chrome = {{}};
            }}
            
            // 12. 防止通过非标准属性检测
            delete window.__nightmare;
            delete window._phantom;
            delete window.callPhantom;
            delete window.Buffer;
            
            // 13. 覆盖 toString 避免被检测
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {{
                if (this === window.navigator.webdriver || this === window.chrome) {{
                    return 'function() {{ [native code] }}';
                }}
                return originalToString.call(this);
            }};
            
            console.log('[AntiDetect] Fingerprint spoofed successfully.');
        }})();
        """

    async def destroy(self):
        if self.context:
            await self.context.close()