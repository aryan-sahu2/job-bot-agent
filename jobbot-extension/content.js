(function () {
  "use strict";
  if (window.__jobbotLoaded) return;
  window.__jobbotLoaded = true;

  const SERVER = "http://localhost:8765";
  let panel = null;
  let profileCache = null;

  // ===== HYBRID API =====
  function apiRequest(method, url, data) {
    if (typeof GM_xmlhttpRequest !== "undefined") {
      return new Promise((resolve, reject) => {
        GM_xmlhttpRequest({
          method: method,
          url: url,
          headers: data ? { "Content-Type": "application/json" } : {},
          data: data ? JSON.stringify(data) : null,
          responseType: "json",
          onload: (res) => {
            if (res.status >= 200 && res.status < 300) {
              try {
                resolve(JSON.parse(res.responseText));
              } catch (e) {
                resolve(res.responseText);
              }
            } else {
              reject(new Error("HTTP " + res.status));
            }
          },
          onerror: reject,
        });
      });
    }
    const options = {
      method: method,
      headers: data ? { "Content-Type": "application/json" } : {},
    };
    if (data && method !== "GET") options.body = JSON.stringify(data);
    return fetch(url, options).then((res) => {
      if (!res.ok) throw new Error("HTTP " + res.status);
      const ct = res.headers.get("content-type");
      return ct && ct.includes("json") ? res.json() : res.text();
    });
  }

  // ===== UNIVERSAL FIELD FINDER =====
  function getAllTextClues(el) {
    const clues = [];
    const add = (s) => {
      if (s) clues.push(s.toLowerCase().trim());
    };

    // Direct attributes
    add(el.placeholder);
    add(el.name);
    add(el.id);
    add(el.getAttribute("aria-label"));
    add(el.getAttribute("data-testid"));
    add(el.getAttribute("automation-id"));
    add(el.getAttribute("data-automation-id"));
    add(el.getAttribute("aria-labelledby"));

    // Type hint
    if (el.type && el.type !== "text") add(el.type);

    // Associated labels
    if (el.labels) Array.from(el.labels).forEach((l) => add(l.innerText));

    // aria-labelledby dereference
    const lbId = el.getAttribute("aria-labelledby");
    if (lbId) {
      lbId.split(/\s+/).forEach((id) => {
        const el2 = document.getElementById(id);
        if (el2) add(el2.innerText);
      });
    }

    // Parent chain (up to 4 levels)
    let parent = el.parentElement;
    for (let i = 0; i < 4 && parent; i++) {
      if (parent.tagName === "LABEL") add(parent.innerText);
      // Look for label-like child
      const labelChild = parent.querySelector(
        'label, .label, [class*="label"]',
      );
      if (labelChild && labelChild !== el) add(labelChild.innerText);
      parent = parent.parentElement;
    }

    // Previous siblings
    let prev = el.previousElementSibling;
    for (let i = 0; i < 3 && prev; i++) {
      add(prev.innerText);
      prev = prev.previousElementSibling;
    }

    // Grandparent first line (for grouped fields with headers)
    const gp = el.parentElement?.parentElement;
    if (gp) {
      const firstLine = gp.innerText?.split("\n")[0]?.trim();
      if (firstLine && firstLine.length < 100) add(firstLine);
    }

    return clues.filter((c) => c.length > 0);
  }

  function scoreField(clues, fieldType) {
    const patterns = {
      firstName: {
        strong: [
          "first name",
          "firstname",
          "first-name",
          "given name",
          "fname",
          "first_name",
          "firstName",
          "first_name",
        ],
        weak: ["first", "name"],
        avoid: ["last", "company", "business", "user name", "username"],
      },
      lastName: {
        strong: [
          "last name",
          "lastname",
          "last-name",
          "surname",
          "family name",
          "lname",
          "last_name",
          "lastName",
        ],
        weak: ["last", "name"],
        avoid: ["first", "company", "business", "maiden"],
      },
      fullName: {
        strong: [
          "full name",
          "fullname",
          "full-name",
          "your name",
          "applicant name",
          "complete name",
          "fullName",
        ],
        weak: ["name"],
        avoid: [
          "company",
          "business",
          "user name",
          "username",
          "first name",
          "last name",
          "email",
        ],
      },
      email: {
        strong: [
          "email",
          "e-mail",
          "email address",
          "e mail",
          "mail address",
          "contact email",
          "emailAddress",
        ],
        weak: ["mail"],
        avoid: [
          "confirm",
          "verify",
          "re-enter",
          "reenter",
          "repeat",
          "secondary",
          "alternative",
          "phone",
        ],
      },
      phone: {
        strong: [
          "phone",
          "mobile",
          "cell",
          "telephone",
          "contact number",
          "phone number",
          "cellphone",
          "tel",
          "mobile number",
          "phoneNumber",
        ],
        weak: ["number", "contact"],
        avoid: [
          "years",
          "experience",
          "salary",
          "age",
          "postal",
          "zip",
          "count",
        ],
      },
      currentRole: {
        strong: [
          "current role",
          "last role",
          "current position",
          "job title",
          "title",
          "current job",
          "present role",
          "most recent role",
          "currentRole",
        ],
        weak: ["role", "position", "job"],
        avoid: ["expected", "desired", "applying for", "next"],
      },
      yearsExperience: {
        strong: [
          "years of experience",
          "years experience",
          "experience",
          "yoe",
          "years of work",
          "how many years",
          "yearsExperience",
        ],
        weak: ["years"],
        avoid: ["salary", "age", "phone"],
      },
      location: {
        strong: [
          "current location",
          "location",
          "city",
          "address",
          "currentLocation",
          "current_location",
          "based in",
          "where are you based",
        ],
        weak: ["place", "area", "based", "located"],
        avoid: ["remote", "relocation", "relocate"],
      },
      salary: {
        strong: ["salary", "current salary", "pay"],
        weak: ["amount", "range"],
        avoid: ["years", "experience", "expected", "desired"],
      },
      expectedCtc: {
        strong: [
          "expected ctc",
          "expected salary",
          "compensation",
          "expected pay",
          "salary expectation",
          "salaryExpectation",
          "expectedCompensation",
          "desired salary",
          "expected compensation",
          "pay expectation",
          "ctc",
          "lpa",
        ],
        weak: ["salary", "pay", "amount", "range", "inr", "rupees"],
        avoid: ["current", "last drawn", "previous", "history", "years"],
      },
      coverLetter: {
        strong: [
          "cover letter",
          "coverletter",
          "cover_letter",
          "message",
          "additional information",
          "why",
          "tell us about",
          "note",
          "comments",
          "coverLetter",
        ],
        weak: ["letter", "additional", "message"],
        avoid: ["resume", "cv"],
      },
      linkedin: {
        strong: [
          "linkedin",
          "linked in",
          "linkedin profile",
          "linkedin url",
          "linkedinUrl",
          "linkedin_url",
        ],
        weak: ["social", "profile url"],
        avoid: [],
      },
      portfolio: {
        strong: [
          "portfolio",
          "portfolio url",
          "portfolio website",
          "portfolio link",
          "portfolioUrl",
          "portfolio_url",
          "personal portfolio",
          "your portfolio",
        ],
        weak: ["site", "url", "website", "link"],
        avoid: ["github", "gitlab", "company", "business", "employer", "code"],
      },
      github: {
        strong: [
          "github",
          "gitlab",
          "github url",
          "gitlab url",
          "githubUrl",
          "gitlabUrl",
          "github_url",
          "gitlab_url",
          "source code",
          "code repository",
        ],
        weak: ["code", "repo", "repository", "url", "git"],
        avoid: ["portfolio", "website", "linkedin", "personal"],
      },
      website: {
        strong: ["website", "personal site", "url", "web"],
        weak: ["link", "site"],
        avoid: [
          "linkedin",
          "portfolio",
          "github",
          "gitlab",
          "company",
          "business",
        ],
      },
      noticePeriod: {
        strong: [
          "availability",
          "notice period",
          "weeks notice",
          "how soon",
          "joining",
          "available",
          "start date",
          "when can you",
          "notice",
          "noticePeriod",
        ],
        weak: ["weeks", "availability", "days"],
        avoid: ["salary", "experience", "age"],
      },
      referralSource: {
        strong: [
          "how did you hear",
          "source",
          "referral",
          "where did you find",
          "how did you find",
          "referred by",
          "how did you hear about us",
          "referralSource",
        ],
        weak: ["hear", "find", "about us", "discover"],
        avoid: [],
      },
    };

    const p = patterns[fieldType];
    if (!p) return 0;

    let score = 0;
    const allText = clues.join(" ");

    for (const c of clues) {
      for (const s of p.strong) {
        if (c === s) score += 15;
        else if (c.includes(s)) score += 8;
      }
      for (const w of p.weak) {
        if (c === w) score += 4;
        else if (c.includes(w)) score += 2;
      }
      for (const a of p.avoid) {
        if (c.includes(a)) score -= 6;
      }
    }

    // Type bonuses
    if (fieldType === "email" && clues.some((c) => c.includes("@"))) score += 3;
    if (fieldType === "phone" && clues.some((c) => /\+?\d{3,}/.test(c)))
      score += 3;
    if (
      fieldType === "yearsExperience" &&
      clues.some((c) => /\d+\+?\s*years?/.test(c))
    )
      score += 5;

    return score;
  }

  function findBestInputs() {
    const allInputs = Array.from(
      document.querySelectorAll("input, textarea, select"),
    );

    const visibleInputs = allInputs.filter((el) => {
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return (
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        rect.width > 5 &&
        rect.height > 5 &&
        !el.disabled &&
        !el.readOnly
      );
    });

    console.log(
      `[JobBot] Found ${visibleInputs.length} visible inputs out of ${allInputs.length}`,
    );

    const candidates = {};
    const assigned = new Set();
    const types = [
      "firstName",
      "lastName",
      "fullName",
      "email",
      "phone",
      "currentRole",
      "yearsExperience",
      "location",
      "salary",
      "expectedCtc",
      "portfolio",
      "github",
      "linkedin",
      "website",
      "coverLetter",
      "noticePeriod",
      "referralSource",
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
        console.log(
          `[JobBot] MATCH ${type} (score ${bestScore}): clues=[${getAllTextClues(best).slice(0, 4).join(", ")}]`,
        );
      }
    }

    // Log unmatched inputs for debugging
    const unmatched = visibleInputs.filter((el) => !assigned.has(el));
    if (unmatched.length > 0) {
      console.log(`[JobBot] ${unmatched.length} unmatched inputs:`);
      unmatched.slice(0, 5).forEach((el) => {
        console.log(
          `  - ${el.tagName} type=${el.type} name=${el.name} clues=[${getAllTextClues(el).slice(0, 3).join(", ")}]`,
        );
      });
    }

    return candidates;
  }

  // ===== REACT-PROOF VALUE SETTER =====
  function setInputValue(el, value) {
    if (!el || value === undefined || value === null || value === "")
      return false;

    el.focus();
    el.scrollIntoView({ behavior: "instant", block: "center" });

    // Handle select dropdowns
    if (el.tagName === "SELECT") {
      const valLower = String(value).toLowerCase();
      const options = Array.from(el.options);
      const match = options.find(
        (opt) =>
          opt.text.toLowerCase().includes(valLower) ||
          opt.value.toLowerCase().includes(valLower),
      );
      if (match) {
        el.value = match.value;
        el.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
      return false;
    }

    // Native setter for inputs/textareas
    const proto =
      el.tagName === "TEXTAREA"
        ? window.HTMLTextAreaElement.prototype
        : window.HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    if (descriptor && descriptor.set) {
      descriptor.set.call(el, value);
    } else {
      el.value = value;
    }

    const events = [
      new Event("focus", { bubbles: true }),
      new Event("keydown", { bubbles: true, cancelable: true }),
      new Event("keypress", { bubbles: true, cancelable: true }),
      new InputEvent("input", {
        bubbles: true,
        cancelable: true,
        inputType: "insertText",
      }),
      new Event("keyup", { bubbles: true, cancelable: true }),
      new Event("change", { bubbles: true }),
      new Event("blur", { bubbles: true }),
    ];
    for (const ev of events) {
      el.dispatchEvent(ev);
    }

    return true;
  }

  // ===== FORM FILLING =====
  function fillForm(profile) {
    console.log("[JobBot] === Starting form fill ===");
    console.log(
      "[JobBot] Profile:",
      JSON.stringify({
        name: profile.name,
        email: profile.email,
        phone: profile.phone,
        portfolio: profile.portfolio,
        github: profile.github,
        linkedin: profile.linkedin,
      }),
    );

    const fields = findBestInputs();
    let filled = 0;
    const log = [];

    const nameParts = (profile.name || "")
      .split(/\s+/)
      .filter((p) => p.length > 0);
    const firstName = profile.first_name || nameParts[0] || "";
    const lastName =
      profile.last_name ||
      (nameParts.length > 1 ? nameParts.slice(1).join(" ") : "");

    if (fields.firstName && firstName) {
      if (setInputValue(fields.firstName, firstName)) {
        filled++;
        log.push("firstName");
      }
    }
    if (fields.lastName && lastName) {
      if (setInputValue(fields.lastName, lastName)) {
        filled++;
        log.push("lastName");
      }
    }
    if (
      !fields.firstName &&
      !fields.lastName &&
      fields.fullName &&
      profile.name
    ) {
      if (setInputValue(fields.fullName, profile.name)) {
        filled++;
        log.push("fullName");
      }
    }

    if (fields.email && profile.email) {
      if (setInputValue(fields.email, profile.email)) {
        filled++;
        log.push("email");
      }
    }

    if (fields.phone && profile.phone && !profile.phone.includes("@")) {
      if (setInputValue(fields.phone, profile.phone)) {
        filled++;
        log.push("phone");
      }
    }

    if (fields.currentRole && profile.current_role) {
      if (setInputValue(fields.currentRole, profile.current_role)) {
        filled++;
        log.push("currentRole");
      }
    }

    if (fields.yearsExperience && profile.years_experience) {
      if (setInputValue(fields.yearsExperience, profile.years_experience)) {
        filled++;
        log.push("yearsExperience");
      }
    }

    if (fields.location && profile.location) {
      if (setInputValue(fields.location, profile.location)) {
        filled++;
        log.push("location");
      }
    }

    if (fields.expectedCtc && profile.expected_ctc) {
      if (setInputValue(fields.expectedCtc, profile.expected_ctc)) {
        filled++;
        log.push("expectedCtc");
      }
    }

    if (
      fields.noticePeriod &&
      profile.notice_period_weeks !== undefined &&
      profile.notice_period_weeks !== ""
    ) {
      if (setInputValue(fields.noticePeriod, profile.notice_period_weeks)) {
        filled++;
        log.push("noticePeriod");
      }
    }

    if (fields.referralSource && profile.referral_source) {
      if (setInputValue(fields.referralSource, profile.referral_source)) {
        filled++;
        log.push("referralSource");
      }
    }

    if (fields.linkedin && profile.linkedin) {
      if (setInputValue(fields.linkedin, profile.linkedin)) {
        filled++;
        log.push("linkedin");
      }
    }

    if (fields.portfolio && profile.portfolio) {
      if (setInputValue(fields.portfolio, profile.portfolio)) {
        filled++;
        log.push("portfolio");
      }
    }

    if (fields.github && profile.github) {
      if (setInputValue(fields.github, profile.github)) {
        filled++;
        log.push("github");
      }
    }

    // Generic website fallback only if no specific fields matched
    if (fields.website && !fields.portfolio && !fields.github) {
      const webUrl =
        profile.portfolio || profile.website || profile.github || "";
      if (webUrl) {
        if (setInputValue(fields.website, webUrl)) {
          filled++;
          log.push("website");
        }
      }
    }

    console.log(`[JobBot] === Filled ${filled} fields: ${log.join(", ")} ===`);
    return filled;
  }

  function pasteCoverLetter(text) {
    const fields = findBestInputs();
    if (fields.coverLetter) {
      return setInputValue(fields.coverLetter, text);
    }
    // Fallback: any large textarea not already matched
    const textareas = Array.from(document.querySelectorAll("textarea")).filter(
      (el) => {
        const style = window.getComputedStyle(el);
        return (
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          el.offsetHeight > 80
        );
      },
    );
    if (textareas.length === 1) {
      return setInputValue(textareas[0], text);
    }
    return false;
  }

  function getDescription() {
    const selectors = [
      '[class*="job-description"]',
      '[class*="jobDescription"]',
      '[id*="job-description"]',
      '[id*="jobDescription"]',
      ".show-more-less-html__markup",
      ".description__text",
      '[data-testid="job-description"]',
      ".posting-description",
      ".section.page-centered",
      "article",
      "main",
    ];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.innerText.length > 100) return el.innerText.slice(0, 3000);
    }
    const ps = Array.from(document.querySelectorAll("p, li"));
    if (ps.length)
      return ps
        .map((p) => p.innerText)
        .join("\n")
        .slice(0, 3000);
    return document.body.innerText.slice(0, 3000);
  }

  async function fetchProfile() {
    if (profileCache) return profileCache;
    try {
      profileCache = await apiRequest("GET", `${SERVER}/profile`);
      return profileCache;
    } catch (e) {
      console.error("[JobBot] Cannot reach server:", e);
      return null;
    }
  }

  async function generateLetter(title, company) {
    const profile = await fetchProfile();
    if (!profile) return null;
    try {
      return await apiRequest("POST", `${SERVER}/cover-letter`, {
        profile,
        job_title: title || document.title,
        company: company || "",
        description: getDescription(),
      });
    } catch (e) {
      console.error("[JobBot] Cover letter failed:", e);
      return null;
    }
  }

  // ===== UI =====
  function createPanel() {
    if (panel) return panel;
    const div = document.createElement("div");
    div.id = "jobbot-panel";
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

    document.getElementById("jb-close").onclick = () =>
      (div.style.display = "none");

    document.getElementById("jb-fill").onclick = async () => {
      const btn = document.getElementById("jb-fill");
      btn.textContent = "Filling...";
      const profile = await fetchProfile();
      if (!profile) {
        alert(
          "JobBot: Cannot reach local server. Make sure you ran: uv run python src/server.py",
        );
        btn.textContent = "Fill Profile";
        return;
      }
      const filled = fillForm(profile);
      btn.textContent = `Filled ${filled} field${filled !== 1 ? "s" : ""}`;
      setTimeout(() => (btn.textContent = "Fill Profile"), 2000);
    };

    document.getElementById("jb-cover").onclick = async () => {
      const btn = document.getElementById("jb-cover");
      btn.textContent = "Generating...";
      const h1 = document.querySelector("h1, h2");
      const title = h1 ? h1.innerText.trim() : document.title;
      const company =
        document
          .querySelector('[class*="company"], [class*="employer"]')
          ?.innerText.trim() || "";
      const result = await generateLetter(title, company);
      if (!result) {
        alert("JobBot: Cover letter request failed entirely.");
        btn.textContent = "Generate Cover Letter";
        return;
      }
      if (result.error) {
        alert(`JobBot: Cover letter failed — ${result.error}`);
        btn.textContent = "Generate Cover Letter";
        return;
      }
      if (!result.cover_letter) {
        alert(
          "JobBot: Cover letter came back empty. Is Ollama running with the correct model?",
        );
        btn.textContent = "Generate Cover Letter";
        return;
      }
      document.getElementById("jb-cover-text").value = result.cover_letter;
      document.getElementById("jb-cover-box").style.display = "block";
      btn.textContent = "Regenerate";
    };

    document.getElementById("jb-paste").onclick = () => {
      const text = document.getElementById("jb-cover-text").value;
      const ok = pasteCoverLetter(text);
      const btn = document.getElementById("jb-paste");
      btn.textContent = ok ? "Pasted!" : "No cover letter field found";
      setTimeout(() => (btn.textContent = "Paste into Form"), 2000);
    };

    apiRequest("GET", `${SERVER}/`)
      .then(() => {
        const st = document.getElementById("jb-status");
        st.textContent = "Server: connected";
        st.style.color = "#10b981";
      })
      .catch(() => {
        const st = document.getElementById("jb-status");
        st.textContent = "Server: offline";
        st.style.color = "#ef4444";
      });

    console.log("[JobBot] Panel created");
    return div;
  }

  function toggle() {
    if (!panel) createPanel();
    else
      panel.style.display = panel.style.display === "none" ? "block" : "none";
  }

  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "k") {
      e.preventDefault();
      toggle();
    }
  });

  if (
    /apply|careers|jobs|posting|application/.test(
      location.pathname + location.search,
    )
  ) {
    setTimeout(() => {
      console.log("[JobBot] Auto-creating panel on job page");
      createPanel();
    }, 1500);
  }

  console.log("[JobBot] Loaded. Press Cmd+Shift+K to toggle panel.");
})();
