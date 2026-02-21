import os
import sys
import json
import urllib.request
import urllib.parse
import time
from jobspy import scrape_jobs
import pandas as pd
from dotenv import load_dotenv

# --- 1. SETUP & SECRETS ---
load_dotenv() # Load local .env file

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing API Keys! Check your .env file (local) or GitHub Secrets.")

# --- 2. TELEGRAM NOTIFICATION ---
def send_telegram_message(message):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req) as response:
            return True
    except Exception as e:
        print(f"   (Telegram Error: {e})")
        return False

# --- 3. SMART KEYWORD FILTER ---
def keyword_prefilter(title, description):
    # Ensure inputs are strings to prevent errors
    title_lower = str(title).lower() if title else ""
    desc_lower = str(description).lower() if description else ""
    
    # HARD EXCLUDE
    exclude_in_title = [
        'quality assurance', 'qa engineer', 'test engineer', 'sdet',
        'data analyst', 'business analyst', 'sales', 'support engineer',
        'junior', 'intern', 'entry level',
        'network engineer', 'help desk', 'service desk',
        'director', 'vp', 'vice president', 'head of', 'chief',
        'distinguished', 'chemist', 'scientist', 'researcher', 'medical', 'pharma'
    ]
    
    for exclude in exclude_in_title:
        if exclude in title_lower:
            return False, "Wrong level/role"
    
    # TARGET ROLES
    perfect_titles = [
        'engineering manager', 'platform manager', 'devops manager',
        'sre manager', 'infrastructure manager', 'technical manager',
        'engineering lead', 'technical lead', 'team lead', 'devops lead',
        'manager, platform', 'manager, devops', 'manager, infrastructure',
        'associate manager', 'delivery manager', 
        'software engineering manager', 'software manager',
        'manager sw', 'sw engineering', 'manager 3', 'manager ii', 'manager iii'
    ]
    
    for keyword in perfect_titles:
        if keyword in title_lower:
            return True, "Perfect title match"
    
    if len(desc_lower) < 100:
        return False, "Need description to evaluate"
    
    # SKILLS
    your_skills = [
        'kubernetes', 'k8s', 'aks', 'eks', 'azure', 'aws', 'cloud',
        'platform engineering', 'platform', 'internal developer platform', 'idp',
        'terraform', 'infrastructure as code', 'iac', 'ansible', 'helm',
        'finops', 'cost optimization', 'gitops', 'ci/cd', 'devops', 'sre',
        'docker', 'container', 'team lead', 'engineering management', 'manage team',
        'generative ai', 'llm', 'prompt engineering', 'python', 'bash'
    ]
    
    skill_matches = sum(1 for skill in your_skills if skill in desc_lower)
    
    if skill_matches >= 2:
        return True, f"Skill match ({skill_matches} skills)"
    
    if ('manager' in title_lower or 'lead' in title_lower) and skill_matches >= 1:
        return True, "Leadership + tech skills"
    
    return False, "Not relevant"

