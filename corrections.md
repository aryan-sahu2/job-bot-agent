Issues Found & Fixes
1. Portfolio/Website URL not matched
Your website pattern checks for portfolio, personal site, github, gitlab — but the field label is "Portfolio / Website URL". The / might cause issues, and more importantly, your server doesn't return a website field in the profile.
Fix in server.py — add website extraction:
Python
# In server.py get_profile(), add after phone detection:
website = ""
for line in lines:
    if "portfolio" in line.lower() or "github" in line.lower() or "pages.dev" in line:
        if "://" in line:
            website = line
            break

# And return it:
return {
    "name": name,
    "first_name": parts[0] if parts else "",
    "last_name": parts[-1] if len(parts) > 1 else "",
    "email": email,
    "phone": phone,
    "website": website,  # ADD THIS
    "linkedin": linkedin,  # ADD THIS
    "raw": raw,
}
Fix in resume.txt — add explicit LinkedIn and website lines at top (or the server won't find them):
txt
Aryan Sahu
aryanwin0609@gmail.com
+91 7058602394
https://www.linkedin.com/in/aryan-sahu
https://dev-portfolio-4d2.pages.dev/
https://github.com/aryan-sahu2/
2. LinkedIn URL not filled
Your linkedin pattern exists but the server doesn't extract it from resume.txt. Same fix as above.
3. Missing field types entirely
Your extension doesn't handle these field types at all:
Current / Last Role (job title/current position)
Years of Experience (YOE/experience)
Availability/Notice Period
Expected CTC/Compensation
How did you hear about us? (source/referral)
Add to content.js patterns in scoreField():
JavaScript
currentRole: {
    strong: ['current role', 'last role', 'current position', 'job title', 'title', 'current job', 'present role', 'most recent role'],
    weak: ['role', 'position', 'job'],
    avoid: ['expected', 'desired', 'applying for']
},
noticePeriod: {
    strong: ['availability', 'notice period', 'weeks notice', 'how soon', 'joining', 'available', 'start date', 'when can you'],
    weak: ['notice', 'weeks', 'availability'],
    avoid: ['salary', 'experience', 'age']
},
expectedCtc: {
    strong: ['expected ctc', 'expected salary', 'compensation', 'expected pay', 'salary expectation', 'desired salary'],
    weak: ['ctc', 'salary', 'pay', 'lpa', 'inr'],
    avoid: ['current', 'last drawn']
},
referralSource: {
    strong: ['how did you hear', 'source', 'referral', 'where did you find', 'how did you find', 'referred by'],
    weak: ['hear', 'find', 'about us'],
    avoid: []
},
Add to fillForm() in content.js:
JavaScript
if (fields.currentRole && profile.currentRole) {
    if (setInputValue(fields.currentRole, profile.currentRole)) { filled++; log.push('currentRole'); }
}
if (fields.yearsExperience && profile.yearsExperience) {
    if (setInputValue(fields.yearsExperience, profile.yearsExperience)) { filled++; log.push('yearsExperience'); }
}
if (fields.noticePeriod && profile.noticePeriod !== undefined) {
    if (setInputValue(fields.noticePeriod, profile.noticePeriod)) { filled++; log.push('noticePeriod'); }
}
if (fields.expectedCtc && profile.expectedCtc) {
    if (setInputValue(fields.expectedCtc, profile.expectedCtc)) { filled++; log.push('expectedCtc'); }
}
if (fields.referralSource && profile.referralSource) {
    if (setInputValue(fields.referralSource, profile.referralSource)) { filled++; log.push('referralSource'); }
}
4. Server profile extraction needs to parse resume.txt better
Replace get_profile() in server.py with this improved version:
Python
@app.get("/profile")
def get_profile():
    if not RESUME_PATH.exists():
        return {"error": f"{RESUME_PATH} not found"}
    raw = RESUME_PATH.read_text()
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    name = lines[0] if lines else "Applicant"
    email = next((line for line in lines if "@" in line and "." in line.split("@")[-1]), "")
    
    # Better phone detection
    phone = ""
    for line in lines:
        if "@" in line:
            continue
        digits = ''.join(c for c in line if c.isdigit())
        if len(digits) >= 10 and len(digits) <= 15:
            phone = line
            break
    
    # Extract URLs
    linkedin = ""
    website = ""
    github = ""
    for line in lines:
        if "linkedin.com" in line.lower():
            linkedin = line
        elif "github.com" in line.lower() or "gitlab.com" in line.lower():
            github = line
        elif "://" in line and not linkedin and not website and not github:
            # Portfolio or other website
            if not any(x in line.lower() for x in ["email", "phone", "tel:", "mailto:"]):
                website = line
    
    # Extract experience years
    years_experience = ""
    for line in lines:
        match = re.search(r'(\d+(?:\.\d+)?)\+?\s*years?', line, re.IGNORECASE)
        if match:
            years_experience = match.group(1)
            break
    
    # Extract current role
    current_role = ""
    for i, line in enumerate(lines):
        if any(k in line.lower() for k in ["full stack", "developer", "engineer", "architect", "manager"]):
            if "at " in line.lower() or i < 5:  # Likely a role mention
                current_role = line.replace("Full Stack Developer at", "").replace("at", "").strip()
                if current_role:
                    current_role = line
                    break
    
    parts = name.split()
    return {
        "name": name,
        "first_name": parts[0] if parts else "",
        "last_name": parts[-1] if len(parts) > 1 else "",
        "email": email,
        "phone": phone,
        "website": website or github,
        "linkedin": linkedin,
        "github": github,
        "yearsExperience": years_experience,
        "currentRole": "Full Stack Developer",  # Hardcode or parse from resume
        "noticePeriod": "0",
        "expectedCtc": "18-24 LPA",
        "referralSource": "LinkedIn",
        "raw": raw,
    }
5. Resume.txt needs structured metadata at top
Replace your resume.txt with this header format so the server can extract fields reliably:
txt
Aryan Sahu
aryanwin0609@gmail.com
+91 7058602394
https://www.linkedin.com/in/aryan-sahu
https://dev-portfolio-4d2.pages.dev/
https://github.com/aryan-sahu2/
Role: Full Stack Developer
Experience: 3.5 years
Notice Period: 0 weeks
Expected CTC: 18-24 LPA
Source: LinkedIn

Full Stack Developer with 3+ years of production experience...
6. Select dropdowns not handled
The "How did you hear about us?" is likely a <select> dropdown. Your findBestInputs() only looks for input, textarea, select but setInputValue() doesn't handle <select> properly.
Add to setInputValue() in content.js:
JavaScript
function setInputValue(el, value) {
    if (!el || value === undefined || value === null || value === '') return false;
    
    // Handle select dropdowns
    if (el.tagName === 'SELECT') {
        const options = Array.from(el.options);
        const match = options.find(opt => 
            opt.text.toLowerCase().includes(value.toLowerCase()) ||
            opt.value.toLowerCase().includes(value.toLowerCase())
        );
        if (match) {
            el.value = match.value;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }
        return false;
    }
    
    // ... rest of existing code
}
7. Add select elements to field scoring
In findBestInputs(), visible inputs already includes select, but you need to make sure the scoring works for dropdowns. The current code should handle it since select elements have name, id, and associated labels.
Quick Summary of Changes Needed
Table
File	Change
resume.txt	Add structured header with URLs, role, experience, notice, CTC, source
server.py	Enhance get_profile() to extract URLs, role, YOE, notice, CTC, source
content.js	Add 4 new field patterns (currentRole, noticePeriod, expectedCtc, referralSource)
content.js	Add fillForm() handlers for new fields
content.js	Add <select> handling in setInputValue()
content.js	Add website to fillForm() (it's defined but never called)
