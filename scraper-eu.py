# -*- coding: utf-8 -*-
"""
Scrape Booking.com hotel reviews (modal + paginated, typically 10 per page).

Requires: Firefox + geckodriver (or set SCRAPER_BROWSER=chrome + chromedriver).

@author: D0mTu
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import time
from time import sleep

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    TimeoutException,
)
pd.set_option("display.max_columns", None)


def normalize_review_text(s: str) -> str:
    """
    Single-line cells for CSV; strip Booking placeholders; collapse whitespace.
    """
    if not s:
        return ""
    t = s.replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    if t in ("#NOM?", "#NOM"):
        return ""
    return t


def _d(msg: str) -> None:
    """Lightweight debug line for Selenium / flow visibility."""
    print(f"[scraper] {msg}", flush=True)


# Delays (seconds). Lower = faster; raise via env if pages flake on slow networks.
def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


PAGE_LOAD_PAUSE = _env_float("SCRAPER_PAGE_LOAD_PAUSE", 0.75)
AFTER_UI_CLICK_PAUSE = _env_float("SCRAPER_AFTER_UI_CLICK_PAUSE", 0.55)
PAGINATION_SETTLE_POLL = _env_float("SCRAPER_PAGINATION_POLL", 0.1)
PAGINATION_MAX_WAIT = _env_float("SCRAPER_PAGINATION_MAX_WAIT", 15.0)
BETWEEN_PAGES_PAUSE = _env_float("SCRAPER_BETWEEN_PAGES_PAUSE", 0.12)
EXPAND_SCROLL_PAUSE = _env_float("SCRAPER_EXPAND_SCROLL_PAUSE", 0.12)
EXPAND_AFTER_CLICK_PAUSE = _env_float("SCRAPER_EXPAND_AFTER_CLICK_PAUSE", 0.45)


# Default: Paço de Açúcar Hotel Porto — strip tracking params; use en-gb for stable UI copy
DEFAULT_HOTEL_URL = (
    "https://www.booking.com/hotel/pt/paodeacucarhotelporto.en-gb.html#tab-reviews"
)


def build_driver():
    browser = os.environ.get("SCRAPER_BROWSER", "firefox").lower()
    if browser == "chrome":
        from selenium.webdriver.chrome.options import Options

        opts = Options()
        opts.add_argument("--window-size=1400,900")
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        return webdriver.Chrome(options=opts)
    opts = webdriver.FirefoxOptions()
    opts.add_argument("--width=1400")
    opts.add_argument("--height=900")
    return webdriver.Firefox(options=opts)


def accept_cookies(driver) -> None:
    try:
        driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
        _d("Cookie banner accepted.")
        sleep(0.25)
    except NoSuchElementException:
        _d("No cookie banner (or already accepted).")


def _try_click_review_trigger(driver, by, sel: str, label: str) -> bool:
    """
    Scroll + JS-click a reviews opener. Re-finds the node after scroll to avoid
    StaleElementReferenceException when the DOM updates.
    """
    for attempt in range(3):
        try:
            el = driver.find_element(by, sel)
        except NoSuchElementException:
            _d(f"Trigger not found: {label}")
            return False
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            sleep(0.18)
            el = driver.find_element(by, sel)
            driver.execute_script("arguments[0].click();", el)
            sleep(AFTER_UI_CLICK_PAUSE)
            _d(f"Clicked trigger: {label}")
            return True
        except NoSuchElementException:
            _d(f"Trigger vanished after scroll: {label} (retry {attempt + 1}/3)")
        except StaleElementReferenceException:
            _d(f"Stale element on trigger: {label} (retry {attempt + 1}/3)")
        sleep(0.3)
    _d(f"Gave up on trigger: {label}")
    return False


def open_reviews_modal_if_needed(driver) -> None:
    """
    Reviews are often behind a tab and/or 'See all reviews' control that opens a dialog.
    Try several safe patterns; no-op if cards are already present.
    """
    def has_review_content() -> bool:
        if driver.find_elements(By.CSS_SELECTOR, "[data-testid='review-title']"):
            return True
        if driver.find_elements(By.CLASS_NAME, "be659bb4c2"):
            return True
        return False

    _d("open_reviews_modal_if_needed: checking for review cards on page…")
    if has_review_content():
        _d("Review cards already visible; skipping modal triggers.")
        return

    # Prefer this first: matches many Booking layouts when reviews are on a tab (often fastest).
    _d("Trying Reviews tab (href tab-reviews / id reviews)…")
    for attempt in range(3):
        try:
            tab = driver.find_element(
                By.XPATH,
                "//a[contains(@href,'tab-reviews') or contains(@id,'reviews')]",
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", tab)
            sleep(0.18)
            tab = driver.find_element(
                By.XPATH,
                "//a[contains(@href,'tab-reviews') or contains(@id,'reviews')]",
            )
            driver.execute_script("arguments[0].click();", tab)
            sleep(AFTER_UI_CLICK_PAUSE)
            _d("Clicked Reviews tab.")
            break
        except NoSuchElementException:
            _d("No Reviews tab link found; trying other triggers…")
            break
        except StaleElementReferenceException:
            _d(f"Stale tab element (retry {attempt + 1}/3)")
            sleep(0.3)

    if has_review_content():
        _d("Review content appeared after tab / early step.")
        return

    triggers: list[tuple[object, str, str]] = [
        (By.CSS_SELECTOR, "a[href*='tab-reviews']", "link href tab-reviews"),
        (
            By.XPATH,
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'all reviews')]",
            "button text all reviews",
        ),
        (
            By.XPATH,
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'all reviews')]",
            "a text all reviews",
        ),
        (
            By.XPATH,
            "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'all reviews')]",
            "span text all reviews",
        ),
        (By.CSS_SELECTOR, "[data-testid='reviews-modal-link']", "data-testid reviews-modal-link"),
        (By.CSS_SELECTOR, "[data-testid='fr-reviews-read-all']", "data-testid fr-reviews-read-all"),
    ]
    for by, sel, label in triggers:
        if _try_click_review_trigger(driver, by, sel, label) and has_review_content():
            _d("Review content appeared after trigger.")
            return

    if not has_review_content():
        _d("Warning: no review cards detected after all open steps; wait_for_any_review may fail.")


def wait_for_any_review(driver, timeout: int = 25) -> None:
    _d(f"Waiting up to {timeout}s for review cards…")
    end = time.time() + timeout
    last_log = 0.0
    while time.time() < end:
        if driver.find_elements(By.CSS_SELECTOR, "[data-testid='review-title']"):
            _d("Found reviews via [data-testid='review-title'].")
            return
        if driver.find_elements(By.CLASS_NAME, "be659bb4c2"):
            _d("Found reviews via legacy class be659bb4c2.")
            return
        now = time.time()
        if now - last_log >= 5.0:
            left = int(end - now)
            _d(f"Still waiting… ~{left}s left")
            last_log = now
        sleep(0.12)
    raise TimeoutException("No review cards found after waiting.")


def review_root_element(driver) -> object:
    """Prefer scraping inside the open dialog so pagination stays in scope."""
    for dlg in driver.find_elements(By.CSS_SELECTOR, "[role='dialog']"):
        if dlg.find_elements(By.CSS_SELECTOR, "[data-testid='review-title']"):
            return dlg
        if dlg.find_elements(By.CLASS_NAME, "be659bb4c2"):
            return dlg
    return driver


def safe_text(elem, xpath: str) -> str:
    try:
        return normalize_review_text(elem.find_element(By.XPATH, xpath).text.strip())
    except (NoSuchElementException, StaleElementReferenceException):
        return ""


def safe_text_by_testid(elem, testid: str) -> str:
    """Booking uses span/div/h3 interchangeably; match any tag with this data-testid."""
    return safe_text(elem, f".//*[@data-testid='{testid}']")


def safe_review_title(card) -> str:
    """Optional guest headline (often a span, not a div); many reviews omit it."""
    return safe_text_by_testid(card, "review-title")


def safe_text_with_click(driver, elem, xpath: str) -> str:
    """
    Expand only applies to buttons inside the target subtree (not the whole card).
    """
    try:
        sub = elem.find_element(By.XPATH, xpath)
    except NoSuchElementException:
        return ""
    click_expand(driver, sub)
    try:
        sub = elem.find_element(By.XPATH, xpath)
    except (NoSuchElementException, StaleElementReferenceException):
        return ""
    return normalize_review_text(sub.text.strip())


def safe_hotel_response(driver, card, pos_review: str) -> str:
    """
    Only the property reply block — not guest text. The old hashed-class fallback matched
    guest copy and duplicated pos_review.
    """
    xp = ".//*[@data-testid='review-host-response']"
    try:
        card.find_element(By.XPATH, xp)
    except NoSuchElementException:
        return ""
    t = safe_text_with_click(driver, card, xp)
    if not t:
        return ""
    p = normalize_review_text(pos_review)
    if p and t == p:
        return ""
    return t


def safe_score(elem) -> str:
    xpaths = [
        ".//div[contains(@class,'f63b14ab7a')]",
        ".//*[@data-testid='review-score']",
        ".//div[contains(@class,'review-score')]",
    ]
    for xp in xpaths:
        try:
            txt = elem.find_element(By.XPATH, xp).text
            line = txt.split("\n")[0].strip()
            return normalize_review_text(line.replace(",", "."))
        except (NoSuchElementException, StaleElementReferenceException):
            continue
    return ""


def click_expand(driver, elem) -> bool:
    try:
        btn = elem.find_element(
            By.XPATH,
            ".//button[contains(@class,'de576f5064') or contains(@class,'bef8628e61')]",
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});",
            btn,
        )
        sleep(EXPAND_SCROLL_PAUSE)
        try:
            btn.click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
            driver.execute_script("arguments[0].click();", btn)
        sleep(EXPAND_AFTER_CLICK_PAUSE)
        return True
    except NoSuchElementException:
        return False


def find_review_cards(root):
    """Booking uses hashed class names; prefer data-testid, then legacy class."""
    cards = root.find_elements(By.CSS_SELECTOR, "div[data-testid='review-card']")
    if cards:
        return cards
    cards = root.find_elements(By.CLASS_NAME, "be659bb4c2")
    if cards:
        return cards
    # Fallback: one ancestor per title (avoid matching a wrapper around all reviews)
    out = []
    seen = set()
    for title in root.find_elements(By.CSS_SELECTOR, "[data-testid='review-title']"):
        try:
            card = title.find_element(
                By.XPATH,
                "ancestor::div[.//span[@data-testid='review-room-name']][1]",
            )
            key = id(card)
            if key not in seen:
                seen.add(key)
                out.append(card)
        except NoSuchElementException:
            continue
    return out


def _card_fingerprint(card) -> str:
    """
    Raw text/HTML slice for dedup when structured selectors return nothing (Booking DOM drift).
    """
    try:
        t = (card.text or "").strip()
        if len(t) >= 30:
            return t[:900]
        html = (card.get_attribute("outerHTML") or "")[:600]
        return (html + "|" + t)[:900]
    except (StaleElementReferenceException, Exception):
        return ""


def review_dedup_key(row: dict, page_index: int) -> tuple:
    """
    Default: content-based key so repeating the same review on a stuck pager is skipped.
    Set SCRAPER_DEDUP_MODE=slot to key by (page, card index) only — use if pagination overlaps
    pages in the UI and content-based dedup drops real rows.
    """
    ox = int(row.get("_order_index", 0))
    mode = (os.environ.get("SCRAPER_DEDUP_MODE") or "").strip().lower()
    if mode in ("slot", "page_slot", "by_page"):
        return ("slot", page_index, ox)
    name = (row.get("name") or "").strip()
    date = (row.get("date") or "").strip()
    title = (row.get("title_review") or "").strip()
    pos = (row.get("pos_review") or "").strip()
    neg = (row.get("neg_review") or "").strip()
    score = (row.get("score") or "").strip()
    if name or date or title or pos or neg or score:
        return ("v1", name, date, title, pos, neg, score)
    fp = (row.get("_dedup_fp") or "").strip()
    if fp:
        return ("fp", fp[:900], ox)
    return ("weak", page_index, ox)


def _reviews_page_fingerprint(driver) -> str:
    """
    Signature of the whole visible review list (not only the first card). Waiting for the
    first title alone often returns before Booking finishes swapping the page, so we still
    collect a mix of old + new rows and dedup looks wrong.
    """
    root = review_root_element(driver)
    cards = find_review_cards(root)
    parts: list[str] = []
    for card in cards:
        nm = safe_text(card, ".//*[@data-testid='reviewer-name']") or safe_text(
            card, ".//div[contains(@class,'b08850ce41')]"
        )
        dt = safe_text(card, ".//span[@data-testid='review-stay-date']")
        pos = (safe_text_by_testid(card, "review-positive-text") or "")[:160]
        parts.append(f"{nm}|{dt}|{pos}")
    return "¦".join(parts)


def _wait_for_reviews_fingerprint_change(driver, previous_fp: str) -> None:
    """After Next, wait until the full list signature changes (or timeout)."""
    if not previous_fp:
        sleep(AFTER_UI_CLICK_PAUSE)
        return
    end = time.time() + PAGINATION_MAX_WAIT
    while time.time() < end:
        cur = _reviews_page_fingerprint(driver)
        if cur and cur != previous_fp:
            sleep(0.4)
            return
        sleep(PAGINATION_SETTLE_POLL)
    sleep(2.0)
    cur = _reviews_page_fingerprint(driver)
    if cur and cur != previous_fp:
        sleep(0.4)
        return
    _d(
        "Review list fingerprint did not change (pagination slow or stuck). "
        "Try SCRAPER_PAGINATION_MAX_WAIT=25 or SCRAPER_DEDUP_MODE=slot."
    )
    sleep(AFTER_UI_CLICK_PAUSE)


def collect_reviews(driver, root) -> list[dict]:
    rows = []
    cards = find_review_cards(root)
    for i, card in enumerate(cards):
        pos = safe_text_by_testid(card, "review-positive-text")
        row = {
            "name": safe_text(card, ".//div[contains(@class,'b08850ce41')]")
            or safe_text(card, ".//*[@data-testid='reviewer-name']"),
            "country": safe_text(card, ".//span[contains(@class,'d838fb5f41')]")
            or safe_text(card, ".//*[@data-testid='reviewer-country']"),
            "room_type": safe_text(card, ".//span[@data-testid='review-room-name']"),
            "nr_nights": safe_text(card, ".//span[@data-testid='review-num-nights']"),
            "date": safe_text(card, ".//span[@data-testid='review-stay-date']"),
            "traveler_type": safe_text(card, ".//span[@data-testid='review-traveler-type']"),
            "title_review": safe_review_title(card),
            "pos_review": pos,
            "neg_review": safe_text_by_testid(card, "review-negative-text"),
            "hotel_response": safe_hotel_response(driver, card, pos),
            "score": safe_score(card),
            "_dedup_fp": _card_fingerprint(card),
            "_order_index": i,
        }
        rows.append(row)
    return rows


def _find_next_review_page_button(driver, root):
    """Prefer explicit Next / Next page in the reviews dialog."""
    xps = [
        ".//button[contains(@aria-label, 'Next')]",
        ".//button[contains(@aria-label, 'next')]",
        ".//*[@role='button' and contains(@aria-label, 'Next')]",
    ]
    for xp in xps:
        btns = root.find_elements(By.XPATH, xp)
        for b in btns:
            label = (b.get_attribute("aria-label") or "").lower()
            if "previous" in label or "prev" in label:
                continue
            if "next" in label and b.is_enabled():
                if (b.get_attribute("aria-disabled") or "").lower() == "true":
                    continue
                return b
    # Legacy hashed classes — often two chevrons (prev / next); take last.
    legacy = root.find_elements(By.CSS_SELECTOR, "button.de576f5064.bd3ea87b7d")
    if len(legacy) >= 2:
        cand = legacy[-1]
    elif len(legacy) == 1:
        cand = legacy[0]
    else:
        cand = None
    if cand is not None and cand.is_enabled():
        return cand
    return None


def click_next_page(driver, root) -> bool:
    """Next page inside the reviews modal (10 reviews per page)."""
    btn = _find_next_review_page_button(driver, root)
    if btn is None and root != driver:
        btn = _find_next_review_page_button(driver, driver)
    if btn is None:
        for b in driver.find_elements(
            By.XPATH,
            "//div[@role='dialog']//button[contains(translate(@aria-label,'NEXT','next'),'next')]",
        ):
            lab = (b.get_attribute("aria-label") or "").lower()
            if "previous" in lab:
                continue
            if "next" in lab and b.is_enabled():
                btn = b
                break
    if btn is None:
        return False

    if not btn.is_enabled():
        return False
    aria_dis = (btn.get_attribute("aria-disabled") or "").lower()
    if aria_dis == "true":
        return False

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    sleep(0.12)
    try:
        btn.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        driver.execute_script("arguments[0].click();", btn)
    return True


def normalize_url(url: str) -> str:
    url = url.strip()
    if "#" not in url:
        url = url + "#tab-reviews"
    return url


def scrape(
    url: str,
    out_csv: str,
    max_pages: int,
    pause_between_pages: float | None = None,
) -> pd.DataFrame:
    url = normalize_url(url)
    if pause_between_pages is None:
        pause_between_pages = BETWEEN_PAGES_PAUSE
    driver = build_driver()
    df = pd.DataFrame(
        columns=[
            "name",
            "country",
            "room_type",
            "nr_nights",
            "date",
            "traveler_type",
            "title_review",
            "pos_review",
            "neg_review",
            "hotel_response",
            "score",
        ]
    )

    try:
        _d(f"Loading URL: {url}")
        driver.get(url)
        sleep(PAGE_LOAD_PAUSE)
        _d(f"Page title: {driver.title!r}")
        accept_cookies(driver)
        open_reviews_modal_if_needed(driver)
        wait_for_any_review(driver)
        root = review_root_element(driver)
        _d(f"Review root: {'dialog' if root != driver else 'full page'}")

        page = 0
        seen = set()
        while page < max_pages:
            root = review_root_element(driver)
            new_rows = collect_reviews(driver, root)
            if not new_rows:
                print(f"No cards on page {page + 1}; stopping.")
                break

            fresh = []
            for r in new_rows:
                key = review_dedup_key(r, page)
                if key not in seen:
                    seen.add(key)
                    r.pop("_dedup_fp", None)
                    r.pop("_order_index", None)
                    fresh.append(r)

            if fresh:
                df = pd.concat([df, pd.DataFrame(fresh)], ignore_index=True)
            elif new_rows:
                print(
                    "No new unique reviews on this page (often: pagination showed the same "
                    "set again, or every row matched a previous key). Stopping."
                )
                break

            print(f"Page {page + 1} | +{len(fresh)} new | total {len(df)}")

            if page + 1 >= max_pages:
                break

            anchor_fp = _reviews_page_fingerprint(driver)
            if not click_next_page(driver, root):
                print("No further next button; done.")
                break

            _wait_for_reviews_fingerprint_change(driver, anchor_fp)
            sleep(pause_between_pages)
            page += 1

    finally:
        df.to_csv(
            out_csv,
            index=False,
            encoding="utf-8-sig",
            sep=",",
            quoting=csv.QUOTE_MINIMAL,
            doublequote=True,
            lineterminator="\n",
        )
        print(f"Saved {len(df)} rows to {out_csv}")
        driver.quit()

    return df


def main():
    p = argparse.ArgumentParser(description="Booking.com hotel reviews → CSV")
    p.add_argument(
        "--url",
        default=os.environ.get("BOOKING_HOTEL_URL", DEFAULT_HOTEL_URL),
        help="Hotel page URL (reviews fragment added if missing)",
    )
    p.add_argument(
        "--out",
        default="reviews_paodeacucar_porto.csv",
        help="Output CSV path",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="How many review pages to scrape (≈10 reviews each). Default 1 until quality is verified; raise for full run.",
    )
    p.add_argument(
        "--pause-between-pages",
        type=float,
        default=None,
        help="Extra seconds after each page turn (default: SCRAPER_BETWEEN_PAGES_PAUSE or 0.12)",
    )
    args = p.parse_args()
    scrape(args.url, args.out, args.max_pages, pause_between_pages=args.pause_between_pages)


if __name__ == "__main__":
    main()
