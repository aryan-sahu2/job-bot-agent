1. Detect & Isolate Custom Questions Before Standard Matching
Add this at the top of content.js (before findBestInputs):
JavaScript
function isLikelyCustomQuestion(el) {
    if (el.tagName !== 'TEXTAREA' && (el.type !== 'text' || !el.maxLength || el.maxLength < 200)) {
        return false;
    }
    
    const clues = getAllTextClues(el);
    const text = clues.join(' ');
    const placeholder = (el.placeholder || '').toLowerCase();
    const name = el.name || '';
    const id = el.id || '';
    
    let score = 0;
    if (/^\d+$/.test(name)) score += 3;                          // Numeric name (10380, 10382)
    if (/candidateAnswer|customQuestion|question/i.test(id)) score += 3;
    if (/write your answer|enter your answer|type here|your response/i.test(placeholder)) score += 2;
    if (text.includes('?')) score += 2;
    if (/\b(write|describe|tell us|explain|share|brief|detail|answer|introduction|about yourself|background|why|how|what|motivation|challenge|strength|weakness|achievement|note:|please)\b/i.test(text)) score += 2;
    if (el.tagName === 'TEXTAREA') score += 1;
    if (el.maxLength > 500) score += 1;
    
    // If it has a generic placeholder like "Write your answer" inside a space-y-2 wrapper,
    // it's almost certainly a custom question
    const wrapper = el.closest('.space-y-2, [class*="form-item"], [class*="field-wrapper"]');
    if (wrapper && wrapper.querySelector('label')?.innerText.length > 50) score += 1;
    
    return score >= 3;
}
Replace findBestInputs with this version that separates custom questions upfront:
JavaScript
function findBestInputs() {
    const allInputs = Array.from(document.querySelectorAll('input, textarea, select'));

    const visibleInputs = allInputs.filter(el => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== 'none' && 
               style.visibility !== 'hidden' && 
               rect.width > 5 && rect.height > 5 &&
               !el.disabled && !el.readOnly;
    });

    // CRITICAL: Separate custom questions before standard matching
    const standardInputs = [];
    const customQuestions = [];
    
    for (const el of visibleInputs) {
        if (isLikelyCustomQuestion(el)) {
            customQuestions.push(el);
        } else {
            standardInputs.push(el);
        }
    }
    
    console.log(`[JobBot] ${visibleInputs.length} total | ${customQuestions.length} custom questions | ${standardInputs.length} standard`);

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
        let best = null, bestScore = 0;
        for (const el of standardInputs) {
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
            console.log(`[JobBot] MATCH ${type} (score ${bestScore})`);
        }
    }

    const unmatched = standardInputs.filter(el => !assigned.has(el));
    return { candidates, unmatched, customQuestions };
}
Update fillForm to receive and pass customQuestions:
JavaScript
function fillForm(profile) {
    console.log('[JobBot] === Starting form fill ===');
    const { candidates: fields, unmatched, customQuestions } = findBestInputs();
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
    if (fields.website && !fields.portfolio && !fields.github) {
        const webUrl = profile.portfolio || profile.website || profile.github || '';
        if (webUrl && setInputValue(fields.website, webUrl)) { filled++; log.push('website'); }
    }

    console.log(`[JobBot] === Filled ${filled} standard fields: ${log.join(', ')} ===`);

    // Now handle custom questions with proper answers
    if (customQuestions.length > 0) {
        fillCustomQuestions(profile, customQuestions).then(cf => {
            console.log(`[JobBot] === Filled ${cf} custom questions ===`);
        });
    }

    return filled;
}
2. Smarter fillCustomQuestions with Format Awareness
Replace fillCustomQuestions with this version that generates proper paragraph answers and handles currency:
JavaScript
async function fillCustomQuestions(profile, customQuestions) {
    let filled = 0;
    
    for (const el of customQuestions) {
        const clues = getAllTextClues(el);
        const labelText = clues.join(' ');
        const lowerLabel = labelText.toLowerCase();
        
        let answer = '';
        let source = 'unknown';
        
        // 1. INTRODUCTION / ABOUT YOURSELF
        if (/\b(introduction|about yourself|background|bio|tell me about|who are you|describe yourself)\b/i.test(lowerLabel)) {
            if (profile.custom_answers?.introduction) {
                answer = profile.custom_answers.introduction;
                source = 'pre-canned';
            } else {
                answer = generateIntroduction(profile);
                source = 'generated';
            }
        }
        // 2. SALARY (USD MONTHLY)
        else if (/\b(monthly salary|salary range.*usd|usd.*month|desired monthly|per month|monthly.*range)\b/i.test(lowerLabel)) {
            if (profile.expected_salary_usd_monthly) {
                answer = profile.expected_salary_usd_monthly;
                source = 'pre-canned-usd-monthly';
            } else if (profile.expected_ctc) {
                // Rough conversion: 18 LPA INR ≈ $1800/month, 24 LPA ≈ $2400/month
                answer = `I'm looking for a range of $1,800 - $2,400 per month, which aligns with my current experience level and the scope of this role.`;
                source = 'converted-estimate';
            }
        }
        // 3. SALARY (USD YEARLY or generic)
        else if (/\b(salary|compensation|ctc|pay range|desired salary|expected.*salary)\b/i.test(lowerLabel)) {
            if (profile.expected_salary_usd_yearly) {
                answer = profile.expected_salary_usd_yearly;
                source = 'pre-canned-usd-yearly';
            } else if (profile.expected_ctc) {
                answer = profile.expected_ctc;
                source = 'pre-canned-inr';
            }
        }
        // 4. AVAILABILITY / NOTICE
        else if (/\b(availability|notice period|start date|joining|how soon|available from)\b/i.test(lowerLabel)) {
            const notice = profile.notice_period_weeks;
            if (notice === '0' || notice === 0 || notice === 'Immediate') {
                answer = "I can start immediately.";
            } else {
                answer = `I have a ${notice}-week notice period with my current employer, so I can join after that.`;
            }
            source = 'computed';
        }
        // 5. WHY THIS COMPANY / MOTIVATION
        else if (/\b(why.*company|why.*role|why.*apply|motivation|interest.*role|interest.*company|why do you want)\b/i.test(lowerLabel)) {
            if (profile.custom_answers?.motivation) {
                answer = profile.custom_answers.motivation;
                source = 'pre-canned';
            } else {
                answer = "I'm looking for a team where I can own features end-to-end and work with modern stacks. This role seems to line up with what I've been building lately.";
                source = 'generic';
            }
        }
        // 6. COVER LETTER / ADDITIONAL INFO
        else if (/\b(cover letter|additional info|anything else|supplement|message|additional information)\b/i.test(lowerLabel)) {
            if (profile.custom_answers?.cover_letter) {
                answer = profile.custom_answers.cover_letter;
                source = 'pre-canned';
            } else {
                // Skip - user should generate via panel
                continue;
            }
        }
        // 7. GENERIC FALLBACK - LLM
        else {
            try {
                const result = await apiRequest('POST', `${SERVER}/answer-question`, {
                    profile: profile,
                    question: clues[0] || labelText,
                    question_type: 'general'
                });
                if (result && !result.error && result.answer) {
                    answer = result.answer;
                    source = 'llm';
                }
            } catch (e) {
                console.error('[JobBot] LLM fallback failed:', e);
                continue;
            }
        }
        
        // Respect word count hints
        const wordMatch = labelText.match(/(\d+)\s*-\s*(\d+)\s*words?/i);
        if (wordMatch && answer.split(/\s+/).length < parseInt(wordMatch[1])) {
            // If pre-canned is too short, expand with LLM
            if (source === 'pre-canned' || source === 'generated') {
                try {
                    const result = await apiRequest('POST', `${SERVER}/expand-answer`, {
                        answer: answer,
                        target_words: parseInt(wordMatch[2]),
                        question: labelText
                    });
                    if (result?.answer) answer = result.answer;
                } catch (e) {}
            }
        }
        
        if (answer && setInputValue(el, answer)) {
            filled++;
            console.log(`[JobBot] Custom question (${source}): ${labelText.substring(0, 50)}...`);
        }
    }
    
    return filled;
}

