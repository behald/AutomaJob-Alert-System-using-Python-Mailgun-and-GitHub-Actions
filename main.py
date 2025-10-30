import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import time
import random
from urllib.parse import unquote

# --- CONFIG ---
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
TO_EMAIL = os.getenv("TO_EMAIL", "behal.divaye@gmail.com")

CSV_FILE = "company_data.csv"
SEEN_FILE = "seen_jobs.json"

DEBUG = True  # Set False to silence debug prints

# --- BUILD SEARCH QUERY (U.S.-focused) ---
def build_query(company):
    company_clean = company.lower().replace(" ", "")
    return (
        f'site:({company_clean}.myworkdayjobs.com OR careers.{company_clean}.com OR greenhouse.io OR lever.co) '
        f'("{company}" AND ("data" OR "analytics" OR "engineer" OR "analyst")) "United States"'
    )


# --- SCRAPE GOOGLE RESULTS ---
def get_google_results(query, company=None):
    """
    Fetches up to 30 clean job links from Google Search for a given company query.
    Includes:
    - Last 1 month filter
    - Debug output
    - Filtering of irrelevant links
    - Relaxed company match
    """
    headers = {
        "User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Mozilla/5.0 (X11; Linux x86_64)",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)"
        ])
    }

    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=30&tbs=qdr:m"
    print(f"\n[DEBUG] Google query for {company}: {url}")

    res = requests.get(url, headers=headers)
    print(f"[DEBUG] Response length for {company}: {len(res.text)}")

    soup = BeautifulSoup(res.text, "html.parser")
    links = []

    company_clean = (company or "").lower().replace(" ", "")

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if not href.startswith("/url?q="):
            continue

        clean_link = unquote(href.split("/url?q=")[1].split("&")[0])

        # Filter irrelevant
        if any(
            clean_link.startswith(prefix)
            for prefix in [
                "https://www.google.com",
                "https://accounts.google.com",
                "https://maps.google.com",
            ]
        ) or clean_link.endswith(".pdf"):
            continue

        # Keep only valid job domains
        valid_domains = [
            "greenhouse.io",
            "myworkdayjobs.com",
            "lever.co",
            "smartrecruiters.com",
            "careers.",
            ".jobs",
            "apply.",
            "workwithus.",
            "jobvite.com",
            "icims.com",
        ]
        if not any(domain in clean_link for domain in valid_domains):
            continue

        # Skip non-US
        if any(
            country in clean_link.lower()
            for country in ["/uk/", "/ca/", "/in/", "/au/", "/eu/", "/sg/", "/de/", "/fr/", "/ph/", "/mx/"]
        ):
            continue

        # Relaxed company name match
        if company_clean and company_clean not in clean_link.lower():
            tokens = [t for t in company_clean.split() if len(t) > 2]
            if not any(t in clean_link.lower() for t in tokens):
                if DEBUG:
                    print(f"[WARN] {company}: unrelated link → {clean_link}")
                continue

        links.append(clean_link)

    clean_links = list(dict.fromkeys(links))[:5]

    if clean_links:
        print(f"[DEBUG] {company}: {len(clean_links)} job links found")
        for l in clean_links:
            print(f"   → {l}")
    else:
        print(f"[INFO] No clean results found for {company}.")

    return clean_links


# --- LOAD/SAVE SEEN JOBS ---
def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


# --- SEND EMAIL ---
def send_email(subject, html_body):
    if not MAILGUN_API_KEY or not MAILGUN_DOMAIN:
        print("❌ Missing Mailgun credentials.")
        return False

    api_base = (
        "https://api.eu.mailgun.net/v3"
        if ".eu." in MAILGUN_DOMAIN
        else "https://api.mailgun.net/v3"
    )

    api_key = MAILGUN_API_KEY.strip()
    if not api_key.startswith("key-"):
        api_key = f"key-{api_key}"  # auto-fix key prefix

    response = requests.post(
        f"{api_base}/{MAILGUN_DOMAIN}/messages",
        auth=("api", api_key),
        data={
            "from": f"Job Alerts <alerts@{MAILGUN_DOMAIN}>",
            "to": [TO_EMAIL],
            "subject": subject,
            "html": html_body,
        },
    )

    if response.status_code == 200:
        print("✅ Email sent successfully.")
        return True
    elif response.status_code == 401:
        print("❌ Mailgun authentication failed (401). Check API key, domain, and recipient verification.")
    else:
        print(f"❌ Mailgun error {response.status_code}: {response.text}")
    return False


# --- MAIN FUNCTION ---
def main():
    if not os.path.exists(CSV_FILE):
        print(f"❌ Missing {CSV_FILE}.")
        return

    df = pd.read_csv(CSV_FILE)
    if "EMPLOYER_NAME" not in df.columns:
        print("❌ 'EMPLOYER_NAME' column missing in CSV.")
        return

    companies = df["EMPLOYER_NAME"].dropna().tolist()
    seen = load_seen()
    new_results = {}

    for company in companies:
        try:
            print(f"\n🔍 Searching for {company}...")
            query = build_query(company)
            links = get_google_results(query, company)

            if not links:
                print(f"⚠️ No results for {company}, retrying broadly...")
                fallback = f'site:({company}.com OR myworkdayjobs.com OR lever.co OR greenhouse.io) "{company}" "data" "United States"'
                links = get_google_results(fallback, company)

            fresh_links = [l for l in links if l not in seen]
            if fresh_links:
                new_results[company] = fresh_links
                seen.update(fresh_links)

            time.sleep(1.5)  # safer crawl rate
        except Exception as e:
            print(f"⚠️ Error fetching {company}: {e}")

    if new_results:
        today = datetime.now().strftime("%b %d, %Y %H:%M")
        body = f"<h3>🚨 New U.S. Job Alerts ({today})</h3><br>"
        for company, links in new_results.items():
            body += f"<b>{company}</b><br>"
            for l in links:
                body += f'→ <a href="{l}">{l}</a><br>'
            body += "<br>"

        send_email("🚨 New Entry-Level U.S. Job Postings", body)
        print(f"✅ Email sent with {len(new_results)} company updates.")
    else:
        print("No new U.S. jobs found. Try again later or loosen filters.")

    save_seen(seen)


if __name__ == "__main__":
    main()
