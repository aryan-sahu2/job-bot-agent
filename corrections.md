On a Mac, Alt is the Option key (⌥) — so the shortcut is ⌥+J (Option+J).
However, on many Mac keyboard layouts Option+J types a special character (like ∆), so browsers often don't fire the shortcut cleanly. If ⌥+J doesn't work or types a symbol instead, swap the shortcut in your content.js to something Mac-native.
Replace this block in content.js:
JavaScript
document.addEventListener('keydown', e => {
    if (e.altKey && e.key === 'j') { e.preventDefault(); toggle(); }
});
With this Mac-friendly version (uses Cmd+Shift+K):
JavaScript
document.addEventListener('keydown', e => {
    // Cmd+Shift+K on Mac, Ctrl+Shift+K on Windows/Linux
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        toggle();
    }
});
Or if you prefer Ctrl+Shift+Space (rarely conflicts with anything):
JavaScript
document.addEventListener('keydown', e => {
    if (e.ctrlKey && e.shiftKey && e.key === ' ') {
        e.preventDefault();
        toggle();
    }
});
Tip: Since the JobBot panel also auto-appears on any URL containing apply, careers, jobs, posting, or application, you often don't need the keyboard shortcut at all — just open a job application page and the panel slides up after 1.5 seconds.