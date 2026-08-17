import os
import re
import json
import time
import asyncio
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz, process
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

BASE_URL = "https://smartjobs.qld.gov.au"
SEARCH_URL = f"{BASE_URL}/jobtools/jncustomsearch.jobsearch?in_organid=14904"
PAGE_SIZE = 25
FUZZY_THRESHOLD = int(os.getenv("FUZZY_THRESHOLD", "75"))
MIN_CANDIDATE_LEN = int(os.getenv("MIN_CANDIDATE_LEN", "20"))
HEADER_SCAN_CHARS = int(os.getenv("HEADER_SCAN_CHARS", "2000"))

APP_DIR = Path(os.getenv("SMARTJOBS_APP_DIR", "/home/ubuntu/smartjobs"))
DATA_DIR = Path(os.getenv("SMARTJOBS_DATA_DIR", str(APP_DIR / "data")))
CLIENTS_FILE = Path(os.getenv("CLIENTS_FILE", str(DATA_DIR / "QLDGovt_Target_List.csv")))
CATEGORIES_FILE = Path(os.getenv("CATEGORIES_FILE", str(DATA_DIR / "Category_List.csv")))
OUTPUT_FILE = Path(os.getenv("OUTPUT_FILE", str(DATA_DIR / "smartjobs_leads.csv")))
ALL_RESULTS_FILE = Path(os.getenv("ALL_RESULTS_FILE", str(DATA_DIR / "smartjobs_all_results.csv")))
LOG_FILE = Path(os.getenv("LOG_FILE", str(DATA_DIR / "smartjobs_scraper.log")))

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEBHOOK_ENABLED = os.getenv("WEBHOOK_ENABLED", "false").lower() == "true"
WEBHOOK_TIMEOUT = int(os.getenv("WEBHOOK_TIMEOUT", "30"))

OUTPUT_COLUMNS = [
    "job_title",
    "organisation",
    "matched_client",
    "match_score",
    "contact_name",
    "contact_phone",
    "contact_email",
    "close_date",
    "job_url",
    "occupational_group",
    "date_scraped",
]

ALL_RESULTS_COLUMNS = [
    "job_title",
    "organisation",
    "matched_client",
    "match_score",
    "match_status",
    "contact_name",
    "contact_phone",
    "contact_email",
    "close_date",
    "job_url",
    "occupational_group",
    "date_scraped",
]

DATA_DIR.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("smartjobs")
log.setLevel(logging.INFO)
log.handlers.clear()
formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
sh = logging.StreamHandler()
fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
sh.setFormatter(formatter)
fh.setFormatter(formatter)
log.addHandler(sh)
log.addHandler(fh)


def load_clients():
    df = pd.read_csv(CLIENTS_FILE, dtype=str)
    df.columns = df.columns.str.strip()
    col = next((c for c in df.columns if any(k in c.lower() for k in ["organisation", "department"])), df.columns[0])
    vals = [v for v in df[col].dropna().str.strip().unique() if v]
    log.info(f"Clients loaded: {len(vals)}")
    return vals


def load_categories():
    df = pd.read_csv(CATEGORIES_FILE, dtype=str)
    df.columns = df.columns.str.strip()
    col = next((c for c in df.columns if any(k in c.lower() for k in ["occupational", "category", "group"])), df.columns[0])
    vals = [v for v in df[col].dropna().str.strip().unique() if v]
    log.info(f"Categories loaded: {vals}")
    return vals


def fuzzy_match(org, clients):
    if not org or not clients:
        return False, "", 0
    r1 = process.extractOne(org, clients, scorer=fuzz.token_sort_ratio)
    r2 = process.extractOne(org, clients, scorer=fuzz.token_set_ratio)
    if not r1 and not r2:
        return False, "", 0
    best = max([r for r in [r1, r2] if r], key=lambda x: x[1])
    name, score, _ = best
    return score >= FUZZY_THRESHOLD, name, score


