import asyncio
import hashlib
import requests
from dataclasses import dataclass
from typing import Dict, Any

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

@dataclass
class EndpointFeatures:
    has_microdata: bool = False
    has_viewstate: bool = False
    has_table: bool = False
    has_login_form: bool = False
    requires_js: bool = False
    infinite_scroll: bool = False
    is_random: bool = False
    delayed_render: bool = False


class EndpointClassifier:
    def __init__(
        self,
        url: str,
        js_wait: float = 2.0,
        scroll_wait: float = 2.0,
        timeout: int = 30000,
    ):
        self.url = url
        self.js_wait = js_wait
        self.scroll_wait = scroll_wait
        self.timeout = timeout

    # -------------------------
    # PUBLIC API
    # -------------------------

    async def classify(self) -> Dict[str, Any]:
        html_raw = self._fetch_raw_html()
        features = await self._analyze(html_raw)
        endpoint_type = self._classify(features)

        return {
            "type": endpoint_type,
            "features": features.__dict__,
        }

    # -------------------------
    # STATIC ANALYSIS
    # -------------------------

    def _fetch_raw_html(self) -> str:
        return requests.get(self.url, timeout=10).text

    def _static_features(self, html: str) -> EndpointFeatures:
        soup = BeautifulSoup(html, "html.parser")

        return EndpointFeatures(
            has_microdata=bool(soup.select("[itemscope], [itemprop]")),
            has_viewstate="__VIEWSTATE" in html or "__EVENTVALIDATION" in html,
            has_table=bool(soup.find("table")),
            has_login_form = bool(
                soup.select_one("input[type='password']")
                or soup.select_one("input[name*='csrf' i]")
            )
        )

    # -------------------------
    # DYNAMIC ANALYSIS (Playwright)
    # -------------------------

    async def _analyze(self, raw_html: str) -> EndpointFeatures:
        features = self._static_features(raw_html)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(self.url, timeout=self.timeout)

            # JS render detection
            await asyncio.sleep(self.js_wait)
            rendered_html = await page.content()
            features.requires_js = len(rendered_html) > len(raw_html) * 1.2

            # Delayed render detection
            await asyncio.sleep(3)
            later_html = await page.content()
            features.delayed_render = hashlib.md5(rendered_html.encode()).hexdigest() != \
                                      hashlib.md5(later_html.encode()).hexdigest()

            # Infinite scroll detection
            height1 = await page.evaluate("document.body.scrollHeight")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(self.scroll_wait)
            height2 = await page.evaluate("document.body.scrollHeight")
            features.infinite_scroll = height2 > height1

            await browser.close()

        # Random endpoint detection
        html2 = self._fetch_raw_html()
        features.is_random = hashlib.md5(raw_html.encode()).hexdigest() != \
                             hashlib.md5(html2.encode()).hexdigest()

        return features

    # -------------------------
    # CLASSIFICATION RULES
    # -------------------------

    def _classify(self, f: EndpointFeatures) -> str:
        if f.has_viewstate:
            return "viewstate"
        if f.has_login_form:
            return "login"
        if f.is_random:
            return "random"
        if f.infinite_scroll:
            return "scroll"
        if f.requires_js or f.delayed_render:
            return "javascript"
        if f.has_microdata:
            return "microdata"
        if f.has_table:
            return "tableful"
        return "default"