function generateIntroduction(profile) {
    const raw = profile.raw_bio || '';
    const role = profile.current_role || 'Developer';
    const years = profile.years_experience || '';
    const skills = profile.skills || '';
    
    // Extract first paragraph of raw bio if it's good
    const firstPara = raw.split('\n\n')[0];
    if (firstPara && firstPara.length > 100 && firstPara.length < 800) {
        return firstPara;
    }
    
    return `${profile.name} — ${role} with ${years}+ years shipping production systems. I've built platforms from scratch, handled zero-downtime deployments, and migrated legacy stacks. I work end-to-end and prefer shipping over meetings.`;
}
Add to server.py (new endpoint for expanding short answers):
Python
@app.post("/expand-answer")
async def expand_answer(payload: dict):
    answer = payload.get("answer", "")
    target = payload.get("target_words", 150)
    question = payload.get("question", "")
    
    prompt = f"""Expand the following answer to roughly {target} words. Keep the same tone and facts. Do not add fluff or buzzwords.

Question: {question}
Current answer ({len(answer.split())} words): {answer}

Write only the expanded answer. No preamble."""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                config.llm_api,
                json={
                    "model": config.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.4}
                },
            )
            text = r.json().get("response", "").strip()
            return {"answer": text}
    except Exception as e:
        return {"error": str(e)}
