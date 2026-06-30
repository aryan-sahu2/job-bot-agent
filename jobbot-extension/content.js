(function () {
  "use strict";
  if (window.__jobbotLoaded) return;
  window.__jobbotLoaded = true;

  const SERVER = "http://localhost:8765";
  let panel = null;
  let profileCache = null;
    let collapsedPill = null;
    let isCollapsed = false;

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
    add(el.getAttribute("aria-describedby"));

    // Type hint
    if (el.type && el.type !== "text") add(el.type);

    // Associated labels (by for=id match)
    if (el.labels) Array.from(el.labels).forEach((l) => add(l.innerText));

    // aria-labelledby / aria-describedby dereference
    ["aria-labelledby", "aria-describedby"].forEach((attr) => {
      const ids = el.getAttribute(attr);
      if (ids) {
        ids.split(/\s+/).forEach((id) => {
          const el2 = document.getElementById(id);
          if (el2) add(el2.innerText);
        });
      }
    });

    // Parent chain (up to 4 levels)
    let parent = el.parentElement;
    for (let i = 0; i < 4 && parent; i++) {
      if (parent.tagName === "LABEL") add(parent.innerText);
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

    // Next siblings (labels sometimes appear after in odd DOM structures)
    let next = el.nextElementSibling;
    for (let i = 0; i < 2 && next; i++) {
      if (
        next.tagName === "LABEL" ||
        (next.innerText && next.innerText.length < 100)
      ) {
        add(next.innerText);
      }
      next = next.nextElementSibling;
    }

    // CRITICAL: Look for ANY label inside the same field wrapper
    // This catches React/Vue forms where label and input are siblings in a div.space-y-2
    const container = el.closest(
      '.space-y-2, .form-field, [class*="field"], [class*="form-group"], [class*="FormItem"], div',
    );
    if (container) {
      const allLabels = container.querySelectorAll(
        'label, [id*="Question"], [class*="label"], [class*="Label"]',
      );
      allLabels.forEach((lbl) => {
        if (lbl !== el) add(lbl.innerText);
      });
    }

    // Grandparent first line
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
          "behance",
          "dribbble",
          "xing",
          "profilexing",
          "social profile",
          "professional profile",
        ],
        weak: ["site", "url", "website", "link", "profile"],
        avoid: [
          "github",
          "gitlab",
          "company",
          "business",
          "employer",
          "code",
          "linkedin",
        ],
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
        avoid: [
          "portfolio",
          "website",
          "linkedin",
          "personal",
          "behance",
          "xing",
        ],
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
          "behance",
          "xing",
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

  function isLikelyCustomQuestion(el) {
    if (
      el.tagName !== "TEXTAREA" &&
      (el.type !== "text" || !el.maxLength || el.maxLength < 200)
    ) {
      return false;
    }

    const clues = getAllTextClues(el);
    const text = clues.join(" ");
    const placeholder = (el.placeholder || "").toLowerCase();
    const name = el.name || "";
    const id = el.id || "";

    let score = 0;
    if (/^\d+$/.test(name)) score += 3;
    if (/candidateAnswer|customQuestion|question/i.test(id)) score += 3;
    if (
      /write your answer|enter your answer|type here|your response/i.test(
        placeholder,
      )
    )
      score += 2;
    if (text.includes("?")) score += 2;
    if (
      /\b(write|describe|tell us|explain|share|brief|detail|answer|introduction|about yourself|background|why|how|what|motivation|challenge|strength|weakness|achievement|note:|please)\b/i.test(
        text,
      )
    )
      score += 2;
    if (el.tagName === "TEXTAREA") score += 1;
    if (el.maxLength > 500) score += 1;

    const wrapper = el.closest(
      '.space-y-2, [class*="form-item"], [class*="field-wrapper"]',
    );
    if (wrapper && wrapper.querySelector("label")?.innerText.length > 50)
      score += 1;

    return score >= 3;
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

    const standardInputs = [];
    const customQuestions = [];

    for (const el of visibleInputs) {
      if (isLikelyCustomQuestion(el)) {
        customQuestions.push(el);
      } else {
        standardInputs.push(el);
      }
    }

    console.log(
      `[JobBot] ${visibleInputs.length} total | ${customQuestions.length} custom questions | ${standardInputs.length} standard`,
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
      "expectedCtc",
      "salary",
      "portfolio",
      "github",
      "linkedin",
      "website",
      "noticePeriod",
      "referralSource",
      "coverLetter",
    ];

    for (const type of types) {
      let best = null;
      let bestScore = 0;

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

    const unmatched = standardInputs.filter((el) => !assigned.has(el));
    return { candidates, unmatched, customQuestions };
  }

  // ===== CUSTOM QUESTION FILLER =====
  function generateIntroduction(profile) {
    const raw = profile.raw_bio || "";
    const role = profile.current_role || "Developer";
    const years = profile.years_experience || "";
    const skills = profile.skills || "";

    const firstPara = raw.split("\n\n")[0];
    if (firstPara && firstPara.length > 100 && firstPara.length < 800) {
      return firstPara;
    }

    return `${profile.name} — ${role} with ${years}+ years shipping production systems. I've built platforms from scratch, handled zero-downtime deployments, and migrated legacy stacks. I work end-to-end and prefer shipping over meetings.`;
  }

  async function fillCustomQuestions(profile, customQuestions) {
    let filled = 0;

    for (const el of customQuestions) {
      const clues = getAllTextClues(el);
      const labelText = clues.join(" ");
      const lowerLabel = labelText.toLowerCase();

      let answer = "";
      let source = "unknown";

      // 1. INTRODUCTION / ABOUT YOURSELF
      if (
        /\b(introduction|about yourself|background|bio|tell me about|who are you|describe yourself)\b/i.test(
          lowerLabel,
        )
      ) {
        if (profile.custom_answers?.introduction) {
          answer = profile.custom_answers.introduction;
          source = "pre-canned";
        } else {
          answer = generateIntroduction(profile);
          source = "generated";
        }
      }
      // 2. SALARY (USD MONTHLY)
      else if (
        /\b(monthly salary|salary range.*usd|usd.*month|desired monthly|per month|monthly.*range)\b/i.test(
          lowerLabel,
        )
      ) {
        if (profile.expected_salary_usd_monthly) {
          answer = profile.expected_salary_usd_monthly;
          source = "pre-canned-usd-monthly";
        } else if (profile.expected_ctc) {
          answer = `I'm looking for a range of $1,800 - $2,400 per month, which aligns with my current experience level and the scope of this role.`;
          source = "converted-estimate";
        }
      }
      // 3. SALARY (USD YEARLY or generic)
      else if (
        /\b(salary|compensation|ctc|pay range|desired salary|expected.*salary)\b/i.test(
          lowerLabel,
        )
      ) {
        if (profile.expected_salary_usd_yearly) {
          answer = profile.expected_salary_usd_yearly;
          source = "pre-canned-usd-yearly";
        } else if (profile.expected_ctc) {
          answer = profile.expected_ctc;
          source = "pre-canned-inr";
        }
      }
      // 4. AVAILABILITY / NOTICE
      else if (
        /\b(availability|notice period|start date|joining|how soon|available from)\b/i.test(
          lowerLabel,
        )
      ) {
        const notice = profile.notice_period_weeks;
        if (notice === "0" || notice === 0 || notice === "Immediate") {
          answer = "I can start immediately.";
        } else {
          answer = `I have a ${notice}-week notice period with my current employer, so I can join after that.`;
        }
        source = "computed";
      }
      // 5. WHY THIS COMPANY / MOTIVATION
      else if (
        /\b(why.*company|why.*role|why.*apply|motivation|interest.*role|interest.*company|why do you want)\b/i.test(
          lowerLabel,
        )
      ) {
        if (profile.custom_answers?.motivation) {
          answer = profile.custom_answers.motivation;
          source = "pre-canned";
        } else {
          answer =
            "I'm looking for a team where I can own features end-to-end and work with modern stacks. This role seems to line up with what I've been building lately.";
          source = "generic";
        }
      }
      // 6. COVER LETTER / ADDITIONAL INFO
      else if (
        /\b(cover letter|additional info|anything else|supplement|message|additional information)\b/i.test(
          lowerLabel,
        )
      ) {
        if (profile.custom_answers?.cover_letter) {
          answer = profile.custom_answers.cover_letter;
          source = "pre-canned";
        } else {
          continue;
        }
      }
      // 7. GENERIC FALLBACK - LLM
      else {
        try {
          const result = await apiRequest("POST", `${SERVER}/answer-question`, {
            profile: profile,
            question: clues[0] || labelText,
            question_type: "general",
          });
          if (result && !result.error && result.answer) {
            answer = result.answer;
            source = "llm";
          }
        } catch (e) {
          console.error("[JobBot] LLM fallback failed:", e);
          continue;
        }
      }

      // Respect word count hints
      const wordMatch = labelText.match(/(\d+)\s*-\s*(\d+)\s*words?/i);
      if (wordMatch && answer.split(/\s+/).length < parseInt(wordMatch[1])) {
        if (source === "pre-canned" || source === "generated") {
          try {
            const result = await apiRequest("POST", `${SERVER}/expand-answer`, {
              answer: answer,
              target_words: parseInt(wordMatch[2]),
              question: labelText,
            });
            if (result?.answer) answer = result.answer;
          } catch (e) {}
        }
      }

      if (answer && setInputValue(el, answer)) {
        filled++;
        console.log(
          `[JobBot] Custom question (${source}): ${labelText.substring(0, 50)}...`,
        );
      }
    }

    return filled;
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

    const { candidates: fields, unmatched, customQuestions } = findBestInputs();
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

    console.log(
      `[JobBot] === Filled ${filled} standard fields: ${log.join(", ")} ===`,
    );

    if (customQuestions.length > 0) {
      fillCustomQuestions(profile, customQuestions).then((cf) => {
        console.log(`[JobBot] === Filled ${cf} custom questions ===`);
      });
    }

    return filled;
  }

  function pasteCoverLetter(text) {
    const { candidates: fields } = findBestInputs();
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
