// ==UserScript==
// @name         JobBot Assistant
// @namespace    jobbot
// @version      2.0
// @description  Auto-fill job applications using your local JobBot profile
// @author       You
// @match        *://*.greenhouse.io/*
// @match        *://boards.greenhouse.io/*
// @match        *://*.lever.co/*
// @match        *://jobs.lever.co/*
// @match        *://*.workday.com/*
// @match        *://*.myworkdayjobs.com/*
// @match        *://*.linkedin.com/*
// @match        *://*.indeed.com/*
// @match        *://*.breezy.hr/*
// @match        *://*.recruitee.com/*
// @match        *://*.workable.com/*
// @match        *://*.smartrecruiters.com/*
// @match        *://*.ashbyhq.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const SERVER = 'http://127.0.0.1:8765';
    let profileCache = null;

    /* ── Platform detection ── */
    function detectPlatform() {
        const h = location.hostname;
        if (h.includes('greenhouse.io')) return 'greenhouse';
        if (h.includes('lever.co')) return 'lever';
        if (h.includes('workday.com') || h.includes('myworkdayjobs.com')) return 'workday';
        if (h.includes('linkedin.com')) return 'linkedin';
        if (h.includes('indeed.com')) return 'indeed';
        if (h.includes('breezy.hr')) return 'breezy';
        if (h.includes('recruitee.com')) return 'recruitee';
        if (h.includes('workable.com')) return 'workable';
        if (h.includes('smartrecruiters.com')) return 'smartrecruiters';
        if (h.includes('ashbyhq.com')) return 'ashby';
        return 'generic';
    }
    const PLATFORM = detectPlatform();

    /* ── Platform-specific selectors ── */
    const SELECTORS = {
        greenhouse: {
            firstName: ['#first_name'],
            lastName: ['#last_name'],
            fullName: [],
            email: ['#email'],
            phone: ['#phone'],
            coverLetter: ['#cover_letter'],
            resume: ['#resume']
        },
        lever: {
            firstName: [],
            lastName: [],
            fullName: ['input[name="name"]'],
            email: ['input[name="email"]'],
            phone: ['input[name="phone"]'],
            coverLetter: ['textarea[name="comments"]'],
            resume: ['input[name="resume"]']
        },
        workday: {
            firstName: ['input[data-automation-id="legalNameSection_firstName"]', 'input[autocomplete="given-name"]'],
            lastName: ['input[data-automation-id="legalNameSection_lastName"]', 'input[autocomplete="family-name"]'],
            fullName: [],
            email: ['input[data-automation-id="email"]', 'input[type="email"]'],
            phone: ['input[data-automation-id="phone-number"]'],
            coverLetter: ['textarea[data-automation-id="coverLetter"]'],
            resume: ['input[data-automation-id="resume"]']
        },
        linkedin: {
            firstName: ['#single-line-text-form-component-formElement-urn-li-jobs-applyformcommon-easyApplyFormElement-0-firstName'],
            lastName: ['#single-line-text-form-component-formElement-urn-li-jobs-applyformcommon-easyApplyFormElement-0-lastName'],
            fullName: [],
            email: ['#single-line-text-form-component-formElement-urn-li-jobs-applyformcommon-easyApplyFormElement-0-email'],
            phone: ['#single-line-text-form-component-formElement-urn-li-jobs-applyformcommon-easyApplyFormElement-0-phoneNumber'],
            coverLetter: [],
            resume: []
        },
        indeed: {
            firstName: ['#input-firstName'],
            lastName: ['#input-lastName'],
            fullName: [],
            email: ['#input-email'],
            phone: ['#input-phoneNumber'],
            coverLetter: [],
            resume: []
        },
        breezy: {
            firstName: ['#candidate_first_name'],
            lastName: ['#candidate_last_name'],
            fullName: [],
            email: ['#candidate_email'],
            phone: ['#candidate_phone'],
            coverLetter: ['#candidate_cover_letter'],
            resume: ['#candidate_resume']
        },
        recruitee: {
            firstName: ['#candidate_first_name'],
            lastName: ['#candidate_last_name'],
            fullName: [],
            email: ['#candidate_email'],
            phone: ['#candidate_phone'],
            coverLetter: ['#candidate_cover_letter'],
            resume: ['#candidate_cv']
        },
        workable: {
            firstName: ['#candidate_first_name'],
            lastName: ['#candidate_last_name'],
            fullName: [],
            email: ['#candidate_email'],
            phone: ['#candidate_phone'],
            coverLetter: ['#candidate_cover_letter'],
            resume: ['#candidate_resume']
        },
        smartrecruiters: {
            firstName: ['input[name="firstName"]'],
            lastName: ['input[name="lastName"]'],
            fullName: [],
            email: ['input[name="email"]'],
            phone: ['input[name="phone"]'],
            coverLetter: ['textarea[name="coverLetter"]'],
            resume: ['input[name="resume"]']
        },
        ashby: {
            firstName: ['input[name="firstName"]'],
            lastName: ['input[name="lastName"]'],
            fullName: [],
            email: ['input[name="email"]'],
            phone: ['input[name="phone"]'],
            coverLetter: ['textarea[name="coverLetter"]'],
            resume: ['input[name="resume"]']
        },
        generic: {
            firstName: [],
            lastName: [],
            fullName: [],
            email: [],
            phone: [],
            coverLetter: [],
            resume: []
        }
    };

    /* ── UI Panel ── */
    const panel = document.createElement('div');
    panel.id = 'jobbot-panel';
    panel.innerHTML = `
      <div style="position:fixed;bottom:20px;right:20px;z-index:99999;background:#0f172a;color:#e2e8f0;padding:16px;border-radius:12px;font-family:system-ui,-apple-system,sans-serif;box-shadow:0 10px 40px rgba(0,0,0,0.5);width:320px;border:1px solid #334155;max-height:90vh;overflow-y:auto;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
          <strong style="font-size:14px;">🤖 JobBot</strong>
          <div>
            <span id="jb-badge" style="font-size:10px;background:#334155;padding:2px 6px;border-radius:4px;margin-right:6px;text-transform:uppercase;">${PLATFORM}</span>
            <button id="jb-close" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:18px;line-height:1;">×</button>
          </div>
        </div>
        <div id="jb-status" style="font-size:12px;color:#94a3b8;margin-bottom:12px;min-height:18px;">Checking server...</div>

        <button id="jb-fill" style="width:100%;padding:10px;margin-bottom:8px;background:#10b981;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">Fill Profile</button>
        <button id="jb-cover" style="width:100%;padding:10px;margin-bottom:8px;background:#3b82f6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">Generate Cover Letter</button>
        <button id="jb-all" style="width:100%;padding:10px;margin-bottom:8px;background:#8b5cf6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">Fill All (Profile + Cover)</button>
        <button id="jb-jobs" style="width:100%;padding:10px;background:#ef4444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">Open Latest Jobs</button>

        <div id="jb-extra" style="margin-top:10px;font-size:12px;"></div>
        <div id="jb-warning" style="margin-top:10px;font-size:11px;color:#fbbf24;display:none;"></div>
      </div>
    `;
    document.body.appendChild(panel);

    const $ = id => document.getElementById(id);
    const statusEl = $('jb-status');
    const extraEl = $('jb-extra');
    const warningEl = $('jb-warning');

    function setStatus(msg) { statusEl.textContent = msg; }
    function showWarning(msg) { warningEl.textContent = msg; warningEl.style.display = 'block'; }

    $('jb-close').onclick = () => { panel.style.display = 'none'; };
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.shiftKey && e.key === 'J') {
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        }
    });

    /* ── Server health ── */
    fetch(`${SERVER}/`).then(r => r.json()).then(() => {
        setStatus('Connected — ready');
    }).catch(() => {
        setStatus('⚠️ Server offline. Run: uv run python src/server.py');
    });

    /* ── Field helpers ── */
    function getLabel(el) {
        if (el.id) {
            const lbl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
            if (lbl) return lbl.innerText;
        }
        const parent = el.closest('label');
        if (parent) return parent.innerText;
        const ariaId = el.getAttribute('aria-labelledby');
        if (ariaId) {
            const lbl = document.getElementById(ariaId);
            if (lbl) return lbl.innerText;
        }
        return el.getAttribute('aria-label') || '';
    }

    function queryPlatformOrGeneric(type) {
        const sels = SELECTORS[PLATFORM][type] || [];
        for (const s of sels) {
            const el = document.querySelector(s);
            if (el) return el;
        }
        const keywords = {
            firstName: ['first name', 'given name', 'fname', 'first-name'],
            lastName: ['last name', 'surname', 'lname', 'last-name'],
            fullName: ['full name', 'name', 'your name'],
            email: ['email', 'e-mail'],
            phone: ['phone', 'mobile', 'cell', 'tel'],
            coverLetter: ['cover letter', 'additional', 'message', 'why', 'tell us', 'comments', 'note', 'summary'],
            resume: ['resume', 'cv', 'upload']
        }[type] || [];
        const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select');
        for (const el of inputs) {
            const text = `${getLabel(el)} ${el.placeholder || ''} ${el.name || ''} ${el.id || ''}`.toLowerCase();
            if (keywords.some(k => text.includes(k))) return el;
        }
        return null;
    }

    function setField(el, value) {
        if (!el) return false;
        if (el.tagName === 'SELECT') {
            const opts = Array.from(el.options);
            const yesOpt = opts.find(o => /yes|agree|confirm|accept/i.test(o.text));
            if (yesOpt) el.value = yesOpt.value;
            else if (opts.length > 1) el.value = opts[1].value;
        } else {
            el.focus();
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.blur();
        }
        return true;
    }

    /* ── Profile ── */
    async function loadProfile() {
        if (profileCache) return profileCache;
        const res = await fetch(`${SERVER}/profile`);
        profileCache = await res.json();
        if (profileCache.error) throw new Error(profileCache.error);
        return profileCache;
    }

    async function fillProfile() {
        const p = await loadProfile();
        let filled = 0;
        let fn = queryPlatformOrGeneric('firstName');
        let ln = queryPlatformOrGeneric('lastName');
        if (!fn && !ln) {
            const full = queryPlatformOrGeneric('fullName');
            if (full) { setField(full, p.name); filled++; }
        } else {
            if (setField(fn, p.first_name)) filled++;
            if (setField(ln, p.last_name)) filled++;
        }
        if (setField(queryPlatformOrGeneric('email'), p.email)) filled++;
        if (setField(queryPlatformOrGeneric('phone'), p.phone)) filled++;
        return filled;
    }

    $('jb-fill').onclick = async () => {
        try {
            setStatus('Filling profile...');
            const n = await fillProfile();
            setStatus(`Filled ${n} profile fields. Upload resume manually.`);
            const resumeEl = queryPlatformOrGeneric('resume');
            if (resumeEl) showWarning('⚠️ Resume upload must be done manually (browser security).');
        } catch (e) { setStatus('Error: ' + e.message); }
    };

    /* ── Cover letter ── */
    function extractJobDetails() {
        const h1 = document.querySelector('h1, h2');
        const title = h1 ? h1.innerText.trim() : document.title;
        let company = '';
        const og = document.querySelector('meta[property="og:site_name"]');
        if (og) company = og.content;
        else {
            const m = window.location.hostname.match(/^([^\.]+)\./);
            if (m) company = m[1];
        }
        let desc = '';
        const descSelectors = [
            '[class*="description"]', '[class*="job-description"]', '#jobDescriptionText',
            '[data-testid*="description"]', '.section.page-centered', '[class*="posting"]',
            '[class*="jobDescription"]', '[class*="details"]'
        ];
        for (const s of descSelectors) {
            const el = document.querySelector(s);
            if (el) { desc = el.innerText.substring(0, 2500); break; }
        }
        return { job_title: title, company, description: desc };
    }

    async function fillCoverLetter() {
        const p = await loadProfile();
        const job = extractJobDetails();
        setStatus('Generating cover letter...');
        const res = await fetch(`${SERVER}/cover-letter`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile: p, ...job })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        const el = queryPlatformOrGeneric('coverLetter');
        if (el) {
            setField(el, data.cover_letter);
            return { filled: true, text: data.cover_letter };
        } else {
            return { filled: false, text: data.cover_letter };
        }
    }

    $('jb-cover').onclick = async () => {
        try {
            const result = await fillCoverLetter();
            if (result.filled) {
                setStatus('Cover letter filled.');
            } else {
                extraEl.innerHTML = `<textarea style="width:100%;height:140px;margin-top:8px;font-size:12px;border-radius:4px;padding:8px;">${result.text.replace(/</g,'&lt;')}</textarea>`;
                setStatus('No cover letter field found. Copied above — paste manually.');
            }
        } catch (e) { setStatus('Error: ' + e.message); }
    };

    /* ── Fill All ── */
    $('jb-all').onclick = async () => {
        try {
            setStatus('Filling profile...');
            const n = await fillProfile();
            setStatus('Generating cover letter...');
            const result = await fillCoverLetter();
            if (result.filled) {
                setStatus(`Filled ${n} fields + cover letter. Review & submit.`);
            } else {
                extraEl.innerHTML = `<textarea style="width:100%;height:140px;margin-top:8px;font-size:12px;border-radius:4px;padding:8px;">${result.text.replace(/</g,'&lt;')}</textarea>`;
                setStatus(`Filled ${n} fields. Cover letter copied above — paste manually.`);
            }
            const resumeEl = queryPlatformOrGeneric('resume');
            if (resumeEl) showWarning('⚠️ Remember to upload your resume manually.');
        } catch (e) { setStatus('Error: ' + e.message); }
    };

    /* ── Open Jobs ── */
    $('jb-jobs').onclick = async () => {
        try {
            const res = await fetch(`${SERVER}/jobs`);
            const jobs = await res.json();
            if (!jobs.length) {
                setStatus('No jobs found. Run aggregator first.');
                return;
            }
            const list = jobs.slice(0, 15).map(j =>
                `<li style="margin-bottom:6px;"><a href="${j.url}" target="_blank" style="color:#60a5fa;text-decoration:none;">${j.title} @ ${j.company}</a> <span style="color:#64748b;">(${j.source})</span></li>`
            ).join('');
            extraEl.innerHTML = `<ul style="padding-left:16px;font-size:12px;max-height:240px;overflow-y:auto;">${list}</ul>`;
            setStatus(`Showing ${Math.min(jobs.length, 15)} jobs.`);
        } catch (e) { setStatus('Error loading jobs.'); }
    };
})();
