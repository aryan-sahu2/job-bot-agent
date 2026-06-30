The Core Problem:
Your browser extension is using GM_xmlhttpRequest (Tampermonkey's privileged API), but as a native Chrome Extension (loaded unpacked), that API doesn't exist. The error in your console says:
plain
content.js:178 [JobBot] Cannot reach server: ReferenceError: GM_xmlhttpRequest is not defined
Why it worked with Tampermonkey but not as an unpacked extension:
Table
Tampermonkey Userscript	Native Chrome Extension
Has GM_xmlhttpRequest	Does NOT have GM_xmlhttpRequest
Bypasses CORS automatically	Must use fetch() with CORS headers
Can call http://localhost from https:// pages	Blocked by mixed-content/CORS
Two separate issues to fix:
Fix 1: Replace GM_xmlhttpRequest with fetch() for native extension use
In content.js, replace the apiRequest function:
JavaScript
// REPLACE this entire function:
function apiRequest(method, url, data) {
    return new Promise((resolve, reject) => {
        GM_xmlhttpRequest({...})  // <-- This doesn't exist in extensions!
    });
}

// WITH this:
function apiRequest(method, url, data) {
    const options = {
        method: method,
        headers: data ? { 'Content-Type': 'application/json' } : {},
    };
    if (data && method !== 'GET') {
        options.body = JSON.stringify(data);
    }
    return fetch(url, options)
        .then(res => {
            if (!res.ok) throw new Error('HTTP ' + res.status);
            const ct = res.headers.get('content-type');
            if (ct && ct.includes('application/json')) {
                return res.json();
            }
            return res.text();
        });
}
But wait — fetch() from a content script on https://indeed.com to http://localhost:8765 will be blocked by CORS. Your server already has CORS enabled, which is good. But you also need to add http://localhost:8765 to host_permissions in your manifest, which you already have.
However, there's a subtlety: Manifest V3 content scripts use fetch() which respects CORS, but the server's CORS middleware should handle it. Let me verify your server CORS is actually working...
Looking at your server.py, you have:
Python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
That looks correct. But the request might fail because Chrome extensions have additional restrictions. You should also check if the request is actually going out — look in the Network tab of DevTools (not just console) to see if the request to localhost:8765 is being made and what's happening.
Fix 2: The "no fields filled" issue
Even when Tampermonkey was working and the server was connected, fields weren't filling. Looking at your fillForm function, I see a logic issue:
JavaScript
function fillForm(profile) {
    const p = detectPlatform();
    const s = p.selectors;
    let n = 0;

    if (s.firstName && s.lastName) {
        // This branch only runs if BOTH selectors exist
        const parts = (profile.name || '').split(' ');
        if (fillField(s.firstName, parts[0])) n++;
        if (fillField(s.lastName, parts.slice(1).join(' '))) n++;
    } else if (s.fullName) {
        // This only runs if NO firstName/lastName selectors
        if (fillField(s.fullName, profile.name)) n++;
    }
    // ... rest
}
Problem: On Indeed's Smart Apply, the selectors might not match. Your indeed selectors are:
JavaScript
fullName: 'input[name="name"], input[placeholder*="Full name" i]',
email: 'input[name="email"], input[type="email"]',
phone: 'input[name="phone"], input[type="tel"]',
But Indeed's Smart Apply form might use different name attributes or no name at all. You need to inspect the actual DOM on the Indeed apply page.
Also, your fallback logic only fires if (!n) — meaning if zero fields were filled by the primary selectors. But if fullName fails but email succeeds, n would be 1, and the fallback won't run. The phone might also fail. So you could end up with only email filled.
Quick Diagnostic Steps
Open DevTools on the Indeed apply page
Go to Console tab — run this to test if fetch works:
JavaScript
fetch('http://localhost:8765/profile').then(r => r.json()).then(console.log).catch(console.error)
Go to Network tab — check if requests to localhost:8765 are actually being made
Inspect the form fields — run in console:
JavaScript
// See what inputs exist
document.querySelectorAll('input').forEach(i => console.log(i.name, i.placeholder, i.id))
Recommended Fix: Make it work as BOTH Tampermonkey userscript AND native extension
Replace your apiRequest function with a hybrid approach:
JavaScript
function apiRequest(method, url, data) {
    // Try GM_xmlhttpRequest first (Tampermonkey)
    if (typeof GM_xmlhttpRequest !== 'undefined') {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: method,
                url: url,
                headers: data ? { 'Content-Type': 'application/json' } : {},
                data: data ? JSON.stringify(data) : null,
                responseType: 'json',
                onload: (res) => {
                    if (res.status >= 200 && res.status < 300) {
                        try { resolve(JSON.parse(res.responseText)); } 
                        catch (e) { resolve(res.responseText); }
                    } else {
                        reject(new Error('HTTP ' + res.status));
                    }
                },
                onerror: reject
            });
        });
    }
    
    // Fallback to fetch (native extension)
    const options = {
        method: method,
        headers: data ? { 'Content-Type': 'application/json' } : {},
    };
    if (data && method !== 'GET') {
        options.body = JSON.stringify(data);
    }
    return fetch(url, options).then(res => {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const ct = res.headers.get('content-type');
        return (ct && ct.includes('json')) ? res.json() : res.text();
    });
}
For the "fields not filling" issue
Add better debugging and more robust selectors. Here's an improved fillForm:
JavaScript
function fillForm(profile) {
    const p = detectPlatform();
    const s = p.selectors;
    let n = 0;

    console.log('[JobBot] Platform detected:', p.name);
    console.log('[JobBot] Profile:', profile);
    console.log('[JobBot] Selectors:', s);

    // Try structured name fields first
    if (s.firstName && s.lastName) {
        const parts = (profile.name || '').split(' ');
        if (fillField(s.firstName, parts[0])) n++;
        if (fillField(s.lastName, parts.slice(1).join(' '))) n++;
    }
    
    // Also try fullName (don't use else-if)
    if (s.fullName && !document.querySelector(s.firstName)?.value) {
        if (fillField(s.fullName, profile.name)) n++;
    }

    if (fillField(s.email, profile.email)) n++;
    if (fillField(s.phone, profile.phone)) n++;

    // Always run fallback for any remaining empty fields
    const inputs = document.querySelectorAll('input');
    inputs.forEach(inp => {
        if (inp.value) return; // already filled
        const nm = (inp.name || '').toLowerCase();
        const ph = (inp.placeholder || '').toLowerCase();
        const id = (inp.id || '').toLowerCase();
        const type = inp.type;
        
        if ((type === 'email' || nm.includes('email') || ph.includes('email') || id.includes('email')) && profile.email) {
            inp.value = profile.email; 
            inp.dispatchEvent(new Event('input', {bubbles:true})); 
            n++;
        }
        if ((nm.includes('phone') || nm.includes('tel') || ph.includes('phone') || id.includes('phone') || type === 'tel') && profile.phone) {
            inp.value = profile.phone; 
            inp.dispatchEvent(new Event('input', {bubbles:true})); 
            n++;
        }
        if ((nm.includes('name') || ph.includes('name') || id.includes('name')) && profile.name && !inp.value) {
            inp.value = profile.name;
            inp.dispatchEvent(new Event('input', {bubbles:true}));
            n++;
        }
    });
    
    console.log(`[JobBot] Filled ${n} fields`);
    return n;
}
Summary of changes needed:
Table
File	Change
content.js	Make apiRequest hybrid (GM_xmlhttpRequest + fetch fallback)
content.js	Improve fillForm to not use else if, add more fallback selectors
content.js	Add more console logging for debugging
manifest.json	Consider adding "permissions": ["activeTab"] if needed