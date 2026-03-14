import os
import re
import sys
import json
import csv
import urllib.request
import urllib.parse
import time
import datetime
from pathlib import Path
from jobspy import scrape_jobs
import pandas as pd
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# 1. SETUP & SECRETS
# ─────────────────────────────────────────────
load_dotenv()

GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")

RESUME_TEXT = os.getenv("MY_RESUME", None)

if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing API Keys! Set GEMINI_API_KEY and TELEGRAM_BOT_TOKEN in .env or GitHub Secrets.")

# ─────────────────────────────────────────────
# 2. CONFIGURATION
# ─────────────────────────────────────────────
SEARCH_STRATEGIES   = [
    "Engineering Manager DevOps",
    "Platform Engineering Manager",
    "Technical Lead Platform",
]
LOCATIONS           = ["Bangalore", "Hyderabad", "Chennai"]
RESULTS_PER_SEARCH  = 10
HOURS_OLD           = 72
TARGET_SITES        = ["indeed", "linkedin"]

AI_SCORE_THRESHOLD  = 45        # ✅ FIX: Lowered from 55 → 45 (Gemini scores conservatively)
AI_MAX_JOBS         = 10
AI_INTER_CALL_SLEEP = 15
AI_RETRY_BASE_WAIT  = 20
AI_RETRIES          = 3

SEEN_JOBS_FILE      = Path("seen_jobs.json")
RESULTS_LOG_FILE    = Path("matched_jobs.csv")

# ─────────────────────────────────────────────
# 3. RESUME
# ─────────────────────────────────────────────
MY_RESUME = RESUME_TEXT or """
NAME: [Your Name - set MY_RESUME env var or edit here]

PROFESSIONAL SUMMARY
Platform Engineering Manager with 16+ years of experience transforming legacy operations
into high-performance, AI-driven DevOps cultures. Currently leading a 7-member engineering
squad to build self-service Internal Developer Platforms (IDP) on Azure & AWS. Expert in
FinOps governance (saving $200k+ annually) and leveraging Generative AI to automate
workflows. Proven track record of scaling delivery for 50+ applications while cutting
release cycles by 40%. Seeking a Senior Manager role to drive platform strategy and
engineering excellence.

CORE SKILLS
Platform Strategy: Platform Engineering, IDP, SRE, FinOps, DevSecOps.
Cloud & Infrastructure: Azure, AWS, Kubernetes (AKS/EKS), Docker, Helm, Terraform, Ansible.
AI & Automation: Generative AI (ChatGPT/Claude), LLMOps, Python, Bash, Prompt Engineering.
Leadership: Engineering Management (team of 7), Hiring, Appraisals, Agile/Scrum.

EXPERIENCE
Associate Manager – Platform Engineering & DevOps | Apr 2025 – Present
- Manage squad of 7 DevOps engineers; scaled from 5 to 7 members.
- Led AI-First DevOps initiative; boosted team productivity by 20%.
- FinOps: saved $200k+/year across 50+ Azure/AWS applications.
- GitOps & self-service pipelines: cut release cycles by 40%.

Technical Lead – DevOps & SRE | Sep 2022 – Mar 2025
- Led pod of 6 engineers; CI/CD transformation for 30+ projects.
- Terraform & GitHub Actions: cut provisioning time by 50%.
- DevSecOps: SonarQube, Veracode, HashiCorp Vault — reduced vulnerabilities by 15%.

Associate Technical Lead | Jan 2018 – Sep 2022
- AKS/OpenShift migration for 40+ production workloads.
- Classic → YAML/GitOps pipeline transition; cut deployment costs by 15%.

Principal Software Engineer | Oct 2016 – Dec 2018
- Azure DevOps & TFS pipeline modernization; reduced build times by 20%.

Senior Software Engineer | Feb 2013 – Oct 2016
- Jenkins automation; Git & TFS enterprise version control.

EDUCATION
Master of Science (Physics), Andhra University, 2004
"""

# ─────────────────────────────────────────────
# 4. SEEN-JOBS DEDUPLICATION
# ─────────────────────────────────────────────
def load_seen_jobs() -> set:
    if SEEN_JOBS_FILE.exists():
        try:
            return set(json.loads(SEEN_JOBS_FILE.read_text()))
        except Exception:
            return set()
    return set()