async def find_occupational_group_dropdown(page, group):
    category_indicators = [
        "Accounting", "Administration", "Aviation", "Engineering",
        "Health", "Legal", "Science", "Transport"
    ]

    selects = await page.query_selector_all('select[name="in_others"]')
    log.info(f"Found {len(selects)} selects named in_others")

    for i, sel in enumerate(selects):
        options = await sel.query_selector_all("option")
        option_texts = [(await o.inner_text()).strip() for o in options]
        is_category_dropdown = any(
            any(ind in opt for ind in category_indicators)
            for opt in option_texts
        )
        log.info(f"select[{i}] is_category={is_category_dropdown} first={option_texts[:4]}")
        if is_category_dropdown:
            exact = next((t for t in option_texts if t.lower() == group.lower()), None)
            if exact:
                return sel, exact, option_texts
            partial = next((t for t in option_texts if group.lower() in t.lower() and t.lower() in group.lower()), None)
            if partial:
                return sel, partial, option_texts
            log.warning(f'Category dropdown found but "{group}" not in options')
            return sel, None, option_texts

    log.warning("Could not find occupational group dropdown")
    return None, None, []


async def get_job_urls_for_group(page, group):
    all_urls = []

    try:
        await page.goto(SEARCH_URL, wait_until="networkidle", timeout=30000)
    except PWTimeout:
        await page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

    dropdown, matched_option, _ = await find_occupational_group_dropdown(page, group)
    if dropdown is None or matched_option is None:
        log.warning(f'Skipping "{group}" - dropdown or option not found')
        return []

    await dropdown.select_option(label=matched_option)
    await page.wait_for_timeout(500)

    search_btn = None
    for sel in ['input[type="submit"]', 'button[type="submit"]', 'input[value*="Search" i]', 'button:has-text("Search")']:
        search_btn = await page.query_selector(sel)
        if search_btn:
            break

    if search_btn:
        await search_btn.click()
    else:
        await page.evaluate('document.querySelector("form").submit()')

    try:
        await page.wait_for_load_state("networkidle", timeout=20000)
    except PWTimeout:
        pass
    await page.wait_for_timeout(3000)

    while True:
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        job_links = soup.find_all("a", href=re.compile(r"/jobs/QLD-", re.I))
        if not job_links:
            job_links = soup.find_all("a", href=re.compile(r"viewFullSingle|jnCounter=\d+", re.I))

        if not job_links:
            break

        for link in job_links:
            href = link.get("href", "")
            url = href if href.startswith("http") else BASE_URL + href
            if url not in all_urls:
                all_urls.append(url)

        next_btn = await page.query_selector('a:has-text("Next"), a[title*="next" i], input[value="Next"]')
        if not next_btn or len(job_links) < PAGE_SIZE:
            break

        await next_btn.click()
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            pass
        await page.wait_for_timeout(2000)

    return all_urls


async def scrape_job_detail(page, url):
    title = ""
    org_candidates = []
    organisation = ""
    contact_name = contact_email = contact_phone = close_date = ""

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        try:
            await page.wait_for_selector("table", timeout=10000)
        except PWTimeout:
            pass
        await page.wait_for_timeout(1000)
        html = await page.content()
    except Exception as e:
        log.warning(f"Detail failed ({url}): {e}")
        return None

    soup = BeautifulSoup(html, "html.parser")

    for h in soup.find_all("h1"):
        t = h.get_text(strip=True)
        if t and t.lower() != "job search":
            title = t
            break

    if title:
        all_lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
        subtitle_line = ""
        for i, line in enumerate(all_lines):
            if line == title and i + 1 < len(all_lines):
                subtitle_line = all_lines[i + 1]
                break

        if subtitle_line:
            parts = [p.strip() for p in subtitle_line.split(";") if p.strip()]
            for part in parts:
                clean = re.sub(r"^Department of ", "", part).strip()
                if clean and len(clean) >= MIN_CANDIDATE_LEN and clean not in org_candidates:
                    org_candidates.append(clean)
                if clean != part and len(part) >= MIN_CANDIDATE_LEN and part not in org_candidates:
                    org_candidates.append(part)
            organisation = org_candidates[0] if org_candidates else subtitle_line

    for trow in soup.find_all("tr"):
        cells = trow.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True).lower()
        value = cells[1].get_text(" ", strip=True)

        if "contact person" in label:
            contact_name = value
        elif "contact detail" in label:
            a = cells[1].find("a", href=re.compile(r"mailto:", re.I))
            if a:
                contact_email = a["href"].replace("mailto:", "").split("?")[0].strip()
            else:
                m = re.search(r"[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}", value)
                if m:
                    contact_email = m.group(0)
            m = re.search(r"\b(0[47]\d{2}[\s]?\d{3}[\s]?\d{3}|0[2-9][\s]?\d{4}[\s]?\d{4})\b", value)
            if m:
                contact_phone = m.group(0)
        elif "closing date" in label or "close date" in label:
            close_date = value

    header_text = soup.get_text(" ", strip=True)[:HEADER_SCAN_CHARS]
    dept_m = re.search(
        r"((?:Department|Office|Commission|Authority|Agency|Service) of [A-Z][\w,\s&/]+?)(?:\s*\(|\s{2,}|\.$)",
        header_text
    )
    if dept_m:
        dept_name = dept_m.group(1).strip().rstrip(",. ")
        dept_stripped = re.sub(r"^Department of ", "", dept_name).strip()
        for dn in [dept_name, dept_stripped]:
            if dn and dn not in org_candidates:
                org_candidates.append(dn)

    if not title:
        return None

    return {
        "job_title": title,
        "organisation": organisation,
        "subtitle_parts": org_candidates,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "contact_email": contact_email,
        "close_date": close_date,
        "job_url": url,
    }


