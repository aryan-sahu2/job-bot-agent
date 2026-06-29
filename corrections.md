The Real Problems
1. The Screen Module is Built on a Broken Foundation
The screen/ module relies entirely on macOS Accessibility APIs (ApplicationServices framework). This approach fails for modern web browsers because:
Browsers don't expose web form elements via Accessibility APIs — Chromium, Safari, and Firefox all use their own rendering engines that don't map DOM elements to native AX elements for standard web forms. You get the window title, maybe some toolbar buttons, but not the actual <input> fields inside the page.
The get_all_text() method in reader.py only reads AXStaticText/AXTextField/AXTextArea roles — modern job sites (LinkedIn, Greenhouse, Lever, Workday) render forms inside complex shadow DOM structures that are invisible to AX APIs.
The _max_depth=15 limit means it can't reach deep into nested web components even if some text were accessible.
Evidence from the code:
Python
# reader.py — this is all it can "see"
if role in ("AXStaticText", "AXTextField", "AXTextArea"):
    if value and str(value).strip():
        texts.append(str(value).strip())
This explains why you only get "the title, not the complete description."
2. The Browser Engine Uses domcontentloaded — Too Early
Python
# engine.py
await page.goto(url, timeout=self._config.timeout, wait_until="domcontentloaded")
domcontentloaded fires when the HTML is parsed, not when JavaScript has rendered the actual form. Modern job sites are SPAs (Single Page Applications) that fetch job data via XHR/fetch after the initial load. The selectors like .base-card (LinkedIn) or .posting (Lever) often don't exist yet when domcontentloaded fires.
3. No Anti-Detection Actually Works
The "stealth" script in engine.py is naive:
Python
Object.defineProperty(navigator, 'webdriver', { get: () => false });
Modern bot detection (DataDome, Cloudflare, PerimeterX, LinkedIn's own systems) checks:
Runtime behavior (mouse movement patterns, keystroke timing)
Webdriver property consistency across iframes and workers
Chrome DevTools Protocol detection (Playwright leaks this)
TLS fingerprinting
Browser feature consistency (your plugins array is fake and detectable)
The STEALTH_SCRIPT doesn't patch navigator.webdriver in workers, doesn't fix the chrome.csi inconsistency, and doesn't handle the fact that Playwright's injected scripts leave traces in Error.stack.
4. The Screen Form Filler Can't Actually Fill Web Forms
Python
# form_filler.py
def _fill_text_field(self, field: DetectedField, value: str) -> bool:
    if self._reader.click_element(element):
        time.sleep(0.15)
        self._reader.type_text(value)
        return True
Even if it detected a field (which it can't), type_text() uses CGEventKeyboardSetUnicodeString which sends events at machine speed — no human types 60 WPM with perfectly uniform 16ms intervals. Bot detection systems flag this immediately.
More critically, the accessibility tree doesn't give you the screen coordinates of web form elements reliably. The AXPosition attribute often returns (0, 0) or viewport-relative coordinates that don't account for scroll position, CSS transforms, or iframes.
5. The "Apply Button" Detection is Theoretically Broken
Python
# button_finder.py
def _get_element_text(self, element: Any) -> str:
    parts = [
        str(self._reader.get_attribute(element, "AXTitle") or ""),
        str(self._reader.get_attribute(element, "AXDescription") or ""),
        str(self._reader.get_attribute(element, "AXValue") or ""),
    ]
Web buttons rendered with <button>Apply Now</button> don't expose their text content via AXTitle — they expose it via AXValue or child AXStaticText elements. The code checks children, but the _is_match logic is fragile:
Python
def _is_match(self, element: Any, text: str | None = None, keywords: list[str] | None = None) -> bool:
    if any(skip in text for skip in SKIP_KEYWORDS):
        return False
    if any(keyword in text for keyword in keywords):
        return True
This means a button labeled "Apply Now (Skip this step)" would be skipped because "skip" is in SKIP_KEYWORDS, even though "apply" is also present.
6. The Form Detector Only Knows 7 Role Types
Python
ROLE_FIELD_MAP = {
    "AXTextField": FieldType.TEXT,
    "AXTextArea": FieldType.TEXTAREA,
    "AXComboBox": FieldType.SELECT,
    "AXPopUpButton": FieldType.SELECT,
    "AXCheckBox": FieldType.CHECKBOX,
    "AXRadioButton": FieldType.RADIO,
    "AXSlider": FieldType.TEXT,
}
Modern job forms use:
Custom dropdowns (div-based, not native <select>)
Rich text editors (contenteditable divs)
File drop zones (not AXTextField)
Date pickers (custom widgets, not AXTextField)
Multi-select chips
Radio groups implemented as styled divs
None of these map to AX roles. The detector will see zero fields on a typical Greenhouse or Lever application form.
7. The Answer Generator Has No Context About the Actual Form
Python
# workflow.py
custom_fields = [
    f for f in (fields or [])
    if f.field_type in (FieldType.TEXTAREA, FieldType.TEXT)
    and (f.title.strip() or f.description.strip())
]
Since fields is usually empty (see #6), custom_fields is empty, so it falls back to generating a generic cover letter and stuffing it into answers["cover_letter"]. But there's no field mapping for "cover_letter" in STANDARD_FIELD_PATTERNS:
Python
STANDARD_FIELD_PATTERNS = {
    "first_name": ["first name", ...],
    "last_name": ["last name", ...],
    "email": ["email", ...],
    # ... no "cover_letter" key
}
So the generated cover letter is never actually placed into any field.
8. The Tests Are Mock-Based and Don't Test Reality
The tests mock ApplicationServices and Quartz frameworks:
Python
# (implied from test structure)
# test_screen_reader.py likely does:
mock_ax_element = MagicMock()
reader.get_attribute(mock_ax_element, "AXTitle")  # returns mock value
This proves the Python logic works with fake data, but doesn't validate that the actual macOS APIs return meaningful data from real browsers. 209 passing tests against mocks don't mean it works against LinkedIn's DOM.
Why the AI Assessment Was Wrong
The AI said "the codebase is very functional with no critical errors" because:
It only checked static analysis — ruff linting, import resolution, test execution
It didn't verify against real websites — no integration tests with actual job boards
It confused "code compiles" with "code works" — the architecture is fundamentally mismatched to the problem
It didn't understand the Accessibility API limitations — this is domain knowledge about how browsers work, not something visible in the code structure
What Would Actually Be Needed
To make this work, you'd need to fundamentally change the approach:
Table
Current Approach	What Actually Works
macOS Accessibility APIs	Playwright/CDP with real DOM access — query selectors, fill inputs, click buttons using browser-native APIs
domcontentloaded wait	networkidle or specific element waits — wait for the actual form to render
Basic stealth script	Playwright-stealth or puppeteer-extra-stealth with proper evasion patches, or use undetected-playwright
AX-based form detection	DOM-based detection — query all <input>, <textarea>, <select>, [contenteditable], custom dropdowns by their ARIA roles and labels
CGEvent typing	page.type() with realistic delay and human-like keystroke patterns
OCR fallback for buttons	Vision-based detection using screenshot + element detection (e.g., GPT-4V, or trained CV models) for cases where DOM selectors fail
Generic cover letter	Per-question answering using the actual label text of each detected field as the prompt
The Honest Verdict
This codebase represents a well-structured learning project that demonstrates good software engineering practices (modularity, testing, configuration), but it's architecturally incapable of performing its stated goal.
The screen-based approach via Accessibility APIs was a fundamental misstep. You'd need to either:
Pivot to full browser automation (Playwright controlling the page directly with proper selectors), or
Use computer-vision + LLM approaches (screenshot the page, have an AI identify fields and generate actions)
Neither approach is a small refactor — both require essentially rebuilding the core interaction layer. The weekend wasn't wasted on implementation details; it was spent on an approach that can't work due to how modern browsers and web applications are architected.
The 11 uncommitted files mentioned ("better label detection for form fields, improved form filling strategies") are likely attempts to patch around these fundamental limitations, which is why they're "incomplete but don't break anything" — you can't patch a broken foundation.