def save_seen_jobs(seen: set):
    SEEN_JOBS_FILE.write_text(json.dumps(list(seen), indent=2))

# ─────────────────────────────────────────────
# 5. RESULTS LOGGING
# ─────────────────────────────────────────────
def log_match_to_csv(title, location, score, url):
    is_new = not RESULTS_LOG_FILE.exists()
    with open(RESULTS_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "title", "location", "score", "url"])
        writer.writerow([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            title, location, score, url
        ])

# ─────────────────────────────────────────────
# 6. TELEGRAM NOTIFICATION
# ─────────────────────────────────────────────
def send_telegram_message(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"   ⚠️ Telegram error: {e}")
        return False

# ─────────────────────────────────────────────
# 7. KEYWORD FILTER
# ─────────────────────────────────────────────
EXCLUDE_TITLE_KEYWORDS = [
    'quality assurance', 'qa engineer', 'test engineer', 'sdet',
    'data analyst', 'business analyst', 'sales', 'support engineer',
    'junior', 'intern', 'entry level',
    'network engineer', 'help desk', 'service desk',
    'director', 'vp', 'vice president', 'head of', 'chief',
    'distinguished', 'chemist', 'scientist', 'researcher', 'medical', 'pharma',
]

PERFECT_TITLE_KEYWORDS = [
    'engineering manager', 'platform manager', 'devops manager',
    'sre manager', 'infrastructure manager', 'technical manager',
    'engineering lead', 'technical lead', 'team lead', 'devops lead',
    'manager, platform', 'manager, devops', 'manager, infrastructure',
    'associate manager', 'delivery manager',
    'software engineering manager', 'software manager',
    'manager sw', 'sw engineering', 'manager 3', 'manager ii', 'manager iii',
]

SKILL_KEYWORDS = [
    'kubernetes', 'k8s', 'aks', 'eks', 'azure', 'aws', 'cloud',
    'platform engineering', 'platform', 'internal developer platform', 'idp',
    'terraform', 'infrastructure as code', 'iac', 'ansible', 'helm',
    'finops', 'cost optimization', 'gitops', 'ci/cd', 'devops', 'sre',
    'docker', 'container', 'team lead', 'engineering management', 'manage team',
    'generative ai', 'llm', 'prompt engineering', 'python', 'bash',
]

def keyword_prefilter(title, description) -> tuple[bool, str, int]:
    title_lower = str(title).lower() if title else ""
    desc_lower  = str(description).lower() if description else ""

    for kw in EXCLUDE_TITLE_KEYWORDS:
        if kw in title_lower:
            return False, f"Excluded: '{kw}' in title", 0

    for kw in PERFECT_TITLE_KEYWORDS:
        if kw in title_lower:
            skill_matches = sum(1 for s in SKILL_KEYWORDS if s in desc_lower)
            priority = 100 + skill_matches
            return True, f"Perfect title match (+{skill_matches} skills)", priority

    if len(desc_lower) < 100:
        return False, "Description too short to evaluate", 0

    skill_matches = sum(1 for s in SKILL_KEYWORDS if s in desc_lower)

    if skill_matches >= 2:
        has_leadership = ('manager' in title_lower or 'lead' in title_lower)
        priority = 50 + skill_matches + (20 if has_leadership else 0)
        return True, f"Skill match ({skill_matches} skills)", priority

    if ('manager' in title_lower or 'lead' in title_lower) and skill_matches >= 1:
        return True, "Leadership + tech skill", 30 + skill_matches

    return False, "Not relevant", 0

