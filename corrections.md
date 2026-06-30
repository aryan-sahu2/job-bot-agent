Here is the complete rewrite of the UI layer. It replaces the close button with a collapse/expand toggle, adds a loading spinner, makes the collapsed state a small floating pill, and fixes the Mac hotkey by also binding Cmd+Shift+K correctly and adding a click-to-toggle on the collapsed icon itself.
Replace createPanel, toggle, and hotkey logic in content.js
JavaScript
(function() {
    'use strict';
    if (window.__jobbotLoaded) return;
    window.__jobbotLoaded = true;

    const SERVER = 'http://localhost:8765';
    let panel = null;
    let collapsedPill = null;
    let profileCache = null;
    let isCollapsed = false;

    // ===== HYBRID API =====
    function apiRequest(method, url, data) {
        if (typeof GM_xmlhttpRequest !== 'undefined') {
            return new Promise((resolve, reject) => {
                GM_xmlhttpRequest({
                    method: method, url: url,
                    headers: data ? { 'Content-Type': 'application/json' } : {},
                    data: data ? JSON.stringify(data) : null,
                    responseType: 'json',
                    onload: (res) => {
                        if (res.status >= 200 && res.status < 300) {
                            try { resolve(JSON.parse(res.responseText)); }
                            catch (e) { resolve(res.responseText); }
                        } else { reject(new Error('HTTP ' + res.status)); }
                    },
                    onerror: reject
                });
            });
        }
        const options = { method: method, headers: data ? { 'Content-Type': 'application/json' } : {} };
        if (data && method !== 'GET') options.body = JSON.stringify(data);
        return fetch(url, options).then(res => {
            if (!res.ok) throw new Error('HTTP ' + res.status);
            const ct = res.headers.get('content-type');
            return (ct && ct.includes('json')) ? res.json() : res.text();
        });
    }

    // ===== COLLAPSED PILL =====
    function createCollapsedPill() {
        if (collapsedPill) return collapsedPill;
        const pill = document.createElement('div');
        pill.id = 'jobbot-pill';
        pill.innerHTML = `
            <div style="width:20px;height:20px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#8b5cf6);box-shadow:0 2px 8px rgba(99,102,241,0.4);animation:pulse 2s infinite;"></div>
        `;
        pill.style.cssText = `
            position:fixed;bottom:24px;right:24px;width:44px;height:44px;
            background:rgba(15,23,42,0.85);border:1px solid rgba(255,255,255,0.08);
            border-radius:14px;display:flex;align-items:center;justify-content:center;
            cursor:pointer;z-index:999998;backdrop-filter:blur(12px);
            box-shadow:0 8px 24px rgba(0,0,0,0.4);
            transition:all 0.3s cubic-bezier(0.4,0,0.2,1);
            opacity:0.6;
        `;
        
        // Hover: full opacity
        pill.onmouseenter = () => { pill.style.opacity = '1'; pill.style.transform = 'scale(1.08)'; };
        pill.onmouseleave = () => { pill.style.opacity = '0.6'; pill.style.transform = 'scale(1)'; };
        
        // Click to expand
        pill.onclick = () => expandPanel();
        
        // Add pulse animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulse {
                0%,100% { box-shadow:0 0 0 0 rgba(99,102,241,0.4); }
                50% { box-shadow:0 0 0 6px rgba(99,102,241,0); }
            }
            @keyframes spin {
                to { transform:rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
        
        document.body.appendChild(pill);
        collapsedPill = pill;
        return pill;
    }

    function showCollapsedPill() {
        if (!collapsedPill) createCollapsedPill();
        collapsedPill.style.display = 'flex';
        if (panel) panel.style.display = 'none';
        isCollapsed = true;
        sessionStorage.setItem('jobbotCollapsed', 'true');
    }

    function expandPanel() {
        if (collapsedPill) collapsedPill.style.display = 'none';
        if (!panel) createPanel();
        panel.style.display = 'block';
        panel.style.opacity = '0';
        panel.style.transform = 'translateY(12px) scale(0.96)';
        requestAnimationFrame(() => {
            panel.style.transition = 'opacity 0.25s ease, transform 0.25s cubic-bezier(0.34,1.56,0.64,1)';
            panel.style.opacity = '1';
            panel.style.transform = 'translateY(0) scale(1)';
        });
        isCollapsed = false;
        sessionStorage.setItem('jobbotCollapsed', 'false');
    }

    function collapsePanel() {
        if (panel) {
            panel.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
            panel.style.opacity = '0';
            panel.style.transform = 'translateY(8px) scale(0.96)';
            setTimeout(() => {
                panel.style.display = 'none';
                showCollapsedPill();
            }, 200);
        }
    }

    // ===== LOADING STATE =====
    function setLoading(button, text) {
        const original = button.innerHTML;
        button.disabled = true;
        button.style.opacity = '0.7';
        button.style.cursor = 'not-allowed';
        button.innerHTML = `<span style="display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,0.3);border-top-color:#fff;border-radius:50%;animation:spin 0.6s linear infinite;vertical-align:middle;margin-right:6px;"></span> ${text}`;
        return () => {
            button.disabled = false;
            button.style.opacity = '1';
            button.style.cursor = 'pointer';
            button.innerHTML = original;
        };
    }

    // ===== PANEL =====
    function createPanel() {
        if (panel) return panel;
        const div = document.createElement('div');
        div.id = 'jobbot-panel';
        div.innerHTML = `
            <div id="jb-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid rgba(148,163,184,0.12);user-select:none;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:15px;box-shadow:0 2px 8px rgba(99,102,241,0.3);">⚡</div>
                    <div>
                        <div style="font-size:15px;font-weight:600;color:#f8fafc;letter-spacing:-0.01em;">JobBot</div>
                        <div style="font-size:11px;color:#64748b;margin-top:1px;">Auto-fill assistant</div>
                    </div>
                </div>
                <button id="jb-collapse" style="background:rgba(255,255,255,0.05);border:none;color:#94a3b8;cursor:pointer;font-size:16px;width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;transition:all 0.15s;" title="Collapse">−</button>
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
            background:rgba(15,23,42,0.92);color:#e2e8f0;
            border:1px solid rgba(255,255,255,0.06);
            border-radius:16px;padding:18px;
            font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
            font-size:13px;z-index:999999;
            box-shadow:0 25px 50px -12px rgba(0,0,0,0.5),0 0 0 1px rgba(255,255,255,0.04);
            backdrop-filter:blur(16px) saturate(1.2);
            line-height:1.4;
            display:none;
        `;
        
        document.body.appendChild(div);
        panel = div;

        // Collapse button
        const collapseBtn = document.getElementById('jb-collapse');
        collapseBtn.onmouseenter = () => { collapseBtn.style.background = 'rgba(255,255,255,0.1)'; collapseBtn.style.color = '#f8fafc'; };
        collapseBtn.onmouseleave = () => { collapseBtn.style.background = 'rgba(255,255,255,0.05)'; collapseBtn.style.color = '#94a3b8'; };
        collapseBtn.onclick = () => collapsePanel();

        // Fill button
        const fillBtn = document.getElementById('jb-fill');
        fillBtn.onmouseenter = () => { fillBtn.style.transform = 'translateY(-1px)'; fillBtn.style.boxShadow = '0 4px 12px rgba(59,130,246,0.35)'; };
        fillBtn.onmouseleave = () => { fillBtn.style.transform = 'translateY(0)'; fillBtn.style.boxShadow = '0 2px 8px rgba(59,130,246,0.25)'; };
        
        fillBtn.onclick = async () => {
            const done = setLoading(fillBtn, 'Filling...');
            const profile = await fetchProfile();
            if (!profile) {
                alert('JobBot: Cannot reach local server. Run: uv run python src/server.py');
                done();
                return;
            }
            const filled = fillForm(profile);
            done();
            fillBtn.innerHTML = `<span style="font-size:14px;">✅</span> Filled ${filled} fields`;
            setTimeout(() => fillBtn.innerHTML = '<span style="font-size:14px;">🚀</span> Fill Profile', 2500);
        };

        // Cover letter button
        const coverBtn = document.getElementById('jb-cover');
        coverBtn.onmouseenter = () => { coverBtn.style.background = 'rgba(255,255,255,0.08)'; };
        coverBtn.onmouseleave = () => { coverBtn.style.background = 'rgba(255,255,255,0.04)'; };

        coverBtn.onclick = async () => {
            const done = setLoading(coverBtn, 'Generating...');
            const h1 = document.querySelector('h1, h2');
            const title = h1 ? h1.innerText.trim() : document.title;
            const company = document.querySelector('[class*="company"], [class*="employer"]')?.innerText.trim() || '';
            const result = await generateLetter(title, company);
            done();
            
            if (!result || result.error || !result.cover_letter) {
                alert('JobBot: Cover letter generation failed. Is Ollama running?');
                return;
            }
            
            document.getElementById('jb-cover-text').value = result.cover_letter;
            document.getElementById('jb-cover-box').style.display = 'block';
            document.getElementById('jb-cover-meta').textContent = `${result.cover_letter.split(/\s+/).length} words`;
            coverBtn.innerHTML = '<span style="font-size:14px;">🔄</span> Regenerate';
        };

        // Paste
        document.getElementById('jb-paste').onclick = () => {
            const text = document.getElementById('jb-cover-text').value;
            const ok = pasteCoverLetter(text);
            const btn = document.getElementById('jb-paste');
            btn.innerHTML = ok ? '<span>✅</span> Pasted!' : '<span>❌</span> No field found';
            setTimeout(() => btn.innerHTML = '<span>📋</span> Paste into Form', 2000);
        };

        // Copy
        document.getElementById('jb-copy').onclick = () => {
            const text = document.getElementById('jb-cover-text').value;
            navigator.clipboard.writeText(text).then(() => {
                const btn = document.getElementById('jb-copy');
                btn.textContent = '✅';
                setTimeout(() => btn.textContent = '📋', 1500);
            });
        };

        // Server status
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

    // ===== TOGGLE =====
    function toggle() {
        if (isCollapsed) {
            expandPanel();
        } else {
            if (!panel || panel.style.display === 'none') {
                expandPanel();
            } else {
                collapsePanel();
            }
        }
    }

    // ===== HOTKEYS =====
    function handleHotkey(e) {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        const mod = isMac ? e.metaKey : e.ctrlKey;
        
        // Primary: Cmd/Ctrl + Shift + K
        if (mod && e.shiftKey && (e.key === 'k' || e.key === 'K')) {
            e.preventDefault();
            e.stopPropagation();
            toggle();
            return false;
        }
        
        // Fallback: Cmd/Ctrl + Shift + J (since user mentioned it)
        if (mod && e.shiftKey && (e.key === 'j' || e.key === 'J')) {
            e.preventDefault();
            e.stopPropagation();
            toggle();
            return false;
        }
    }

    // Bind at capture phase to beat other listeners
    document.addEventListener('keydown', handleHotkey, true);

    // ===== INIT =====
    function init() {
        // Restore state from session
        const wasCollapsed = sessionStorage.getItem('jobbotCollapsed');
        if (wasCollapsed === 'true') {
            createCollapsedPill();
        } else if (wasCollapsed === 'false') {
            createPanel();
            panel.style.display = 'block';
        } else {
            // First time: auto-show on job pages, collapsed elsewhere
            if (/apply|careers|jobs|posting|application|workable|greenhouse|lever|breezy|recruitee/i.test(location.pathname + location.search)) {
                createPanel();
                panel.style.display = 'block';
                isCollapsed = false;
                sessionStorage.setItem('jobbotCollapsed', 'false');
            } else {
                createCollapsedPill();
                isCollapsed = true;
                sessionStorage.setItem('jobbotCollapsed', 'true');
            }
        }
    }

    // Wait for DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    console.log('[JobBot] Loaded. Hotkeys: Cmd/Ctrl+Shift+K or J. Click pill to expand.');
})();
What Changed
Table
Feature	Before	After
Close button	× that hid the panel forever	− that collapses to a pill
Collapsed state	Gone, unreachable	Small 44×44px floating pill, semi-transparent (0.6), pulses to show it's alive
Re-open	Only via hotkey	Click the pill or hotkey
Loading state	Button text changed to "Filling..."	Spinner animation inside button, disabled state
Hotkey	Only Cmd+Shift+K	Cmd/Ctrl+Shift+K and Cmd/Ctrl+Shift+J, bound at capture phase
Session persistence	None	sessionStorage remembers collapsed/expanded across page navigations
Auto-show	1.5s delay on job pages	Immediate init; auto-expands on job pages, auto-collapses elsewhere
The pill is always visible when collapsed, so you never lose the extension. Click it to expand. The loading spinner gives clear visual feedback during slow LLM calls.