3. Update resume.json with USD Conversions & Pre-Canned Answers
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
  "expected_salary_usd_monthly": "$1,800 - $2,400 per month",
  "expected_salary_usd_yearly": "$22,000 - $29,000 per year",
  "referral_source": "LinkedIn",
  "skills": "React, Next.js, TypeScript, Node.js, PostgreSQL, AWS, Python",
  "custom_answers": {
    "introduction": "I'm Aryan Sahu, a Full Stack Developer with 3.5 years of production experience building and shipping web applications at scale. I've delivered features for enterprise clients supporting 10M+ daily transactions, and I'm currently architecting Next.js systems for a Dubai-based startup. I handle everything from React frontends and Node APIs to PostgreSQL schema design and AWS/Nginx deployments. I like owning the full stack and prefer shipping working code over writing lengthy specs.",
    "motivation": "I'm looking for teams where I can own features end-to-end and work with modern stacks. Your role lines up with what I've been building lately — particularly the Next.js and Node.js infrastructure work.",
    "cover_letter": ""
  },
  "raw_bio": "Full Stack Developer with 3+ years of production experience..."
}
4. Modern UI Panel
Replace createPanel with this glassmorphism design:
JavaScript
function createPanel() {
    if (panel) return panel;
    
    const div = document.createElement('div');
    div.id = 'jobbot-panel';
    div.innerHTML = `
        <div id="jb-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid rgba(148,163,184,0.15);cursor:move;user-select:none;">
            <div style="display:flex;align-items:center;gap:10px;">
                <div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:15px;box-shadow:0 2px 8px rgba(99,102,241,0.3);">⚡</div>
                <div>
                    <div style="font-size:15px;font-weight:600;color:#f8fafc;letter-spacing:-0.01em;">JobBot</div>
                    <div style="font-size:11px;color:#64748b;margin-top:1px;">Auto-fill assistant</div>
                </div>
            </div>
            <button id="jb-close" style="background:rgba(255,255,255,0.05);border:none;color:#94a3b8;cursor:pointer;font-size:18px;width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;transition:all 0.15s;">×</button>
        </div>
        
        <div id="jb-status" style="display:flex;align-items:center;gap:8px;font-size:12px;color:#94a3b8;margin-bottom:14px;padding:8px 10px;background:rgba(15,23,42,0.6);border-radius:8px;border:1px solid rgba(255,255,255,0.05);">
            <span id="jb-status-dot" style="width:7px;height:7px;border-radius:50%;background:#ef4444;transition:background 0.3s;"></span>
            <span id="jb-status-text">Server: checking...</span>
        </div>
        
        <div style="display:flex;flex-direction:column;gap:8px;">
            <button id="jb-fill" style="display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:10px;background:linear-gradient(135deg,#3b82f6,#6366f1);color:white;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500;transition:all 0.15s;box-shadow:0 2px 8px rgba(59,130,246,0.25);letter-spacing:-0.01em;">
                <span style="font-size:14px;">🚀</span> Fill Profile
            </button>
            
            <button id="jb-cover" style="display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:10px;background:rgba(255,255,255,0.04);color:#e2e8f0;border:1px solid rgba(255,255,255,0.08);border-radius:8px;cursor:pointer;font-size:13px;font-weight:500;transition:all 0.15s;letter-spacing:-0.01em;">
                <span style="font-size:14px;">✍️</span> Generate Cover Letter
            </button>
        </div>
        
        <div id="jb-cover-box" style="display:none;margin-top:14px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;">Cover Letter</div>
                <div id="jb-cover-meta" style="font-size:10px;color:#475569;"></div>
            </div>
            <textarea id="jb-cover-text" style="width:100%;height:150px;background:rgba(15,23,42,0.5);color:#e2e8f0;border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:10px;font-size:12px;line-height:1.6;resize:vertical;font-family:system-ui,sans-serif;outline:none;" placeholder="Click 'Generate' to create a cover letter..."></textarea>
            <div style="display:flex;gap:8px;margin-top:10px;">
                <button id="jb-paste" style="flex:1;padding:8px;background:#6366f1;color:white;border:none;border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;transition:all 0.15s;display:flex;align-items:center;justify-content:center;gap:6px;">
                    <span>📋</span> Paste into Form
                </button>
                <button id="jb-copy" style="padding:8px 12px;background:rgba(255,255,255,0.05);color:#94a3b8;border:1px solid rgba(255,255,255,0.08);border-radius:6px;cursor:pointer;font-size:12px;transition:all 0.15s;" title="Copy to clipboard">📋</button>
            </div>
        </div>
        
        <div id="jb-log" style="margin-top:14px;padding-top:12px;border-top:1px solid rgba(148,163,184,0.12);font-size:11px;color:#47548b;max-height:120px;overflow-y:auto;font-family:'SF Mono',monospace;line-height:1.5;"></div>
    `;
    
    div.style.cssText = `
        position:fixed;bottom:24px;right:24px;width:320px;
        background:rgba(15,23,42,0.88);color:#e2e8f0;
        border:1px solid rgba(255,255,255,0.06);
        border-radius:16px;padding:18px;
        font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        font-size:13px;z-index:999999;
        box-shadow:0 25px 50px -12px rgba(0,0,0,0.5),0 0 0 1px rgba(255,255,255,0.04);
        backdrop-filter:blur(16px) saturate(1.2);
        line-height:1.4;
        transition:opacity 0.2s,transform 0.2s;
    `;
    
    document.body.appendChild(div);
    panel = div;

    // Hover effects via JS (avoid inline CSS complexity)
    const closeBtn = document.getElementById('jb-close');
    closeBtn.onmouseenter = () => { closeBtn.style.background = 'rgba(255,255,255,0.1)'; closeBtn.style.color = '#f8fafc'; };
    closeBtn.onmouseleave = () => { closeBtn.style.background = 'rgba(255,255,255,0.05)'; closeBtn.style.color = '#94a3b8'; };
    closeBtn.onclick = () => { div.style.display = 'none'; };

    const fillBtn = document.getElementById('jb-fill');
    fillBtn.onmouseenter = () => { fillBtn.style.transform = 'translateY(-1px)'; fillBtn.style.boxShadow = '0 4px 12px rgba(59,130,246,0.35)'; };
    fillBtn.onmouseleave = () => { fillBtn.style.transform = 'translateY(0)'; fillBtn.style.boxShadow = '0 2px 8px rgba(59,130,246,0.25)'; };
    
    const coverBtn = document.getElementById('jb-cover');
    coverBtn.onmouseenter = () => { coverBtn.style.background = 'rgba(255,255,255,0.08)'; };
    coverBtn.onmouseleave = () => { coverBtn.style.background = 'rgba(255,255,255,0.04)'; };

    fillBtn.onclick = async () => {
        fillBtn.textContent = 'Filling...';
        const profile = await fetchProfile();
        if (!profile) {
            alert('JobBot: Cannot reach local server. Run: uv run python src/server.py');
            fillBtn.innerHTML = '<span style="font-size:14px;">🚀</span> Fill Profile';
            return;
        }
        const filled = fillForm(profile);
        fillBtn.innerHTML = `<span style="font-size:14px;">✅</span> Filled ${filled} fields`;
        setTimeout(() => fillBtn.innerHTML = '<span style="font-size:14px;">🚀</span> Fill Profile', 2500);
    };

    coverBtn.onclick = async () => {
        coverBtn.innerHTML = '<span style="font-size:14px;">⏳</span> Generating...';
        const h1 = document.querySelector('h1, h2');
        const title = h1 ? h1.innerText.trim() : document.title;
        const company = document.querySelector('[class*="company"], [class*="employer"]')?.innerText.trim() || '';
        const result = await generateLetter(title, company);
        
        if (!result || result.error || !result.cover_letter) {
            alert('JobBot: Cover letter generation failed. Is Ollama running?');
            coverBtn.innerHTML = '<span style="font-size:14px;">✍️</span> Generate Cover Letter';
            return;
        }
        
        document.getElementById('jb-cover-text').value = result.cover_letter;
        document.getElementById('jb-cover-box').style.display = 'block';
        document.getElementById('jb-cover-meta').textContent = `${result.cover_letter.split(/\s+/).length} words`;
        coverBtn.innerHTML = '<span style="font-size:14px;">🔄</span> Regenerate';
    };

    document.getElementById('jb-paste').onclick = () => {
        const text = document.getElementById('jb-cover-text').value;
        const ok = pasteCoverLetter(text);
        const btn = document.getElementById('jb-paste');
        btn.innerHTML = ok ? '<span>✅</span> Pasted!' : '<span>❌</span> No field found';
        setTimeout(() => btn.innerHTML = '<span>📋</span> Paste into Form', 2000);
    };

    document.getElementById('jb-copy').onclick = () => {
        const text = document.getElementById('jb-cover-text').value;
        navigator.clipboard.writeText(text).then(() => {
            const btn = document.getElementById('jb-copy');
            btn.textContent = '✅';
            setTimeout(() => btn.textContent = '📋', 1500);
        });
    };

    apiRequest('GET', `${SERVER}/`).then(() => {
        document.getElementById('jb-status-dot').style.background = '#10b981';
        document.getElementById('jb-status-text').textContent = 'Server: connected';
    }).catch(() => {
        document.getElementById('jb-status-dot').style.background = '#ef4444';
        document.getElementById('jb-status-text').textContent = 'Server: offline';
    });

    console.log('[JobBot] Panel created');
    return div;
}
Summary of What This Fixes
Table
Issue	Root Cause	Fix
Introduction got "3.5"	yearsExperience pattern matched the label "your experience" and stole the textarea before custom logic ran	isLikelyCustomQuestion now detects textareas with numeric names, generic IDs, and question-like labels, and removes them from standard matching before findBestInputs runs
Salary got "18-24 LPA INR"	expectedCtc pattern matched "salary" in the label and filled raw profile value	Same isolation as above. Plus new logic detects "USD monthly" and serves $1,800-$2,400 instead
Answers too short	Pre-canned intro was missing from resume.json	Added custom_answers.introduction with a proper 50-word paragraph. Added /expand-answer endpoint for LLM expansion if word count hints are present
UI looked basic	Basic dark box with no polish	Glassmorphism backdrop, gradients, hover states, copy button, word count meta, better spacing
The key architectural change: custom questions are detected and quarantined before any standard field scoring happens. This guarantees they never get polluted by raw profile values.