Here's the full fix:
1. Fix getAllTextClues — Search Labels Inside the Same Wrapper
Replace your getAllTextClues with this version that scans the container for labels:
JavaScript
function getAllTextClues(el) {
    const clues = [];
    const add = (s) => { if (s) clues.push(s.toLowerCase().trim()); };

    // Direct attributes
    add(el.placeholder);
    add(el.name);
    add(el.id);
    add(el.getAttribute('aria-label'));
    add(el.getAttribute('data-testid'));
    add(el.getAttribute('automation-id'));
    add(el.getAttribute('data-automation-id'));
    add(el.getAttribute('aria-labelledby'));
    add(el.getAttribute('aria-describedby'));

    // Type hint
    if (el.type && el.type !== 'text') add(el.type);

    // Associated labels (by for=id match)
    if (el.labels) Array.from(el.labels).forEach(l => add(l.innerText));

    // aria-labelledby / aria-describedby dereference
    ['aria-labelledby', 'aria-describedby'].forEach(attr => {
        const ids = el.getAttribute(attr);
        if (ids) {
            ids.split(/\s+/).forEach(id => {
                const el2 = document.getElementById(id);
                if (el2) add(el2.innerText);
            });
        }
    });

    // Parent chain (up to 4 levels)
    let parent = el.parentElement;
    for (let i = 0; i < 4 && parent; i++) {
        if (parent.tagName === 'LABEL') add(parent.innerText);
        const labelChild = parent.querySelector('label, .label, [class*="label"]');
        if (labelChild && labelChild !== el) add(labelChild.innerText);
        parent = parent.parentElement;
    }

    // Previous siblings
    let prev = el.previousElementSibling;
    for (let i = 0; i < 3 && prev; i++) {
        add(prev.innerText);
        prev = prev.previousElementSibling;
    }

    // Next siblings (labels sometimes appear after in odd DOM structures)
    let next = el.nextElementSibling;
    for (let i = 0; i < 2 && next; i++) {
        if (next.tagName === 'LABEL' || (next.innerText && next.innerText.length < 100)) {
            add(next.innerText);
        }
        next = next.nextElementSibling;
    }

    // CRITICAL: Look for ANY label inside the same field wrapper
    // This catches React/Vue forms where label and input are siblings in a div.space-y-2
    const container = el.closest('.space-y-2, .form-field, [class*="field"], [class*="form-group"], [class*="FormItem"], div');
    if (container) {
        const allLabels = container.querySelectorAll('label, [id*="Question"], [class*="label"], [class*="Label"]');
        allLabels.forEach(lbl => {
            if (lbl !== el) add(lbl.innerText);
        });
    }

    // Grandparent first line
    const gp = el.parentElement?.parentElement;
    if (gp) {
        const firstLine = gp.innerText?.split('\n')[0]?.trim();
        if (firstLine && firstLine.length < 100) add(firstLine);
    }

    return clues.filter(c => c.length > 0);
}
2. Update findBestInputs to Return Unmatched Fields
Replace findBestInputs so it returns unmatched inputs for custom question processing:
JavaScript
function findBestInputs() {
    const allInputs = Array.from(document.querySelectorAll('input, textarea, select'));

    const visibleInputs = allInputs.filter(el => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== 'none' && 
               style.visibility !== 'hidden' && 
               rect.width > 5 && rect.height > 5 &&
               !el.disabled &&
               !el.readOnly;
    });

    console.log(`[JobBot] Found ${visibleInputs.length} visible inputs out of ${allInputs.length}`);

    const candidates = {};
    const assigned = new Set();
    const types = [
        'firstName', 'lastName', 'fullName', 
        'email', 'phone', 
        'currentRole', 'yearsExperience', 
        'location', 
        'expectedCtc', 'salary',
        'portfolio', 'github', 'linkedin', 'website',
        'noticePeriod', 'referralSource',
        'coverLetter'
    ];

    for (const type of types) {
        let best = null;
        let bestScore = 0;

        for (const el of visibleInputs) {
            if (assigned.has(el)) continue;
            const clues = getAllTextClues(el);
            const s = scoreField(clues, type);
            if (s > bestScore) {
                bestScore = s;
                best = el;
            }
        }

        if (best && bestScore >= 5) {
            candidates[type] = best;
            assigned.add(best);
            console.log(`[JobBot] MATCH ${type} (score ${bestScore}): clues=[${getAllTextClues(best).slice(0,4).join(', ')}]`);
        }
    }

    const unmatched = visibleInputs.filter(el => !assigned.has(el));
    if (unmatched.length > 0) {
        console.log(`[JobBot] ${unmatched.length} unmatched inputs:`);
        unmatched.slice(0, 10).forEach(el => {
            console.log(`  - ${el.tagName} type=${el.type} name=${el.name} id=${el.id} clues=[${getAllTextClues(el).slice(0,3).join(', ')}]`);
        });
    }

    return { candidates, unmatched };
}
3. Expand Portfolio & GitHub Patterns
Add these to scoreField() patterns:
JavaScript
portfolio: {
    strong: [
        'portfolio', 'portfolio url', 'portfolio website', 
        'portfolio link', 'portfolioUrl', 'portfolio_url',
        'personal portfolio', 'your portfolio',
        'behance', 'dribbble', 'xing', 'profilexing',  // catches name="profilexing"
        'social profile', 'professional profile'
    ],
    weak: ['site', 'url', 'website', 'link', 'profile'],
    avoid: ['github', 'gitlab', 'company', 'business', 'employer', 'code', 'linkedin']
},
github: {
    strong: [
        'github', 'gitlab', 'github url', 'gitlab url', 
        'githubUrl', 'gitlabUrl', 'github_url', 'gitlab_url',
        'source code', 'code repository'
    ],
    weak: ['code', 'repo', 'repository', 'url', 'git'],
    avoid: ['portfolio', 'website', 'linkedin', 'personal', 'behance', 'xing']
},
website: {
    strong: ['website', 'personal site', 'url', 'web'],
    weak: ['link', 'site'],
    avoid: ['linkedin', 'portfolio', 'github', 'gitlab', 'company', 'business', 'behance', 'xing']
},
4. Add fillCustomQuestions for Weird/Custom Fields
Add this function to content.js:
JavaScript
async function fillCustomQuestions(profile, unmatchedInputs) {
    const questions = [];
    
    for (const el of unmatchedInputs) {
        // Only consider textareas and text inputs that look like answer fields
        if (el.tagName !== 'TEXTAREA' && el.type !== 'text' && el.type !== 'url') continue;
        
        const clues = getAllTextClues(el);
        const labelText = clues.join(' ');
        
        // Detect if this looks like a custom question
        const hasQuestionMark = labelText.includes('?');
        const hasInstructionWords = /\b(write|describe|tell us|explain|share|what|how|why|please|brief|detail|answer|list)\b/.test(labelText);
        const hasQuestionWords = /\b(introduction|about yourself|background|experience|salary|compensation|notice|availability|why|motivation|interest|challenge|strength|weakness|achievement|fit|qualification|project|skill)\b/.test(labelText);
        
        const isCustomQuestion = hasQuestionMark || (hasInstructionWords && hasQuestionWords);
        const isLargeField = el.tagName === 'TEXTAREA' || (el.maxLength && el.maxLength > 200) || (el.placeholder && el.placeholder.length > 30);
        
        if (isCustomQuestion && isLargeField) {
            let qType = 'general';
            const text = labelText;
            
            if (/\b(introduction|about yourself|background|bio|tell me about|who are you|describe yourself)\b/.test(text)) qType = 'introduction';
            else if (/\b(salary|compensation|pay|ctc|expected|desired.*monthly|desired.*yearly|monthly salary|yearly salary|pay range|remuneration)\b/.test(text)) qType = 'salary';
            else if (/\b(why.*company|why.*role|why.*apply|motivation|interest.*role|interest.*company|why do you want)\b/.test(text)) qType = 'motivation';
            else if (/\b(availability|notice|start.*date|when.*join|when.*start|how soon|available from)\b/.test(text)) qType = 'availability';
            else if (/\b(cover.*letter|additional.*info|anything else|supplement|message)\b/.test(text)) qType = 'cover';
            else if (/\b(experience.*relevant|relevant.*experience|why.*fit|why.*qualified|match.*role)\b/.test(text)) qType = 'fit';
            
            questions.push({ element: el, question: labelText, type: qType, rawLabel: clues[0] || labelText });
        }
    }
    
    if (questions.length === 0) return 0;
    
    let filled = 0;
    for (const q of questions) {
        let answer = '';
        let usedLLM = false;
        
        // Fast path: pre-computed answers (no LLM call)
        if (q.type === 'salary' && profile.expected_ctc) {
            answer = profile.expected_ctc;
            // If question asks for USD monthly, use pre-computed USD field if available
            if (/monthly.*usd|usd.*month|\$.*month|per.*month.*usd/.test(q.question) && profile.expected_salary_usd_monthly) {
                answer = profile.expected_salary_usd_monthly;
            }
        } else if (q.type === 'availability' && profile.notice_period_weeks !== undefined) {
            answer = (profile.notice_period_weeks === '0' || profile.notice_period_weeks === 0) 
                ? 'Immediate' 
                : `${profile.notice_period_weeks} weeks`;
        } else if (q.type === 'introduction' && profile.custom_answers?.introduction) {
            answer = profile.custom_answers.introduction;
        } else if (q.type === 'motivation' && profile.custom_answers?.motivation) {
            answer = profile.custom_answers.motivation;
        } else {
            // LLM fallback for complex/unrecognized questions
            usedLLM = true;
            try {
                const result = await apiRequest('POST', `${SERVER}/answer-question`, {
                    profile: profile,
                    question: q.rawLabel,
                    question_type: q.type
                });
                if (result && !result.error && result.answer) {
                    answer = result.answer;
                }
            } catch (e) {
                console.error('[JobBot] Custom question LLM failed:', e);
            }
        }
        
        if (answer && setInputValue(q.element, answer)) {
            filled++;
            console.log(`[JobBot] Filled custom question (${q.type}${usedLLM ? '-LLM' : ''}): ${q.rawLabel.substring(0, 60)}...`);
        }
    }
    
    return filled;
}
5. Update fillForm to Wire It All Together
Replace fillForm with this version that calls fillCustomQuestions at the end:
JavaScript
function fillForm(profile) {
    console.log('[JobBot] === Starting form fill ===');
    console.log('[JobBot] Profile:', JSON.stringify({
        name: profile.name,
        email: profile.email,
        phone: profile.phone,
        portfolio: profile.portfolio,
        github: profile.github,
        linkedin: profile.linkedin
    }));

    const { candidates: fields, unmatched } = findBestInputs();
    let filled = 0;
    const log = [];

    const nameParts = (profile.name || '').split(/\s+/).filter(p => p.length > 0);
    const firstName = profile.first_name || nameParts[0] || '';
    const lastName = profile.last_name || (nameParts.length > 1 ? nameParts.slice(1).join(' ') : '');

    if (fields.firstName && firstName) {
        if (setInputValue(fields.firstName, firstName)) { filled++; log.push('firstName'); }
    }
    if (fields.lastName && lastName) {
        if (setInputValue(fields.lastName, lastName)) { filled++; log.push('lastName'); }
    }
    if (!fields.firstName && !fields.lastName && fields.fullName && profile.name) {
        if (setInputValue(fields.fullName, profile.name)) { filled++; log.push('fullName'); }
    }

    if (fields.email && profile.email) {
        if (setInputValue(fields.email, profile.email)) { filled++; log.push('email'); }
    }

    if (fields.phone && profile.phone && !profile.phone.includes('@')) {
        if (setInputValue(fields.phone, profile.phone)) { filled++; log.push('phone'); }
    }

    if (fields.currentRole && profile.current_role) {
        if (setInputValue(fields.currentRole, profile.current_role)) { filled++; log.push('currentRole'); }
    }

    if (fields.yearsExperience && profile.years_experience) {
        if (setInputValue(fields.yearsExperience, profile.years_experience)) { filled++; log.push('yearsExperience'); }
    }

    if (fields.location && profile.location) {
        if (setInputValue(fields.location, profile.location)) { filled++; log.push('location'); }
    }

    if (fields.expectedCtc && profile.expected_ctc) {
        if (setInputValue(fields.expectedCtc, profile.expected_ctc)) { filled++; log.push('expectedCtc'); }
    }

    if (fields.noticePeriod && profile.notice_period_weeks !== undefined && profile.notice_period_weeks !== '') {
        if (setInputValue(fields.noticePeriod, profile.notice_period_weeks)) { filled++; log.push('noticePeriod'); }
    }

    if (fields.referralSource && profile.referral_source) {
        if (setInputValue(fields.referralSource, profile.referral_source)) { filled++; log.push('referralSource'); }
    }

    if (fields.linkedin && profile.linkedin) {
        if (setInputValue(fields.linkedin, profile.linkedin)) { filled++; log.push('linkedin'); }
    }

    if (fields.portfolio && profile.portfolio) {
        if (setInputValue(fields.portfolio, profile.portfolio)) { filled++; log.push('portfolio'); }
    }

    if (fields.github && profile.github) {
        if (setInputValue(fields.github, profile.github)) { filled++; log.push('github'); }
    }

    // Generic website fallback only if no specific fields matched
    if (fields.website && !fields.portfolio && !fields.github) {
        const webUrl = profile.portfolio || profile.website || profile.github || '';
        if (webUrl) {
            if (setInputValue(fields.website, webUrl)) { filled++; log.push('website'); }
        }
    }

    console.log(`[JobBot] === Filled ${filled} standard fields: ${log.join(', ')} ===`);

    // Now handle custom questions
    fillCustomQuestions(profile, unmatched).then(customFilled => {
        if (customFilled > 0) {
            console.log(`[JobBot] === Filled ${customFilled} custom questions ===`);
        }
    });

    return filled;
}
6. Add Server Endpoint for LLM Custom Answers
Add this to server.py:
Python
@app.post("/answer-question")
async def answer_question(payload: dict):
    profile = payload.get("profile", {})
    question = payload.get("question", "")
    q_type = payload.get("question_type", "general")
    
    raw = profile.get("raw_bio", "") or profile.get("raw", "")
    expected_ctc = profile.get("expected_ctc", "")
    notice = profile.get("notice_period_weeks", "")
    current_role = profile.get("current_role", "")
    years = profile.get("years_experience", "")
    name = profile.get("name", "the applicant")

    # Pre-computed fast answers (avoid LLM call)
    if q_type == "salary" and expected_ctc:
        return {"answer": expected_ctc}
    if q_type == "availability" and notice:
        return {"answer": "Immediate" if notice in ("0", 0, "0 weeks") else f"{notice} weeks"}

    prompt = f"""You are {name}, a practical engineer answering a job application question. 
Write like you talk to a colleague. No corporate buzzwords.

Question: {question}

Your background:
{raw[:1500]}

Current role: {current_role}
Years of experience: {years}
Expected CTC: {expected_ctc}
Notice period: {notice}

Rules:
- Answer naturally and directly. No fluff.
- Don't use: passionate, results-driven, innovative, dynamic, leveraging, holistic, synergy, proactive.
- Stick to facts from your background. Don't invent experience.
- If the question asks for a word count, respect it.
- If it's about salary, state your range clearly.
- If it's about availability, be direct.
- Write only the answer text. No preamble like "Here is my answer:"""

    try:
        async with httpx.AsyncClient(timeout=config.llm_timeout) as client:
            r = await client.post(
                config.llm_api,
                json={
                    "model": config.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.4, "top_p": 0.9}
                },
            )
            text = r.json().get("response", "").strip()
            # Strip any wrapping quotes or markdown
            text = re.sub(r'^["\']{1,2}|["\']{1,2}$', '', text)
            text = re.sub(r'^```\w*\n?|\n?```$', '', text)
            return {"answer": text}
    except Exception as e:
        return {"error": str(e)}