# ─────────────────────────────────────────────
# 8. GEMINI AI — with retry logic
# ─────────────────────────────────────────────
def ask_gemini(prompt: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    headers = {'Content-Type': 'application/json'}
    data = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode('utf-8')

    for attempt in range(1, AI_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                return result['candidates'][0]['content']['parts'][0]['text']

        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = AI_RETRY_BASE_WAIT * attempt
                print(f" [Rate limited — waiting {wait}s, attempt {attempt}/{AI_RETRIES}]", end="", flush=True)
                time.sleep(wait)
            else:
                print(f" [HTTP {e.code} — retrying {attempt}/{AI_RETRIES}]", end="", flush=True)
                time.sleep(5 * attempt)

        except Exception as e:
            print(f" [Error: {e} — retrying {attempt}/{AI_RETRIES}]", end="", flush=True)
            time.sleep(5 * attempt)

    print(f" [Failed after {AI_RETRIES} retries]", end="")
    return "0"

def parse_score(raw: str) -> int:
    match = re.search(r'\b(\d{1,3})\b', raw)
    if match:
        val = int(match.group(1))
        return max(0, min(val, 100))
    return 0

# ─────────────────────────────────────────────
# ✅ FIX: Rewritten scoring prompt with explicit rubric
#    Old prompt asked Gemini to be a "recruiter" which
#    made it rate conservatively and penalise location.
#    New prompt gives a clear rubric and focuses only on
#    skills + seniority — location is already handled by
#    the scraper so we don't penalise for it here.
# ─────────────────────────────────────────────
def build_score_prompt(job_title, job_company, job_location, desc_truncated):
    return f"""You are a helpful job-matching assistant. Your task is to score how well
a candidate's profile matches a job posting, based ONLY on:
  1. Technical skills overlap (cloud, DevOps, platform engineering tools)
  2. Seniority and leadership level match
  3. Domain/industry relevance

DO NOT penalise for location — location fit is handled separately.
DO NOT penalise for minor skill gaps if the overall profile is a strong fit.

Use this rubric:
  90–100 = Near-perfect match: seniority, skills, and domain all align tightly
  70–89  = Strong match: most key skills present, seniority fits
  50–69  = Decent match: some skills align, minor seniority or domain gaps
  30–49  = Weak match: relevant background but significant gaps
  0–29   = Poor match: different domain or seniority level entirely

CANDIDATE PROFILE:
{MY_RESUME}

JOB TITLE: {job_title}
COMPANY: {job_company}
LOCATION: {job_location}
JOB DESCRIPTION:
{desc_truncated}

Respond with ONLY a single integer between 0 and 100. No explanation. No text. Just the number.
"""

# ─────────────────────────────────────────────
# 9. MAIN
# ─────────────────────────────────────────────
def start_hunting():
    print("=" * 60)
    print(f"🚀 Job Hunter  |  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    print("\n🔌 Testing connections...")

    print("   - Gemini AI...", end="", flush=True)
    test_response = ask_gemini("Reply with the single word OK and nothing else.")
    if "OK" in test_response.upper():
        print(" ✅")
    else:
        print(f" ⚠️  (Got: '{test_response[:40]}' — will retry per job)")

    print("   - Telegram...", end="", flush=True)
    tg_ok = send_telegram_message("🤖 <b>Job Hunter started!</b>")
    print(" ✅" if tg_ok else " ⚠️  (Check TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")

    seen_jobs = load_seen_jobs()
    print(f"\n📋 Previously seen jobs: {len(seen_jobs)}")

    all_frames = []
    for search_location in LOCATIONS:
        for search_term in SEARCH_STRATEGIES:
            print(f"\n🕵️  Scraping: '{search_term}' in {search_location}...", flush=True)
            try:
                time.sleep(2)
                jobs_df = scrape_jobs(
                    site_name=TARGET_SITES,
                    search_term=search_term,
                    location=f"{search_location}, India",
                    results_wanted=RESULTS_PER_SEARCH,
                    hours_old=HOURS_OLD,
                    country_indeed='India',
                )
                print(f"   Found {len(jobs_df)} jobs")
                all_frames.append(jobs_df)
            except Exception as e:
                print(f"   ⚠️  Scrape error: {e}")
                continue

    if not all_frames:
        msg = "❌ No jobs scraped from any source."
        print(f"\n{msg}")
        send_telegram_message(f"🤖 {msg}")
        return

    jobs = pd.concat(all_frames, ignore_index=True)
    jobs = jobs.drop_duplicates(subset=['job_url'], keep='first')
    print(f"\n✅ Total unique jobs scraped: {len(jobs)}")

    new_jobs = jobs[~jobs['job_url'].isin(seen_jobs)].copy()
    skipped = len(jobs) - len(new_jobs)
    print(f"   Skipping {skipped} already-seen jobs → {len(new_jobs)} new to evaluate")

    if new_jobs.empty:
        msg = "🤖 Job Hunter finished — no new jobs since last run."
        print(f"\n{msg}")
        send_telegram_message(msg)
        return

    print(f"\n🔍 PHASE 1: Keyword Filtering ({len(new_jobs)} jobs)...")
    promising = []
    for _, job in new_jobs.iterrows():
        title = job.get('title', 'Unknown')
        desc  = str(job.get('description', '') or '')
        is_match, reason, priority = keyword_prefilter(title, desc)
        if is_match:
            promising.append((priority, job, reason))
            print(f"   ✅ [{priority:>3}] {str(title)[:55]} — {reason}")

    if not promising:
        msg = "🤖 Job Hunter finished — no promising jobs after keyword filter."
        print(f"\n❌ {msg}")
        send_telegram_message(msg)
        seen_jobs.update(new_jobs['job_url'].tolist())
        save_seen_jobs(seen_jobs)
        return

    promising.sort(key=lambda x: x[0], reverse=True)
    print(f"\n🎯 {len(promising)} jobs passed keyword filter (sorted by priority)")

    to_analyze = promising[:AI_MAX_JOBS]
    print(f"\n🤖 PHASE 2: AI Analysis on top {len(to_analyze)} jobs (cap={AI_MAX_JOBS})...")

    matched_count = 0

    for i, (priority, job, kw_reason) in enumerate(to_analyze, 1):
        job_title    = job.get('title', 'Unknown')
        job_location = job.get('location', 'Unknown')
        job_url      = job.get('job_url', '#')
        job_company  = job.get('company', 'Unknown')

        raw_desc = job.get('description', '')
        desc = str(raw_desc) if raw_desc and str(raw_desc).lower() != 'nan' else "No description available."
        desc_truncated = desc[:2000]

        print(f"\n   [{i}/{len(to_analyze)}] {str(job_title)[:50]}", end="", flush=True)
        print(f"\n   🏢 {job_company} | 📍 {job_location}", flush=True)

        # ✅ FIX: Use the new rubric-based prompt
        prompt = build_score_prompt(job_title, job_company, job_location, desc_truncated)

        print(f"   🤖 Scoring...", end="", flush=True)
        raw_score = ask_gemini(prompt)
        score = parse_score(raw_score)

        # ✅ FIX: Warn if score looks unparseable (helps debug future issues)
        if score == 0 and raw_score.strip() not in ("0", "00"):
            print(f" ⚠️  (Could not parse score from: '{raw_score[:40]}')")
        else:
            print(f" {score}%")

        if score >= AI_SCORE_THRESHOLD:
            matched_count += 1
            log_match_to_csv(job_title, job_location, score, job_url)

            bar = "🟩" * (score // 10) + "⬜" * (10 - score // 10)
            message = (
                f"🎯 <b>MATCH FOUND! Score: {score}%</b>\n"
                f"{bar}\n\n"
                f"<b>{job_title}</b>\n"
                f"🏢 {job_company}\n"
                f"📍 {job_location}\n"
                f"🔑 Filter: {kw_reason}\n\n"
                f"<a href='{job_url}'>👉 APPLY NOW</a>"
            )
            tg_sent = send_telegram_message(message)
            if not tg_sent:
                print(f"   ⚠️  Telegram failed — match saved to {RESULTS_LOG_FILE}")

        if i < len(to_analyze):
            time.sleep(AI_INTER_CALL_SLEEP)

    all_evaluated_urls = [job.get('job_url', '') for _, job, _ in promising]
    seen_jobs.update(all_evaluated_urls)
    save_seen_jobs(seen_jobs)
    print(f"\n💾 Updated seen_jobs.json ({len(seen_jobs)} total URLs tracked)")

    summary = (
        f"🤖 <b>Job Hunt Complete!</b>\n\n"
        f"📊 Scraped: {len(jobs)} jobs\n"
        f"🆕 New this run: {len(new_jobs)}\n"
        f"🔍 Passed keyword filter: {len(promising)}\n"
        f"🤖 AI analyzed: {len(to_analyze)}\n"
        f"🎯 Matches (≥{AI_SCORE_THRESHOLD}%): {matched_count}\n\n"
        f"📁 Full log: matched_jobs.csv"
    )
    print(f"\n{'='*60}")
    print(summary.replace('<b>', '').replace('</b>', ''))
    print('='*60)
    send_telegram_message(summary)


if __name__ == "__main__":
    start_hunting()
