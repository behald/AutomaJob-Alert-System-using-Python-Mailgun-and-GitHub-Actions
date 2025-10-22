import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os

# --- CONFIG ---
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
TO_EMAIL = os.getenv("TO_EMAIL", "behal.divaye@gmail.com")

CSV_FILE = "company_data.csv"
SEEN_FILE = "seen_jobs.json"

# --- BUILD SEARCH QUERY (USA-focused) ---
def build_query(company):
    exp_keywords = (
        '"entry level" OR "new grad" OR "graduate" OR "junior" OR "0-1 years" OR "0-2 years" '
        'OR "master student" OR "recent graduate" OR "early career" OR "fresh graduate"'
    )

    role_keywords = (
        '"data engineer" OR "backend engineer" OR "data analyst" OR "business analyst" OR '
        '"bi engineer" OR "analytics engineer" OR "cloud engineer" OR "software engineer" OR '
        '"data scientist" OR "ml engineer" OR "ai engineer" OR "data analytics" OR '
        '"big data" OR "etl engineer" OR "python developer" OR "sql analyst" OR '
        '"power bi" OR "tableau" OR "aws engineer" OR "azure engineer" OR "gcp engineer"'
    )

    company_clean = company.lower().replace(" ", "")

    # Add "United States" to query
    query = (
        f'(site:careers.{company_clean}.com OR site:greenhouse.io OR site:myworkdayjobs.com OR site:lever.co) '
        f'({exp_keywords}) AND ({role_keywords}) "United States" "{company}"'
    )
    return query


# --- SCRAPE GOOGLE RESULTS (Clean + US Only) ---
def get_google_results(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    links = []
    for g in soup.find_all("a", href=True):
        href = g["href"]
        if href.startswith("/url?q="):
            clean_link = href.split("/url?q=")[1].split("&")[0]

            # Keep only real job-related domains
            if any(domain in clean_link for domain in [
                "greenhouse.io",
                "myworkdayjobs.com",
                "lever.co",
                "careers.",
                "jobs.",
                "boards.",
                "apply.",
                "workwithus.",
                "smartrecruiters.com"
            ]) and not clean_link.startswith("https://maps.google"):
                
                # Skip non-US job URLs
                if any(country in clean_link.lower() for country in [
                    "/uk/", "/ca/", "/in/", "/au/", "/eu/", "/sg/", "/de/", "/fr/", "/ph/", "/mx/"
                ]):
                    continue

                links.append(clean_link)

    # Remove duplicates and limit to 5 links
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


# --- SEND EMAIL (Mailgun API) ---
def send_email(subject, html_body):
    if not MAILGUN_API_KEY or not MAILGUN_DOMAIN:
        print("❌ Mailgun credentials missing. Please set MAILGUN_API_KEY and MAILGUN_DOMAIN.")
        return False

    # Adjust key format (some Mailgun accounts omit "key-" prefix)
    api_key = MAILGUN_API_KEY if MAILGUN_API_KEY.startswith("key-") else f"key-{MAILGUN_API_KEY}"

    response = requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
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
    else:
        print(f"❌ Mailgun error {response.status_code}: {response.text}")
        return False


# --- MAIN JOB ALERT FUNCTION ---
def main():
    if not os.path.exists(CSV_FILE):
        print(f"❌ Missing file: {CSV_FILE}")
        return

    df = pd.read_csv(CSV_FILE)
    if "EMPLOYER_NAME" not in df.columns:
        print("❌ Column 'EMPLOYER_NAME' not found in CSV.")
        return

    # Target all employers from CSV
    companies = df["EMPLOYER_NAME"].dropna().tolist()

    seen = load_seen()
    new_results = {}

    for company in companies:
        try:
            query = build_query(company)
            links = get_google_results(query)
            fresh_links = [l for l in links if l not in seen]
            if fresh_links:
                new_results[company] = fresh_links
                seen.update(fresh_links)
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
        print("No new U.S. jobs found.")

    save_seen(seen)


# --- ENTRYPOINT ---
if __name__ == "__main__":
    main()