7. Update resume.json with Optional Fast-Path Fields
Add these optional fields for common custom questions so the extension can fill them without LLM latency:
JSON
{
  "name": "Aryan Sahu",
  "first_name": "Aryan",
  "last_name": "Sahu",
  "email": "aryanwin0609@gmail.com",
  "phone": "+91 7058602394",
  "location": "Pune, Maharashtra",
  "current_role": "Full Stack Developer",
  "years_experience": "3.5",
  "linkedin": "https://www.linkedin.com/in/aryan-sahu",
  "github": "https://github.com/aryan-sahu2",
  "portfolio": "https://dev-portfolio-4d2.pages.dev/",
  "notice_period_weeks": "0",
  "expected_ctc": "18-24 LPA INR",
  "expected_salary_usd_monthly": "$1,800 - $2,400",
  "referral_source": "LinkedIn",
  "custom_answers": {
    "introduction": "Aryan Sahu — Full Stack Developer with 3+ years shipping production systems. I've built platforms from scratch (React, Node, PostgreSQL, AWS), handled zero-downtime deployments, and migrated legacy stacks to Next.js. I work end-to-end and prefer shipping over meetings.",
    "motivation": "I'm looking for teams where I can own features end-to-end and work with modern stacks. Your role lines up with what I've been building lately."
  },
  "raw_bio": "Full Stack Developer with 3+ years of production experience..."
}
Summary of What This Fixes
Table
Field	Why It Failed	Fix
Behance / Portfolio (name="profilexing")	Label was sibling in wrapper div, not parent/previous sibling. name was profilexing — no pattern matched.	getAllTextClues now scans all labels inside the same container. Added profilexing, xing, behance to portfolio.strong.
Current Location (name="currentLocation")	camelCase name didn't match spaced patterns.	Added camelCase variants (currentLocation) to location.strong.
Expected CTC (name="salaryExpectation")	camelCase combined word wasn't in patterns.	Added salaryExpectation, expectedCompensation to expectedCtc.strong.
Custom intro question (name="10380")	Numeric name, no keyword match possible.	fillCustomQuestions detects it by label text ("write a brief introduction") and fills via fast-path custom_answers.introduction or LLM.
Custom salary question (name="10382")	Numeric name, label asks for USD monthly.	Detected as salary type. Uses expected_salary_usd_monthly if available, otherwise falls back to expected_ctc or LLM.
GitHub got portfolio URL	website pattern matched both fields; no separate github type existed.