# --- 4. AI FUNCTION ---
def ask_gemini_stealth(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return result['candidates'][0]['content']['parts'][0]['text']
    except urllib.error.HTTPError as e:
        print(f"   (AI Error: HTTP {e.code})", end="")
        return "0"
    except Exception as e:
        print(f"   (AI Error: {e})", end="")
        return "0"

# --- 5. CONFIGURATION ---
SEARCH_STRATEGIES = ["Engineering Manager DevOps", "Platform Engineering Manager", "Technical Lead Platform"]
LOCATIONS = ["Bangalore", "Hyderabad", "Chennai"]
RESULTS_PER_SEARCH = 10
HOURS_OLD = 72
TARGET_SITES = ["indeed", "linkedin"]

MY_RESUME = """
Shaik Noor Ahamed
📍 Bengaluru, India | 📞 +91-8123532127 | ✉️ ahamed338@gmail.com | 🔗 linkedin.com/in/ahamed-shaik-9ba020191

PROFESSIONAL SUMMARY
Platform Engineering Manager with 16+ years of experience transforming legacy operations into high-performance, AI-driven DevOps cultures. Currently leading a 7-member engineering squad to build self-service Internal Developer Platforms (IDP) on Azure & AWS. Expert in FinOps governance (saving $200k+ annually) and leveraging Generative AI to automate workflows. Proven track record of scaling delivery for 50+ applications while cutting release cycles by 40%. Seeking a Senior Manager role to drive platform strategy and engineering excellence.

CORE SKILLS
Platform Strategy: Platform Engineering, Internal Developer Platform (IDP), Site Reliability Engineering (SRE), FinOps (Cloud Cost Optimization), DevSecOps.
Cloud & Infrastructure: Azure, AWS, Kubernetes (AKS/EKS), Docker, Helm, Terraform (IaC), Ansible.
AI & Automation: Generative AI Integration (ChatGPT/Claude), LLM Ops, Python, Bash, Prompt Engineering.
Leadership: Engineering Management (Team of 7), Performance Reviews, Tech Hiring, Agile/Scrum Delivery, Stakeholder Management.

PROFESSIONAL EXPERIENCE
First American (India) Pvt. Ltd. | Bengaluru,  India
Associate Manager – Platform Engineering & DevOps (Functionally: Engineering Manager)
Apr 2025 – Present
* Engineering Leadership: Manage a high-performing squad of 7 DevOps Engineers, handling hiring, performance appraisals, and career coaching. Scaled team from 5 to 7 members to support enterprise platform growth.
* GenAI Innovation: Pioneered the “AI-First” DevOps initiative, training the team on Prompt Engineering and integrating ChatGPT/Claude to automate documentation and troubleshooting, boosting team productivity by 20%.
* FinOps & Cost Strategy: Spearheaded multi-cloud (Azure/AWS) cost optimization for 50+ applications, achieving $200k+ in annual savings (20% reduction) through rightsizing and automated governance.
* Platform Transformation: Directed the transition to GitOps and self-service pipelines, successfully slashing release cycles by 40% and increasing Agile sprint velocity by 18%. 

Technical Lead – DevOps & SRE
Sep 2022 – Mar 2025
* Team Leadership: Led a pod of 6 engineers, driving the CI/CD transformation for 30+ critical projects while acting as the de-facto delivery lead.
* Infrastructure as Code: Architected scalable Terraform & GitHub Actions pipelines, reducing environment provisioning time by 50%.
* Security (DevSecOps): Integrated SonarQube, Veracode, and HashiCorp Vault into the release path, reducing production vulnerabilities by 15%.

Associate Technical Lead | Jan 2018 – Sep 2022
Coordinated team of 4-5 engineers through AKS and OpenShift migration for 40+ production workloads
Led daily standups, sprint planning, and delivery coordination while managing cross-team dependencies
Migrated legacy applications to Kubernetes, improving scalability by 30% and reducing infrastructure overhead
Transitioned pipelines from Classic → YAML/GitOps, reducing deployment costs by 15%.

Principal Software Engineer | Oct 2016 – Dec 2018
Modernized release pipelines in Azure DevOps & TFS, reducing build times by 20%.
Enabled automated testing frameworks, lowering production defects by 10%.

SLK Software Services Pvt. Ltd. | Bengaluru, India
Senior Software Engineer | Feb 2013 – Oct 2016
Automated build & deployment processes using Jenkins, improving release speed.
Managed Git & TFS version control for enterprise-scale applications.

Patra India Pvt. Ltd. | Hyderabad, India
Application Support Engineer | Aug 2007 – Nov 2012
Delivered 99% uptime in production environments through proactive monitoring.
Improved SLA adherence with automation scripts (Bash/PowerShell).

KEY PROJECTS & IMPACT
Cloud Migration: Migrated legacy apps to AKS/OpenShift, cutting deployment time by 20%.
CI/CD Optimization: Implemented YAML & GitOps pipelines, reducing new project setup time by 30%.
Cost Savings: Applied FinOps & automation strategies, saving 25% in infrastructure costs.
DevSecOps: Integrated Vault, SonarQube, Veracode, strengthening cloud security posture.
Tool Modernization: Transitioned from TFS → Azure DevOps, cutting tool maintenance cost by 20%.

EDUCATION
Master of Science (Physics), Andhra University, 2004
"""

def start_hunting():
    print(f"🔌 Testing Connections...")
    
    # Test Gemini
    print(f"   - Gemini AI...", end="")
    test = ask_gemini_stealth("Reply 'OK'")
    if "OK" not in test:
        print(f" ❌ Failed")
    else:
        print(" ✅")
    
    # Test Telegram
    print(f"   - Telegram...", end="")
    if send_telegram_message("🤖 Job Hunter Started!"):
        print(" ✅")
    else:
        print(" ⚠️ (Optional)")
    
    all_jobs = []
    for location in LOCATIONS:
        for search_term in SEARCH_STRATEGIES:
            print(f"\n🕵️‍♂️ Scraping: '{search_term}' in {location}...")
            try:
                time.sleep(2) 
                jobs = scrape_jobs(
                    site_name=TARGET_SITES,
                    search_term=search_term,
                    location=f"{location}, India",
                    results_wanted=RESULTS_PER_SEARCH,
                    hours_old=HOURS_OLD,
                    country_indeed='India'
                )
                print(f"   Found {len(jobs)} jobs")
                all_jobs.append(jobs)
            except Exception as e:
                print(f"   ⚠️ Error: {e}")
                continue
    
    if not all_jobs:
        print("\n❌ No jobs found.")
        return
    
    jobs = pd.concat(all_jobs, ignore_index=True)
    jobs = jobs.drop_duplicates(subset=['job_url'], keep='first')
    print(f"\n✅ Total unique jobs found: {len(jobs)}")
    
    # Phase 1: Filtering
    promising_jobs = []
    for index, job in jobs.iterrows():
        title = job.get('title', 'Unknown')
        
        # Safe description handling for filtering
        raw_desc = job.get('description')
        description = str(raw_desc) if raw_desc else ""
        
        is_match, reason = keyword_prefilter(title, description)
        
        if is_match:
            promising_jobs.append(job)
            print(f"   ✅ {str(title)[:50]} - {reason}")

    if not promising_jobs:
        print("\n❌ No promising jobs found.")
        return
    
    # Phase 2: AI Analysis
    print(f"\n🤖 PHASE 2: AI Analysis on {len(promising_jobs)} promising jobs...")
    
    for i, job in enumerate(promising_jobs):
        if i >= 10: break # Limit calls
        
        title = job.get('title', 'Unknown')
        location = job.get('location', 'Unknown')
        apply_url = job.get('job_url', '#')
        
        # --- CRITICAL FIX: HANDLE NONE & FLOAT DESCRIPTIONS ---
        raw_desc = job.get('description')
        description = str(raw_desc) # Convert NaN/Float/None to string "nan" or "None"
        
        # Check if it's truly empty or just "nan" text
        if not raw_desc or description.lower() == 'nan':
            description = "No description available for this job."
            
        desc_truncated = description[:1500] 
        
        print(f"\n   Analyzing: {str(title)[:35]}...", end="")
        
        prompt = f"""
        Score match (0-100).
        RESUME: {MY_RESUME}
        JOB: {title} in {location}
        DESC: {desc_truncated}
        Output ONLY number.
        """
        
        score_text = ask_gemini_stealth(prompt)
        
        # --- RATE LIMIT FIX: SLOW DOWN ---
        # print(" (cooling down)...", end="")
        time.sleep(10) # Increased to 10s to avoid 429 Errors
        
        try:
            score = int(''.join(filter(str.isdigit, score_text)))
        except:
            score = 0
        
        print(f" {score}%")
        
        if score >= 55:
            message = f"🎯 <b>MATCH: {score}%</b>\n\n<b>{title}</b>\n📍 {location}\n\n<a href='{apply_url}'>👉 APPLY NOW</a>"
            send_telegram_message(message)

if __name__ == "__main__":
    start_hunting()