def load_existing():
    if OUTPUT_FILE.exists():
        try:
            df = pd.read_csv(OUTPUT_FILE, dtype=str).fillna("")
            log.info(f"Existing records: {len(df)}")
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def audit_key(df):
    return (
        df["job_url"].fillna("").str.lower()
        + "|"
        + df["occupational_group"].fillna("").str.lower()
    )


def load_existing_all_results():
    if ALL_RESULTS_FILE.exists():
        try:
            df = pd.read_csv(ALL_RESULTS_FILE, dtype=str).fillna("")
            for column in ALL_RESULTS_COLUMNS:
                if column not in df.columns:
                    df[column] = ""
            df = df[ALL_RESULTS_COLUMNS]
            log.info(f"Existing audit records: {len(df)}")
            return df
        except Exception as exc:
            log.warning(f"Could not load audit results: {exc}")
    return pd.DataFrame(columns=ALL_RESULTS_COLUMNS)


def save_all_results_checkpoint(existing, new_rows):
    if not new_rows:
        out = existing if not existing.empty else pd.DataFrame(columns=ALL_RESULTS_COLUMNS)
    else:
        new_df = pd.DataFrame(new_rows)[ALL_RESULTS_COLUMNS].fillna("")
        if existing.empty:
            out = new_df
        else:
            current = existing.copy()
            current["_key"] = audit_key(current)
            new_df["_key"] = audit_key(new_df)
            kept = current[~current["_key"].isin(new_df["_key"])].drop(columns=["_key"])
            out = pd.concat([kept, new_df.drop(columns=["_key"])], ignore_index=True)

        out = out.sort_values(
            ["date_scraped", "close_date", "organisation"],
            ascending=[False, True, True],
            na_position="last",
        )

    out.to_csv(ALL_RESULTS_FILE, index=False, encoding="utf-8-sig")
    log.info(f"Saved {len(out)} audit records to {ALL_RESULTS_FILE}")
    return out


def save_checkpoint(existing, new_rows):
    if not new_rows:
        out = existing if not existing.empty else pd.DataFrame(columns=OUTPUT_COLUMNS)
    else:
        new_df = pd.DataFrame(new_rows)[OUTPUT_COLUMNS].fillna("")
        def key(df):
            return df["job_title"].str.lower() + "|" + df["organisation"].str.lower()
        if existing.empty:
            out = new_df
        else:
            e = existing.copy()
            e["_key"] = key(e)
            new_df["_key"] = key(new_df)
            kept = e[~e["_key"].isin(new_df["_key"])].drop(columns=["_key"])
            out = pd.concat([kept, new_df.drop(columns=["_key"])], ignore_index=True)
        out = out.sort_values(["close_date", "organisation"], na_position="last")

    out.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    log.info(f"Saved {len(out)} records to {OUTPUT_FILE}")
    return out


