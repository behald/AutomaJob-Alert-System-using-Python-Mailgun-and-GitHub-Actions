# Job Alerts (U.S. Data / Analytics / Engineering Roles)

This project is a **job alert bot** for people (especially international students) who want to target **H1B-friendly companies** and get **U.S.-based entry-level job links** by email.

It:
- reads a list of companies from a CSV,
- searches Google for job postings (last 1 month),
- keeps only real job-board links,
- removes duplicates using a “seen links” file,
- emails you **only the new links** using **Mailgun**.

---

## Proof (Automation + Email Working)

> After you push the screenshots to GitHub, these images will show as proof that the system works end-to-end.

### GitHub Actions scheduled runs (automation proof)
![GitHub Actions scheduled runs](screenshots/actions_result.png)

### Mailgun email received (notification proof)
![Mailgun email success](screenshots/mailgun_notifications%20work%20.png)

---

## Why I built this

When you apply for jobs, the hardest part is staying consistent and checking many company career pages every day.

This bot makes that easier:
- you provide the company list once,
- run the script daily/weekly,
- and you get an email when **new roles** show up.

---

## What’s inside this repo

- `main.py`  
  The full script: search → filter → dedupe → email

- `company_data.csv`  
  Company list (must include column: `EMPLOYER_NAME`)  
  In your file, there are **143 companies** and an extra column `New Employment Approval` (this column is not used by the script right now, but it’s useful info to keep).

- `seen_jobs.json`  
  Stores links that were already sent earlier (so you don’t get repeats)

- `requirements.txt`  
  Python dependencies

- `render.yaml`  
  Render deployment config (worker)

---

## Key features (what this bot does well)

✅ **Company-based searching**  
Searches jobs for each company in your CSV.

✅ **U.S. focused search**  
Search query includes `"United States"` and uses Google’s **last 1 month** filter.

✅ **Job-board filtering**  
Keeps only links that look like job pages (Workday, Greenhouse, Lever, SmartRecruiters, iCIMS, Jobvite, etc.)

✅ **Dedupe (no repeated alerts)**  
If a link is already in `seen_jobs.json`, it is skipped.

✅ **Email alerts (Mailgun)**  
Sends one email that groups results **company-wise**.

**Mailgun proof (email received):**  
![Mailgun email success](screenshots/mailgun_notifications%20work%20.png)

✅ **Safer scraping pace**  
Waits ~1.5 seconds between companies.

✅ **GitHub Actions automation**  
Runs automatically on a schedule and can commit updated `seen_jobs.json` back to the repo.

**Automation proof (runs in Actions):**  
![GitHub Actions scheduled runs](screenshots/actions_result.png)

---

## Tech stack

- Python
- pandas (CSV reading)
- requests (HTTP)
- BeautifulSoup (HTML parsing)
- Mailgun API (sending email)
- GitHub Actions (automation + schedule)
- Render (deployment)

---

## How it works (deep, step-by-step)

### Step 1: Load company list
- Reads `company_data.csv`
- Validates that `EMPLOYER_NAME` exists
- Makes a Python list of company names

### Step 2: Load seen links
- Reads `seen_jobs.json`
- Converts it into a Python `set()` for fast “already seen?” checks

### Step 3: Build a Google search query per company
For each company, the script builds a query like:
- search within common job platforms:
  - `company.myworkdayjobs.com`
  - `careers.company.com`
  - `greenhouse.io`
  - `lever.co`
- and search for roles like:
  - data / analytics / engineer / analyst
- and include:
  - `"United States"`

### Step 4: Scrape Google results (HTML)
The script hits a URL like:
- `https://www.google.com/search?q=...&num=30&tbs=qdr:m`

Important details:
- `num=30` → tries to fetch up to 30 results
- `tbs=qdr:m` → **last 1 month**

Then it:
- parses the page HTML using BeautifulSoup
- finds `<a href="...">` links
- keeps only links that start with `/url?q=` (Google result links)
- extracts the real URL from that format

**Proof (script logs running inside automation):**  
![Script logs - Google queries + retry](screenshots/script_result.png)

![Script logs - continued](screenshots/script_result_2.png)

### Step 5: Clean + filter links
The script drops:
- Google internal links
- Google account links
- Google maps links
- PDFs

Then it keeps only links that match these patterns:
- `greenhouse.io`
- `myworkdayjobs.com`
- `lever.co`
- `smartrecruiters.com`
- `careers.`
- `.jobs`
- `apply.`
- `workwithus.`
- `jobvite.com`
- `icims.com`

Then it skips links that look **non-U.S.** using path checks like:
- `/uk/`, `/ca/`, `/in/`, `/au/`, `/eu/`, `/sg/`, `/de/`, `/fr/`, `/ph/`, `/mx/`

### Step 6: Keep only “new” links
For each company:
- `fresh_links = [link for link in links if link not in seen]`
- If there are fresh links:
  - store them under that company
  - add them into `seen`

### Step 7: Build the email (HTML)
If at least one company has new links, it builds an email like:
- Title: “New U.S. Job Alerts (date/time)”
- Then for each company:
  - company name in bold
  - clickable job links underneath

### Step 8: Send the email via Mailgun
The script calls Mailgun’s `/messages` endpoint.

Extra smart check included:
- If you paste an API key without `key-`, it auto-fixes it.

**Proof (workflow shows email sent):**  
![Workflow shows email sent](screenshots/script_result_3.png)

### Step 9: Save `seen_jobs.json`
At the end:
- it writes the updated “seen links” back to `seen_jobs.json`

So next run = no repeats.

---

## Folder / file structure

```text
.
├── main.py
├── company_data.csv
├── seen_jobs.json
├── requirements.txt
├── render.yaml
└── screenshots/
    ├── actions_result.png
    ├── mailgun_notifications work .png
    ├── script_result.png
    ├── script_result_2.png
    └── script_result_3.png

