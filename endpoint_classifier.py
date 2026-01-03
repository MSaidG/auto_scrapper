import asyncio
import requests
import json
from dataclasses import dataclass
from typing import Dict, Any, Optional, Union
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from collections import Counter

@dataclass
class EndpointFeatures:
    has_auth_wall: bool = False
    has_viewstate: bool = False
    has_table: bool = False
    requires_js: bool = False
    infinite_scroll: bool = False
    is_random: bool = False
    has_repeating_containers: bool = False
    login_required: bool = False

class EndpointClassifier:
    def __init__(self, url: str, js_wait: float = 2.5, scroll_wait: float = 2.0, timeout: int = 30000):
        self.url = url
        self.js_wait = js_wait
        self.scroll_wait = scroll_wait
        self.timeout = timeout

    async def classify(self) -> Dict[str, Any]:
        features = await self._analyze()
        endpoint_type = self._classify(features)
        return {"type": endpoint_type, "features": features.__dict__}

    def _fetch_raw_html(self) -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"}
            return requests.get(self.url, headers=headers, timeout=10).text
        except:
            return ""

    async def _analyze(self) -> EndpointFeatures:
        raw_html = self._fetch_raw_html()
        soup_raw = BeautifulSoup(raw_html, "html.parser")
        raw_text_len = len(soup_raw.get_text(strip=True))
        
        # Static feature detection
        features = EndpointFeatures(
            has_viewstate="__VIEWSTATE" in raw_html or "__EVENTVALIDATION" in raw_html,
            has_table=bool(soup_raw.find("table")),
            has_repeating_containers=self._count_containers(soup_raw) >= 3
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                # wait_until="networkidle" helps X.com fully load the login modal
                await page.goto(self.url, timeout=self.timeout, wait_until="networkidle")
                
                # Double check specific redirections
                if "login" in page.url or "checkpoint" in page.url:
                    features.has_auth_wall = True

                rendered_html = await page.content()
                soup_rendered = BeautifulSoup(rendered_html, "html.parser")
                rendered_text_len = len(soup_rendered.get_text(strip=True))

                # 1. Javascript Detection
                # Trigger if text content doubles OR if raw page was basically empty (< 500 chars)
                features.requires_js = (raw_text_len < 500) or (rendered_text_len > raw_text_len * 2.0)

                # 2. Auth Wall Detection (The X.com Fix)
                if not features.has_auth_wall:
                    features.login_required = self._detect_login_required(rendered_html)
                    features.has_auth_wall = self._detect_auth_wall(rendered_html)

                # 3. Smart Scroll Detection (The Quotes vs Reddit Fix)
                h1 = await page.evaluate("document.body.scrollHeight")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(self.scroll_wait)
                h2 = await page.evaluate("document.body.scrollHeight")
                
                # It is infinite scroll if:
                # A) It grew by a massive amount (2000px+) -> Catches big social feeds
                # B) OR It grew by 50% relative to original size -> Catches small demo sites
                features.infinite_scroll = (h2 - h1 > 2000) or (h2 > h1 * 1.5)

            except Exception as e:
                # If page crashes/timeouts, assume unsupported if we can't read it
                pass
            finally:
                await browser.close()

        # Randomness check (static)
        features.is_random = self._detect_randomness()
        return features

    def _classify(self, f: EndpointFeatures) -> str:
        # Priority 1: Blocking Walls (X.com, Facebook)
        if f.has_auth_wall or f.login_required or f.has_viewstate:
            return "unsupported"
            
        # Priority 2: Behavioral
        if f.is_random:
            return "random"
            
        # Priority 3: Scroll vs Default
        # If it scrolls, it is 'scroll' ONLY IF it didn't start with content.
        # Reddit starts with content (has_repeating_containers=True) -> Default
        # Quotes/Scroll starts empty (has_repeating_containers=False) -> Scroll
        if f.infinite_scroll:
            if not f.has_repeating_containers:
                return "scroll"
            # If it has containers but requires JS to show MORE, it might just be a JS site
            # but usually we prefer 'default' if the first page is useful.
        
        # Priority 4: Structure
        if f.requires_js:
            return "javascript"
        if f.has_table:
            return "tableful"
            
        return "default"

    def _count_containers(self, soup) -> int:
        selector_counts = Counter()
        # Look for typical item containers
        for el in soup.find_all(["article", "div", "li"], recursive=True):
            classes = el.get("class")
            if classes:
                # Create a signature: "tag_name.sorted_classes"
                key = f"{el.name}." + ".".join(sorted(classes))
                selector_counts[key] += 1
        
        if not selector_counts:
            return 0
        # Return the count of the most common container type
        return max(selector_counts.values())

    def _detect_login_required(self, html: str) -> bool:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True).lower()
        phrases = ["log in to continue", "sign in to", "login required", "please login"]
        # Only flag if page is relatively empty (avoids false positives in footer text)
        return any(p in text for p in phrases) and len(text) < 3000

    def _detect_auth_wall(self, html: str) -> bool:
        soup = BeautifulSoup(html, "lxml")
        
        # 1. Structural React/Next.js markers (X and Facebook use these heavily)
        if soup.select_one('[data-testid*="login"], [data-testid*="signup"], [data-testid*="apple"], [data-testid*="google"]'):
            return True
            
        # 2. Path-based check (if Playwright stayed on a login-heavy path)
        text = soup.get_text(" ", strip=True).lower()
        
        # 3. Keyword Density Check
        # On X.com, "Sign up" and "Log in" appear many times in buttons and headers
        auth_keywords = ["sign up", "log in", "create account", "forgot password", "policy"]
        hits = sum(text.count(k) for k in auth_keywords)
        
        # If the page is essentially a "Join X today" screen
        if hits >= 4 and len(text) < 5000:
            return True
            
        return False

    def _detect_randomness(self) -> bool:
        # Check randomness using raw requests to be fast
        try:
            t1 = self._fetch_raw_html()
            t2 = self._fetch_raw_html()
            # Compare the first 500 chars of text content
            s1 = BeautifulSoup(t1, "lxml").get_text(strip=True)[:500]
            s2 = BeautifulSoup(t2, "lxml").get_text(strip=True)[:500]
            return s1 != s2
        except:
            return False
