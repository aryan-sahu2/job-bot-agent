(function() {
    'use strict';
    if (window.__jobbotLoaded) return;
    window.__jobbotLoaded = true;

    const SERVER = 'http://127.0.0.1:8765';
    let panel = null;
    let profileCache = null;

    const PLATFORMS = {
        greenhouse: {
            test: () => /greenhouse\.io/.test(location.hostname),
            selectors: {
                firstName: 'input[name="job_application[first_name]"], input#first_name',
                lastName: 'input[name="job_application[last_name]"], input#last_name',
                fullName: 'input[name="job_application[full_name]"]',
                email: 'input[name="job_application[email]"], input[type="email"]',
                phone: 'input[name="job_application[phone]"]',
                coverLetter: 'textarea[name="job_application[cover_letter]"], textarea#cover_letter, textarea[name="job_application[cover_letter_body]"]'
            }
        },
        lever: {
            test: () => /lever\.co/.test(location.hostname),
            selectors: {
                fullName: 'input[name="name"]',
                email: 'input[name="email"]',
                phone: 'input[name="phone"]',
                coverLetter: 'textarea[name="comments"], textarea[data-qa="cover-letter"], textarea[name="coverLetter"]'
            }
        },
        workable: {
            test: () => /workable\.com/.test(location.hostname) || /apply\.workable\.com/.test(location.hostname),
            selectors: {
                firstName: 'input[name="candidate[first_name]"]',
                lastName: 'input[name="candidate[last_name]"]',
                fullName: 'input[name="candidate[name]"]',
                email: 'input[name="candidate[email]"]',
                phone: 'input[name="candidate[phone]"]',
                coverLetter: 'textarea[name="candidate[cover_letter]"]'
            }
        },
        linkedin: {
            test: () => /linkedin\.com/.test(location.hostname),
            selectors: {
                fullName: 'input[name="firstName"], input[id*="name"]',
                email: 'input[name="email"]',
                phone: 'input[name="phoneNumber"]',
                coverLetter: 'textarea[aria-describedby*="cover-letter"], textarea[name="coverLetter"]'
            }
        },
        indeed: {
            test: () => /indeed\.com/.test(location.hostname),
            selectors: {
                fullName: 'input[name="name"], input[placeholder*="Full name" i]',
                email: 'input[name="email"], input[type="email"]',
                phone: 'input[name="phone"], input[type="tel"]',
                coverLetter: 'textarea[name="coverletter"], textarea[placeholder*="cover letter" i]'
            }
        },
        breezy: {
            test: () => /breezy\.hr/.test(location.hostname),
            selectors: {
                fullName: 'input[name="name"]',
                email: 'input[name="email"]',
                phone: 'input[name="phone"]',
                coverLetter: 'textarea[name="cover_letter"]'
            }
        },
        recruitee: {
            test: () => /recruitee\.com/.test(location.hostname),
            selectors: {
                fullName: 'input[name="candidate[name]"]',
                email: 'input[name="candidate[email]"]',
                phone: 'input[name="candidate[phone]"]',
                coverLetter: 'textarea[name="candidate[cover_letter]"]'
            }
        },
        smartrecruiters: {
            test: () => /smartrecruiters\.com/.test(location.hostname),
            selectors: {
                firstName: 'input[name="firstName"]',
                lastName: 'input[name="lastName"]',
                email: 'input[name="email"]',
                phone: 'input[name="phone"]',
                coverLetter: 'textarea[name="coverLetter"]'
            }
        },
        ashby: {
            test: () => /ashby\.hq/.test(location.hostname),
            selectors: {
                fullName: 'input[name="name"]',
                email: 'input[name="email"]',
                phone: 'input[name="phone"]',
                coverLetter: 'textarea[name="coverLetter"]'
            }
        },
        workday: {
            test: () => /myworkdayjobs\.com/.test(location.hostname) || /workday\.com/.test(location.hostname),
            selectors: {
                fullName: 'input[data-automation-id="fullName"], input[aria-label*="Name" i]',
                email: 'input[data-automation-id="email"], input[type="email"]',
                phone: 'input[data-automation-id="phone"], input[type="tel"]',
                coverLetter: 'textarea[data-automation-id="coverLetter"], textarea[aria-label*="cover letter" i]'
            }
        }
    };

    function detectPlatform() {
        for (const [name, cfg] of Object.entries(PLATFORMS)) {
            if (cfg.test()) return { name, selectors: cfg.selectors };
        }
        return { name: 'generic', selectors: {} };
    }

    function fillField(selector, value) {
        if (!selector || !value) return false;
        const el = document.querySelector(selector);
        if (!el) return false;
        el.focus();
        el.value = value;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.blur();
        return true;
    }

    function getDescription() {
        const selectors = [
            '[class*="job-description"]', '[class*="jobDescription"]',
            '[id*="job-description"]', '[id*="jobDescription"]',
            '.show-more-less-html__markup', '.description__text',
            '[data-testid="job-description"]', '.posting-description',
            '.section.page-centered', 'article', 'main'
        ];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.innerText.length > 100) return el.innerText.slice(0, 3000);
        }
        const ps = Array.from(document.querySelectorAll('p, li'));
        if (ps.length) return ps.map(p => p.innerText).join('\n').slice(0, 3000);
        return document.body.innerText.slice(0, 3000);
    }

    async function fetchProfile() {
        if (profileCache) return profileCache;
        try {
            const r = await fetch(`${SERVER}/profile`);
            if (!r.ok) throw new Error('bad response');
            profileCache = await r.json();
            return profileCache;
        } catch (e) {
            return null;
        }
    }

    async function generateLetter(title, company) {
        const profile = await fetchProfile();
        if (!profile) return null;
        try {
            const r = await fetch(`${SERVER}/cover-letter`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    profile,
                    job_title: title || document.title,
                    company: company || '',
                    description: getDescription()
                })
            });
            const data = await r.json();
            return data.cover_letter || null;
        } catch (e) {
            return null;
        }
    }

    function fillForm(profile) {
        const p = detectPlatform();
        const s = p.selectors;
        let n = 0;

        if (s.firstName && s.lastName) {
            const parts = (profile.name || '').split(' ');
            if (fillField(s.firstName, parts[0])) n++;
            if (fillField(s.lastName, parts.slice(1).join(' '))) n++;
        } else if (s.fullName) {
            if (fillField(s.fullName, profile.name)) n++;
        }

        if (fillField(s.email, profile.email)) n++;
        if (fillField(s.phone, profile.phone)) n++;

        if (!n) {
            // Generic fallback heuristics
            document.querySelectorAll('input').forEach(inp => {
                const nm = (inp.name || '').toLowerCase();
                const ph = (inp.placeholder || '').toLowerCase();
                const id = (inp.id || '').toLowerCase();
                if ((inp.type === 'email' || nm.includes('email') || ph.includes('email') || id.includes('email')) && profile.email) {
                    inp.value = profile.email; inp.dispatchEvent(new Event('input', {bubbles:true})); n++;
                }
                if ((nm.includes('phone') || nm.includes('tel') || ph.includes('phone') || id.includes('phone')) && profile.phone) {
                    inp.value = profile.phone; inp.dispatchEvent(new Event('input', {bubbles:true})); n++;
                }
            });
        }
        return n;
    }

    function createPanel() {
        if (panel) return panel;
        const div = document.createElement('div');
        div.id = 'jobbot-panel';
        div.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <strong style="font-size:16px;">JobBot</strong>
                <button id="jb-close" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:18px;">×</button>
            </div>
            <div id="jb-status" style="font-size:12px;color:#94a3b8;margin-bottom:10px;">Server: checking...</div>
            <button id="jb-fill" style="width:100%;padding:8px;margin-bottom:8px;background:#3b82f6;color:white;border:none;border-radius:4px;cursor:pointer;">Fill Profile</button>
            <button id="jb-cover" style="width:100%;padding:8px;margin-bottom:8px;background:#10b981;color:white;border:none;border-radius:4px;cursor:pointer;">Generate Cover Letter</button>
            <div id="jb-cover-box" style="display:none;margin-top:8px;">
                <textarea id="jb-cover-text" style="width:100%;height:120px;background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:4px;padding:6px;font-size:13px;" placeholder="Cover letter..."></textarea>
                <button id="jb-paste" style="width:100%;padding:6px;margin-top:4px;background:#6366f1;color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;">Paste into Form</button>
            </div>
        `;
        div.style.cssText = `
            position:fixed;bottom:20px;right:20px;width:280px;
            background:#0f172a;color:#e2e8f0;border:1px solid #334155;
            border-radius:8px;padding:16px;font-family:system-ui,sans-serif;
            font-size:14px;z-index:999999;box-shadow:0 10px 25px rgba(0,0,0,0.5);line-height:1.4;
        `;
        document.body.appendChild(div);
        panel = div;

        document.getElementById('jb-close').onclick = () => div.style.display = 'none';

        document.getElementById('jb-fill').onclick = async () => {
            const btn = document.getElementById('jb-fill');
            btn.textContent = 'Filling...';
            const profile = await fetchProfile();
            if (!profile) {
                alert('JobBot: Cannot reach local server. Run: uv run python src/server.py');
                btn.textContent = 'Fill Profile';
                return;
            }
            const filled = fillForm(profile);
            btn.textContent = `Filled ${filled} field${filled!==1?'s':''}`;
            setTimeout(() => btn.textContent = 'Fill Profile', 2000);
        };

        document.getElementById('jb-cover').onclick = async () => {
            const btn = document.getElementById('jb-cover');
            btn.textContent = 'Generating...';
            const h1 = document.querySelector('h1, h2');
            const title = h1 ? h1.innerText.trim() : document.title;
            const company = document.querySelector('[class*="company"], [class*="employer"]')?.innerText.trim() || '';
            const letter = await generateLetter(title, company);
            if (!letter) {
                alert('JobBot: Cover letter failed. Is Ollama running?');
                btn.textContent = 'Generate Cover Letter';
                return;
            }
            document.getElementById('jb-cover-text').value = letter;
            document.getElementById('jb-cover-box').style.display = 'block';
            btn.textContent = 'Regenerate';
        };

        document.getElementById('jb-paste').onclick = () => {
            const text = document.getElementById('jb-cover-text').value;
            const p = detectPlatform();
            let ok = false;
            if (p.selectors.coverLetter) ok = fillField(p.selectors.coverLetter, text);
            if (!ok) {
                const ta = document.querySelector('textarea[placeholder*="cover" i], textarea[name*="cover" i], textarea[id*="cover" i], textarea');
                if (ta) { ta.value = text; ta.dispatchEvent(new Event('input', {bubbles:true})); ok = true; }
            }
            const btn = document.getElementById('jb-paste');
            btn.textContent = ok ? 'Pasted!' : 'No cover letter field found';
            setTimeout(() => btn.textContent = 'Paste into Form', 2000);
        };

        fetch(`${SERVER}/`).then(r => r.json()).then(() => {
            const st = document.getElementById('jb-status');
            st.textContent = 'Server: connected'; st.style.color = '#10b981';
        }).catch(() => {
            const st = document.getElementById('jb-status');
            st.textContent = 'Server: offline'; st.style.color = '#ef4444';
        });

        return div;
    }

    function toggle() {
        if (!panel) createPanel();
        else panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }

    document.addEventListener('keydown', e => {
        // Cmd+Shift+K on Mac, Ctrl+Shift+K on Windows/Linux
        if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            toggle();
        }
    });

    if (/apply|careers|jobs|posting|application/.test(location.pathname + location.search)) {
        setTimeout(createPanel, 1500);
    }

    console.log('JobBot loaded. Press Cmd/Ctrl+Shift+K to toggle panel.');
})();