/* ============================================================
   config.js — where the frontend finds the backend API.
   The backend runs on Hugging Face Spaces; local dev runs it
   on :8000. Edit STACKTRACE_API_BASE if your backend URL differs.
   Must load BEFORE auth.js.
   ============================================================ */
(function () {
  const isLocal =
    location.hostname === 'localhost' || location.hostname === '127.0.0.1';

  window.STACKTRACE_API_BASE = isLocal
    ? 'http://localhost:8000'                          // local backend
    : 'https://vivekreddy04-stacktrace-run.hf.space';  // Hugging Face Space
})();
