import pandas as pd
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json, os, time

# --- CONFIG ---
FROM_EMAIL = "h1b.job.alerts@gmail.com"
TO_EMAIL = "behal.divaye@gmail.com"
EMAIL_PASSWORD = "bhux ajec utjz ovby"  # <-- replace this
CSV_FILE = "company_data.csv"
SEEN_FILE = "seen_jobs.json"
CHECK_INTERVAL = 300  # 300 seconds = 5 minutes

# --- BUILD SEARCH QUERY ---
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
    query = (
        f'(site:careers.{company_clean}.com OR site:greenhouse.io OR site:myworkdayjobs.com OR site:lever.co) '
        f'({exp_keywords}) AND ({role_keywords})'
    )
    return query

# --- SCRAPE GOOGLE RESULTS ---
def get_google_results(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    links = []
    for g in soup.find_all("a"):
        href = g.get("href", "")
        if href.startswith("/url?q="):
            clean_link = href.split("/url?q=")[1].split("&")[0]
            if "careers" in clean_link or "jobs" in clean_link:
                links.append(clean_link)
    return links[:5]

# --- LOAD/SAVE SEEN JOBS ---
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

# --- EMAIL FUNCTION ---
def send_email(subject, body):
    msg = MIMEMultipart("alternative")
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(FROM_EMAIL, EMAIL_PASSWORD)
        server.send_message(msg)

# --- MAIN FUNCTION ---
def main():
    df = pd.read_csv(CSV_FILE)
    companies = df["EMPLOYER_NAME"].dropna().head(150)

    seen = load_seen()
    new_results = {}

    for company in companies:
        try:
            query = build_query(company)
            links = get_google_results(query)
            fresh_links = [l for l in links if l not in seen]
            if fresh_links:
                new_results[company] = fresh_links
                for l in fresh_links:
                    seen.add(l)
        except Exception as e:
            print(f"Error fetching {company}: {e}")

    if new_results:
        today = datetime.now().strftime("%b %d, %Y %H:%M")
        body = f"<h3>🚨 New Job Alerts ({today})</h3><br>"
        for company, links in new_results.items():
            body += f"<b>{company}</b><br>"
            for l in links:
                body += f'→ <a href="{l}">{l}</a><br>'
            body += "<br>"
        send_email("🚨 New Entry-Level Job Posted", body)
        print(f"✅ Email sent with {len(new_results)} new updates.")
    else:
        print("No new jobs found.")
    save_seen(seen)

# --- LOOP EVERY 5 MINUTES ---
if __name__ == "__main__":
    while True:
        main()
        time.sleep(CHECK_INTERVAL)
