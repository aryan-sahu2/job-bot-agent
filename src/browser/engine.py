import asyncio
import json
import logging
from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright

from src.config.loader import BrowserConfig

logger = logging.getLogger("job-bot.browser")

STEALTH_SCRIPT = """
// Override webdriver flag at the top level
Object.defineProperty(navigator, 'webdriver', { get: () => false });

// Override navigator.webdriver in Worker/ServiceWorker globals
if (typeof WorkerGlobalScope !== 'undefined') {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
}

// Build a convincing chrome.runtime with proper structure
const makeChrome = () => {
    const runtime = {
        id: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
        getManifest: () => ({
            name: 'Chrome',
            version: '134.0.6998.165',
            manifest_version: 3,
        }),
        connect: () => null,
        sendMessage: () => null,
    };
    return {
        runtime: runtime,
        loadTimes: () => ({
            requestTime: performance.now() / 1000,
            startLoadTime: performance.now() / 1000,
            commitLoadTime: (performance.now() + 100) / 1000,
            finishDocumentLoadTime: (performance.now() + 200) / 1000,
            finishLoadTime: (performance.now() + 500) / 1000,
            firstPaintTime: (performance.now() + 100) / 1000,
            firstPaintAfterLoadTime: (performance.now() + 600) / 1000,
            navigationType: 'Other',
            wasFetchedViaSpdy: true,
            wasNpnNegotiated: true,
            npnNegotiatedProtocol: 'h2',
            wasAlternateProtocolAvailable: false,
            connectionInfo: 'http/2',
        }),
        csi: () => ({
            startE: performance.now(),
            onloadT: performance.now() + 200,
            onT: performance.now() + 100,
            pageT: 'new',
            tran: Math.random() * 1000000,
        }),
        app: { isInstalled: false, InstallState: 'notinstalled', RunningState: 'stopped' },
    };
};

if (!window.chrome) {
    window.chrome = makeChrome();
} else {
    const existing = window.chrome;
    const newChrome = makeChrome();
    if (!existing.runtime) existing.runtime = newChrome.runtime;
    if (!existing.loadTimes) existing.loadTimes = newChrome.loadTimes;
    if (!existing.csi) existing.csi = newChrome.csi;
    if (!existing.app) existing.app = newChrome.app;
}

// Plugins — return a realistic array
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const p = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', desc: 'PDF' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', desc: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', desc: '' },
        ];
        p.length = 3;
        p.item = i => p[i] || null;
        p.namedItem = n => p.find(x => x.name === n) || null;
        p.refresh = () => {};
        return p;
    }
});

// Languages
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

// Permissions query — override to show notifications as prompt (not default deny)
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: 'prompt', onchange: null })
        : originalQuery(parameters)
);

// Platform consistency
Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

// Remove common Playwright/CDP automation indicators
const deleteProps = [
    'cdc_adoQpoasnfa76pfcZLmcfl_Array',
    'cdc_adoQpoasnfa76pfcZLmcfl_Promise',
    'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
    '_cdc_adoQpoasnfa76pfcZLmcfl_Array',
    '_cdc_adoQpoasnfa76pfcZLmcfl_Promise',
    '_cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
];
deleteProps.forEach(p => {
    try { delete window[p]; } catch (_) {}
});

// Override stack trace to hide injected script traces
const origPrepareStackTrace = Error.prepareStackTrace;
Error.prepareStackTrace = (err, stack) => {
    const filtered = stack.filter(callSite => {
        const fileName = callSite.getFileName() || '';
        return !fileName.includes('__playwright') && !fileName.includes('__pw');
    });
    return origPrepareStackTrace
        ? origPrepareStackTrace(err, filtered)
        : filtered.map(cs => cs.toString()).join('\\n');
};
"""


class BrowserError(Exception):
    pass


