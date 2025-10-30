import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import time

# --- CONFIG ---
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
TO_EMAIL = os.getenv("TO_EMAIL", "behal.divaye@gmail.com")

CSV_FILE = "company_data.csv"
SEEN_FILE = "seen_jobs.json"

DEBUG = True  # Set False to silence debug prints


# --- BUILD SEARCH QUERY (simplified + US focused) ---
def build_query(company):
    company_clean = company.lower().replace(" ", "")
    query = (
        f'site:({company_clean}.myworkdayjobs.com OR careers.{company_clean}.com OR greenhouse.io OR lever.co)'
        f'("{company}" AND ("data" OR "analytics" OR "engineer" OR "analyst")) "United States"'
    )
    return query


# --- SCRAPE GOOGLE RESULTS ---
from urllib.parse import unquote

from urllib.parse import unquote

from urllib.parse import unquote

def get_google_results(query, company=None):
    headers = {"User-Agent": "Mozilla/5.0"}
    # 👇 Only fetch results from the past 24 hours
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=30&tbs=qdr:m"
    res = requests.get(url, headers=headers)
    print(f"[DEBUG] Google URL used: {url}")
    print(f"[DEBUG] Response length: {len(res.text)}")

    soup = BeautifulSoup(res.text, "html.parser")

    links = []
    company_clean = (company or "").lower().replace(" ", "")

    for tag in soup.find_all("a", href=True):
        href = tag["href"]

        if href.startswith("/url?q="):
            clean_link = unquote(href.split("/url?q=")[1].split("&")[0])

            # Filter for real career/job sites only
            valid_domains = (
                "greenhouse.io",
                "myworkdayjobs.com",
                "lever.co",
                "smartrecruiters.com",
                "careers.",
                ".jobs",
                "apply.",
                "workwithus.",
            )

            if (
                any(domain in clean_link for domain in valid_domains)
                and not clean_link.startswith(("https://accounts.google.com", "https://maps.google.com"))
                and not "support.google" in clean_link
                and not "recruiting-resources" in clean_link
                and not "youtube.com" in clean_link
            ):
                # Skip non-US patterns
                if any(
                    country in clean_link.lower()
                    for country in ["/uk/", "/ca/", "/in/", "/au/", "/eu/", "/sg/", "/de/", "/fr/", "/ph/", "/mx/"]
                ):
                    continue

                # Keep only if company name appears
                if company_clean and company_clean not in clean_link.lower():
                    if not any(token in clean_link.lower() for token in company_clean.split()):
                        continue

                links.append(clean_link)

    # Remove duplicates and limit
    return list(dict.fromkeys(links))[:5]





# --- LOAD/SAVE SEEN JOBS ---
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            try:
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
        print("❌ Mailgun credentials missing. Please set MAILGUN_API_KEY and MAILGUN_DOMAIN.")
        return False

    # Detect region automatically
    api_base = (
        "https://api.eu.mailgun.net/v3"
        if ".eu." in MAILGUN_DOMAIN
        else "https://api.mailgun.net/v3"
    )

    api_key = MAILGUN_API_KEY.strip()


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

    # --- Detailed diagnostics ---
    if response.status_code == 200:
        print("✅ Email sent successfully.")
        return True
    elif response.status_code == 401:
        print("❌ Mailgun authentication failed (401).")
        print("🔑 Possible causes:")
        print("   • Wrong API key or missing 'key-' prefix.")
        print("   • Incorrect Mailgun domain.")
        print("   • Free account: recipient not verified.")
        print("   • Region mismatch (EU vs US).")
    else:
        print(f"❌ Mailgun error {response.status_code}: {response.text}")

    return False



# --- MAIN ---
def main():
    if not os.path.exists(CSV_FILE):
        print(f"❌ Missing file: {CSV_FILE}")
        return

    df = pd.read_csv(CSV_FILE)
    if "EMPLOYER_NAME" not in df.columns:
        print("❌ Column 'EMPLOYER_NAME' not found in CSV.")
        return

    companies = df["EMPLOYER_NAME"].dropna().tolist()
    seen = load_seen()
    new_results = {}

    for company in companies:
        try:
            query = build_query(company)
            if DEBUG:
                print(f"\n🔍 Searching for {company}...")
            links = get_google_results(query)

            # If nothing found, retry with broader query
            if not links:
                if DEBUG:
                    print(f"⚠️ No results for {company}, retrying with fallback query...")
                fallback = f'site:({company}.com OR myworkdayjobs.com OR lever.co OR greenhouse.io) "{company}" "data" "United States"'
                links = get_google_results(fallback)

            if DEBUG:
                print(f"Found {len(links)} links: {links}")

            fresh_links = [l for l in links if l not in seen]
            if fresh_links:
                new_results[company] = fresh_links
                seen.update(fresh_links)

            time.sleep(1)  # avoid too many Google requests quickly
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

        send_email("🚨 New Entry-Level U.S. Job Posted", body)
        print(f"✅ Email sent with {len(new_results)} company updates.")
    else:
        print("No new U.S. jobs found. (Try relaxing filters or wait for new postings.)")

    save_seen(seen)


if __name__ == "__main__":
    main()