def build_webhook_payload(row):
    return {
        "source_type": "smartjobs",
        "review_type": "unmatched_contact",
        "source_record_key": row["job_url"],
        "source_payload": row,
        "scraped_organisation": row["organisation"],
        "scraped_contact_name": row["contact_name"],
        "scraped_contact_email": row["contact_email"],
        "scraped_contact_phone": row["contact_phone"],
        "job_title": row["job_title"],
        "job_url": row["job_url"],
        "best_candidate_checked": "false",
        "best_score": str(row["match_score"]),
    }


def post_to_webhook(row):
    if not WEBHOOK_ENABLED or not WEBHOOK_URL:
        return None
    payload = build_webhook_payload(row)
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=WEBHOOK_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


async def run_scraper(categories, clients):
    today = datetime.now().strftime("%Y-%m-%d")
    existing_df = load_existing()
    existing_all_results_df = load_existing_all_results()
    all_matched = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            locale="en-AU",
            viewport={"width": 1280, "height": 900},
        )
        search_page = await context.new_page()
        detail_page = await context.new_page()

        for group in categories:
            log.info(f'=== "{group}" ===')
            group_matched = []
            group_all_results = []

            job_urls = await get_job_urls_for_group(search_page, group)
            log.info(f'URLs found: {len(job_urls)}')

            for i, url in enumerate(job_urls):
                log.info(f'[{i+1}/{len(job_urls)}] {url}')
                await asyncio.sleep(1.5)
                job = await scrape_job_detail(detail_page, url)
                if not job:
                    group_all_results.append({
                        "job_title": "",
                        "organisation": "",
                        "matched_client": "",
                        "match_score": "",
                        "match_status": "scrape_error",
                        "contact_name": "",
                        "contact_phone": "",
                        "contact_email": "",
                        "close_date": "",
                        "job_url": url,
                        "occupational_group": group,
                        "date_scraped": today,
                    })
                    continue

                best_client = ""
                best_score = 0
                candidates = job.get("subtitle_parts", [])
                if job["organisation"] and job["organisation"] not in candidates:
                    candidates = [job["organisation"]] + candidates

                for candidate in candidates:
                    if not candidate:
                        continue
                    _, client, score = fuzzy_match(candidate, clients)
                    if score > best_score:
                        best_client, best_score = client, score

                best_match = best_score >= FUZZY_THRESHOLD
                if best_match:
                    match_status = "matched"
                elif job["organisation"] or candidates:
                    match_status = "below_threshold"
                else:
                    match_status = "no_organisation"

                audit_row = {
                    "job_title": job["job_title"],
                    "organisation": job["organisation"],
                    "matched_client": best_client,
                    "match_score": str(round(best_score, 1)) if best_client else "",
                    "match_status": match_status,
                    "contact_name": job["contact_name"],
                    "contact_phone": job["contact_phone"],
                    "contact_email": job["contact_email"],
                    "close_date": job["close_date"],
                    "job_url": job["job_url"],
                    "occupational_group": group,
                    "date_scraped": today,
                }
                group_all_results.append(audit_row)

                if best_match:
                    row = {column: audit_row[column] for column in OUTPUT_COLUMNS}
                    group_matched.append(row)

                    if WEBHOOK_ENABLED and WEBHOOK_URL:
                        try:
                            result = post_to_webhook(row)
                            log.info(f"Webhook posted: {result}")
                        except Exception as e:
                            log.warning(f"Webhook failed for {row['job_url']}: {e}")

            all_matched.extend(group_matched)
            existing_df = save_checkpoint(existing_df, group_matched)
            existing_all_results_df = save_all_results_checkpoint(
                existing_all_results_df,
                group_all_results,
            )
            log.info(
                f'Done group "{group}" - {len(group_matched)} matches, '
                f'{len(group_all_results)} audit rows'
            )

        await browser.close()

    log.info(f"TOTAL matched: {len(all_matched)}")
    return all_matched


def main():
    log.info("=" * 60)
    log.info("SmartJobs QLD Scraper VM Script")
    log.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    clients = load_clients()
    categories = load_categories()
    matched = asyncio.run(run_scraper(categories, clients))

    print(json.dumps({
        "ok": True,
        "matched_count": len(matched),
        "output_file": str(OUTPUT_FILE),
        "webhook_enabled": WEBHOOK_ENABLED,
    }, indent=2))


if __name__ == "__main__":
    main()