class BrowserEngine:
    def __init__(self, config: BrowserConfig) -> None:
        self._config = config
        self._browser = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._playwright = None
        self._user_data_dir = Path(config.user_data_dir)

    async def start(self) -> None:
        try:
            self._user_data_dir.mkdir(parents=True, exist_ok=True)

            self._playwright = await async_playwright().start()

            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ]

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._user_data_dir),
                headless=self._config.headless,
                args=launch_args,
                viewport={
                    "width": self._config.viewport.width,
                    "height": self._config.viewport.height,
                },
                locale="en-US",
                timezone_id="America/New_York",
            )

            await self._context.add_init_script(STEALTH_SCRIPT)

            if self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = await self._context.new_page()

        except Exception as e:
            raise BrowserError(f"Failed to launch browser: {e}") from e

    async def close(self) -> None:
        if self._config.storage_state and self._context:
            try:
                state = await self._context.storage_state()
                state_path = Path(self._config.storage_state)
                state_path.parent.mkdir(parents=True, exist_ok=True)
                state_path.write_text(json.dumps(state, indent=2))
                logger.info("Session state saved to %s", self._config.storage_state)
            except Exception as e:
                logger.warning("Failed to save session state: %s", e)

        if self._context:
            await self._context.close()
            self._context = None
            self._page = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def navigate(
        self, url: str, wait_until: str | None = None, wait_for_selector: str | None = None
    ) -> None:
        page = self._require_page()
        try:
            wait_arg = wait_until or "networkidle"
            await page.goto(url, timeout=self._config.timeout, wait_until=wait_arg)
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=self._config.timeout)
        except Exception as e:
            raise BrowserError(f"Failed to navigate to {url}: {e}") from e

    async def click(self, selector: str) -> None:
        page = self._require_page()
        try:
            await page.click(selector)
        except Exception as e:
            raise BrowserError(f"Failed to click {selector}: {e}") from e

    async def fill(self, selector: str, value: str) -> None:
        page = self._require_page()
        try:
            await page.fill(selector, value)
        except Exception as e:
            raise BrowserError(f"Failed to fill {selector}: {e}") from e

    async def select_option(self, selector: str, value: str) -> None:
        page = self._require_page()
        try:
            await page.select_option(selector, label=value)
        except Exception as e:
            raise BrowserError(f"Failed to select '{value}' in {selector}: {e}") from e

    async def set_checked(self, selector: str, checked: bool = True) -> None:
        page = self._require_page()
        try:
            await page.set_checked(selector, checked)
        except Exception as e:
            raise BrowserError(f"Failed to set checked={checked} for {selector}: {e}") from e

    async def upload_file(self, selector: str, file_path: str) -> None:
        page = self._require_page()
        path = Path(file_path)
        if not path.exists():
            raise BrowserError(f"File not found: {file_path}")
        try:
            await page.set_input_files(selector, str(path))
        except Exception as e:
            raise BrowserError(f"Failed to upload {file_path} to {selector}: {e}") from e

    async def scroll(self, selector: str | None = None) -> None:
        page = self._require_page()
        try:
            if selector:
                await page.evaluate(f"document.querySelector('{selector}')?.scrollIntoView()")
            else:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception as e:
            raise BrowserError(f"Failed to scroll: {e}") from e

    async def wait_for(self, selector: str, timeout: int | None = None) -> None:
        page = self._require_page()
        try:
            await page.wait_for_selector(
                selector,
                timeout=timeout or self._config.timeout,
            )
        except Exception as e:
            raise BrowserError(f"Failed waiting for {selector}: {e}") from e

    async def evaluate(self, expression: str) -> object:
        page = self._require_page()
        try:
            return await page.evaluate(expression)
        except Exception as e:
            raise BrowserError(f"Failed to evaluate JS: {e}") from e

    async def get_content(self) -> str:
        page = self._require_page()
        try:
            return await page.content()
        except Exception as e:
            raise BrowserError(f"Failed to get page content: {e}") from e

    async def screenshot(self, path: str) -> None:
        page = self._require_page()
        try:
            await page.screenshot(path=path, full_page=True)
        except Exception as e:
            raise BrowserError(f"Failed to save screenshot to {e}") from e

    async def pause_for_login(
        self, url: str, login_indicator: str, logged_in_indicator: str
    ) -> bool:
        page = self._require_page()
        try:
            await page.goto(url, timeout=self._config.timeout, wait_until="networkidle")

            try:
                await page.wait_for_selector(logged_in_indicator, timeout=5000)
                logger.info("Already logged in")
                return True
            except Exception:
                pass

            try:
                await page.wait_for_selector(login_indicator, timeout=3000)
            except Exception:
                logger.info("No login required for %s", url)
                return True

            print(f"\n{'=' * 60}")
            print("Manual login required")
            print(f"{'=' * 60}")
            print(f"A browser window has opened to: {url}")
            print("Please log in manually in the browser.")
            print("Once you are logged in, come back here and press Enter.")
            print(f"{'=' * 60}\n")

            await asyncio.get_event_loop().run_in_executor(
                None, input, "Press Enter after logging in... "
            )

            try:
                await page.wait_for_selector(logged_in_indicator, timeout=15000)
                logger.info("Login successful")
                return True
            except Exception:
                logger.warning("Could not verify login - proceeding anyway")
                return True

        except Exception as e:
            logger.error("Login pause failed: %s", e)
            return False

    async def __aenter__(self) -> "BrowserEngine":
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    def _require_page(self) -> Page:
        if self._page is None:
            raise BrowserError("Browser not started. Call start() first.")
        return self._page
