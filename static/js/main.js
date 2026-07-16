/**
 * main.js — AI Interview Coach
 * Landing page logic: theme toggle, setup modal, form validation, API calls,
 * navigation helpers, particle generation.
 *
 * All functions are exposed on the global scope because index.html calls them
 * via inline onclick attributes.
 */

'use strict';

/* ─────────────────────────────────────────────────────────────────────────────
   THEME
   ───────────────────────────────────────────────────────────────────────── */

/**
 * Read the stored preference (defaulting to "dark") and apply it immediately
 * so there is no flash of the wrong theme while the page loads.
 */
(function applyStoredTheme() {
  const stored = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', stored);
  // The toggle button may not exist yet if this IIFE runs before DOMContentLoaded,
  // so we guard with a deferred update handled in the DOMContentLoaded block.
})();

/**
 * Toggle between dark and light mode, persist the choice, and update the
 * moon/sun icon on the nav button.
 */
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next    = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  syncThemeIcon(next);
}

/** Update the toggle button emoji to match the current theme. */
function syncThemeIcon(theme) {
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = theme === 'dark' ? '🌙' : '☀️';
}

/* ─────────────────────────────────────────────────────────────────────────────
   NAVIGATION HELPERS
   ───────────────────────────────────────────────────────────────────────── */

/**
 * Smooth-scroll to a section identified by its element ID.
 * Used by the nav buttons (Features, About, etc.).
 *
 * @param {string} id - The element ID to scroll to.
 */
function scrollTo(id) {
  const target = document.getElementById(id);
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

/* ─────────────────────────────────────────────────────────────────────────────
   CATEGORY & ROLES MAPPING
   ───────────────────────────────────────────────────────────────────────── */

const CATEGORY_ROLES = {
  "Engineering": [
    "Computer Science",
    "Information Technology",
    "Artificial Intelligence",
    "Data Science",
    "Cyber Security",
    "Electronics and Communication",
    "Electrical Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
    "Chemical Engineering",
    "Aerospace Engineering",
    "Automobile Engineering",
    "Biomedical Engineering",
    "Mechatronics Engineering"
  ],
  "Business": [
    "MBA",
    "Finance",
    "Marketing",
    "Human Resources",
    "Business Analyst",
    "Operations"
  ],
  "Healthcare": [
    "Doctor",
    "Nurse",
    "Pharmacist",
    "Physiotherapist",
    "Medical Laboratory",
    "Healthcare Administration"
  ],
  "Government": [
    "UPSC",
    "SSC",
    "Banking",
    "Railway",
    "Defence",
    "Police"
  ],
  "Design & Creative": [
    "UI/UX Designer",
    "Graphic Designer",
    "Interior Designer",
    "Fashion Designer"
  ],
  "Education": [
    "School Teacher",
    "College Lecturer",
    "Assistant Professor"
  ],
  "Others": [
    "Sales",
    "Customer Support",
    "Digital Marketing",
    "Content Writer",
    "Hotel Management",
    "Aviation",
    "Logistics",
    "Supply Chain",
    "Agriculture",
    "Architecture"
  ]
};

function onCategoryChange() {
  const categorySelect = document.getElementById('setupCategory');
  const roleSelect = document.getElementById('setupRole');
  if (!categorySelect || !roleSelect) return;

  const category = categorySelect.value;
  roleSelect.innerHTML = '';

  if (!category) {
    roleSelect.disabled = true;
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'Select a category first…';
    roleSelect.appendChild(opt);
    return;
  }

  roleSelect.disabled = false;
  const defOpt = document.createElement('option');
  defOpt.value = '';
  defOpt.textContent = 'Select a role…';
  roleSelect.appendChild(defOpt);

  const roles = CATEGORY_ROLES[category] || [];
  roles.forEach(role => {
    const opt = document.createElement('option');
    opt.value = role;
    opt.textContent = role;
    roleSelect.appendChild(opt);
  });
}

/* ─────────────────────────────────────────────────────────────────────────────
   SETUP MODAL
   ───────────────────────────────────────────────────────────────────────── */

/** Open the interview setup modal and focus the first field. */
function openSetupModal() {
  const overlay = document.getElementById('setupModal');
  if (!overlay) return;
  overlay.classList.add('active');
  clearSetupError();
  // Small delay so the CSS transition is visible before we try to focus.
  setTimeout(() => {
    const nameField = document.getElementById('setupName');
    if (nameField) nameField.focus();
  }, 60);
}

/** Close the interview setup modal and reset the start button. */
function closeSetupModal() {
  const overlay = document.getElementById('setupModal');
  if (!overlay) return;
  overlay.classList.remove('active');
  resetStartButton();
}

/** Show a validation or API error message inside the modal. */
function showSetupError(msg) {
  const el = document.getElementById('setupError');
  if (!el) return;
  el.textContent = msg;
  el.style.display = 'block';
}

/** Hide the error message inside the modal. */
function clearSetupError() {
  const el = document.getElementById('setupError');
  if (!el) return;
  el.textContent = '';
  el.style.display = 'none';
}

/** Reset the start button to its default state. */
function resetStartButton() {
  const btn = document.getElementById('startBtn');
  if (!btn) return;
  btn.disabled  = false;
  btn.innerHTML = 'Start Interview →';
}

/* ─────────────────────────────────────────────────────────────────────────────
   FORM VALIDATION
   ───────────────────────────────────────────────────────────────────────── */

/**
 * Validate the setup form fields.
 * Returns { valid: boolean, error: string|null }.
 */
function validateSetupForm(name, email, category, role, exp) {
  if (!name) return { valid: false, error: 'Please enter your full name.' };
  if (name.length < 2) return { valid: false, error: 'Name must be at least 2 characters.' };

  if (!email) return { valid: false, error: 'Please enter your email address.' };
  const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRe.test(email)) return { valid: false, error: 'Please enter a valid email address.' };

  if (!category) return { valid: false, error: 'Please select a category.' };
  if (!role) return { valid: false, error: 'Please select a job role.' };
  if (!exp)  return { valid: false, error: 'Please select an experience level.' };

  return { valid: true, error: null };
}

/* ─────────────────────────────────────────────────────────────────────────────
   API — START INTERVIEW
   ───────────────────────────────────────────────────────────────────────── */

/**
 * Read the form, validate it, POST to /api/start_interview, then redirect
 * to the interview page with the returned interview ID.
 * Called from the modal's Start button (onclick="startInterview()").
 */
async function startInterview() {
  clearSetupError();

  const name  = (document.getElementById('setupName')?.value  || '').trim();
  const email = (document.getElementById('setupEmail')?.value || '').trim();
  const category = document.getElementById('setupCategory')?.value || '';
  const role  = document.getElementById('setupRole')?.value   || '';
  const exp   = document.getElementById('setupExp')?.value    || '';

  const { valid, error } = validateSetupForm(name, email, category, role, exp);
  if (!valid) {
    showSetupError(error);
    return;
  }

  // Switch the button to a loading state.
  const btn = document.getElementById('startBtn');
  if (btn) {
    btn.disabled  = true;
    btn.innerHTML = '<span class="loader"></span> Setting up…';
  }

  try {
    const response = await fetch('/api/start_interview', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        name,
        email,
        category,
        job_role:         role,
        experience_level: exp
      })
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      showSetupError(err.error || `Server error (${response.status}). Please try again.`);
      resetStartButton();
      return;
    }

    const data = await response.json();

    if (!data.interview_id) {
      showSetupError(data.error || 'Failed to start interview. Please try again.');
      resetStartButton();
      return;
    }

    // Persist candidate metadata so the interview page can display it without
    // an extra API call.
    sessionStorage.setItem('interview_meta', JSON.stringify({ name, category, role, exp }));

    // Navigate to the interview page.
    window.location.href = `/interview?id=${data.interview_id}`;

  } catch (networkErr) {
    console.error('[main.js] startInterview network error:', networkErr);
    showSetupError('Network error — is the Flask server running on port 5000?');
    resetStartButton();
  }
}

/* ─────────────────────────────────────────────────────────────────────────────
   PARTICLES
   ───────────────────────────────────────────────────────────────────────── */

/**
 * Generate decorative floating particles in the hero section.
 * The container element must have id="particles".
 */
function spawnParticles() {
  const container = document.getElementById('particles');
  if (!container) return;

  const count = 22;
  for (let i = 0; i < count; i++) {
    const p    = document.createElement('div');
    p.className = 'particle';
    const size  = Math.random() * 8 + 2;
    const delay = Math.random() * 8;
    const dur   = Math.random() * 10 + 6;
    const left  = Math.random() * 100;
    const top   = Math.random() * 100;

    p.style.cssText = [
      `width:${size}px`,
      `height:${size}px`,
      `left:${left}%`,
      `top:${top}%`,
      `animation-duration:${dur}s`,
      `animation-delay:${delay}s`,
    ].join(';');

    container.appendChild(p);
  }
}

/* ─────────────────────────────────────────────────────────────────────────────
   KEYBOARD SHORTCUTS
   ───────────────────────────────────────────────────────────────────────── */

/**
 * Allow pressing Enter inside the setup modal to trigger the Start button,
 * and Escape to close the modal.
 */
function initModalKeyboard() {
  document.addEventListener('keydown', (e) => {
    const overlay = document.getElementById('setupModal');
    if (!overlay) return;
    const isOpen = overlay.classList.contains('active');

    if (isOpen && e.key === 'Escape') {
      closeSetupModal();
    }
    if (isOpen && e.key === 'Enter' && e.target.tagName !== 'SELECT') {
      startInterview();
    }
  });
}

/**
 * Close the modal when the user clicks on the translucent overlay backdrop
 * (i.e. outside the white modal card).
 */
function initModalBackdropClose() {
  const overlay = document.getElementById('setupModal');
  if (!overlay) return;
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeSetupModal();
  });
}

/* ─────────────────────────────────────────────────────────────────────────────
   FOOTER YEAR
   ───────────────────────────────────────────────────────────────────────── */

function setFooterYear() {
  const el = document.getElementById('year');
  if (el) el.textContent = new Date().getFullYear();
}

/* ─────────────────────────────────────────────────────────────────────────────
   ACTIVE NAV HIGHLIGHT (scroll-spy)
   ───────────────────────────────────────────────────────────────────────── */

/**
 * Light scroll-spy: highlight the correct nav link as the user scrolls through
 * section anchors (features, about, how).
 */
function initScrollSpy() {
  const sections = ['features', 'how', 'about'];
  const navBtns  = document.querySelectorAll('.nav-btn[data-section]');
  if (!navBtns.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        navBtns.forEach((btn) => {
          const active = btn.dataset.section === entry.target.id;
          btn.classList.toggle('active-nav', active);
        });
      });
    },
    { threshold: 0.4 }
  );

  sections.forEach((id) => {
    const el = document.getElementById(id);
    if (el) observer.observe(el);
  });
}

/* ─────────────────────────────────────────────────────────────────────────────
   ROLE PILL CLICK — pre-fill the modal's role selector
   ───────────────────────────────────────────────────────────────────────── */

/**
 * When a user clicks a role pill in the "Supported Job Roles" section, open
 * the setup modal with that role pre-selected.
 */
function initRolePillClicks() {
  document.querySelectorAll('.role-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      // Strip the emoji prefix
      const raw  = pill.textContent.trim();
      const role = raw.replace(/^\S+\s/, '');

      let foundCategory = '';
      for (const [cat, roles] of Object.entries(CATEGORY_ROLES)) {
        if (roles.some(r => r.toLowerCase() === role.toLowerCase())) {
          foundCategory = cat;
          break;
        }
      }

      if (foundCategory) {
        const categorySelect = document.getElementById('setupCategory');
        if (categorySelect) {
          categorySelect.value = foundCategory;
          onCategoryChange();
          const roleSelect = document.getElementById('setupRole');
          if (roleSelect) {
            const opt = Array.from(roleSelect.options).find(
              (o) => o.value.toLowerCase() === role.toLowerCase()
            );
            if (opt) roleSelect.value = opt.value;
          }
        }
      }
      openSetupModal();
    });
  });
}

/* ─────────────────────────────────────────────────────────────────────────────
   HERO MOCKUP — animated score count-up
   ───────────────────────────────────────────────────────────────────────── */

/**
 * Animate the numbers inside the mockup preview card from 0 up to their target
 * values, creating a pleasing count-up effect when the page loads.
 */
function animateMockupScores() {
  const targets = document.querySelectorAll('.ms-val');
  targets.forEach((el) => {
    const target = parseFloat(el.textContent);
    if (isNaN(target)) return;
    let current  = 0;
    const step   = target / 40; // 40 frames
    const tick   = setInterval(() => {
      current += step;
      if (current >= target) {
        current = target;
        clearInterval(tick);
      }
      el.textContent = current.toFixed(1);
    }, 30);
  });
}

/* ─────────────────────────────────────────────────────────────────────────────
   STAT CARD COUNT-UP
   ───────────────────────────────────────────────────────────────────────── */

/**
 * Animate the hero stat cards (10K+, 94%, etc.) when they scroll into view.
 */
function initStatCountUp() {
  const cards = document.querySelectorAll('.stat-card .val');

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        observer.unobserve(entry.target);
        const el  = entry.target;
        const raw = el.textContent; // e.g. "10K+", "94%", "4.9★"

        // Extract the numeric part, animate it, then restore the suffix.
        const numMatch = raw.match(/[\d.]+/);
        if (!numMatch) return;

        const target   = parseFloat(numMatch[0]);
        const suffix   = raw.replace(/[\d.]+/, '');
        let   current  = 0;
        const frames   = 50;
        const step     = target / frames;

        const tick = setInterval(() => {
          current += step;
          if (current >= target) {
            current = target;
            clearInterval(tick);
          }
          // Keep original formatting (integer vs one decimal place).
          const display = Number.isInteger(target)
            ? Math.round(current)
            : current.toFixed(1);
          el.textContent = display + suffix;
        }, 25);
      });
    },
    { threshold: 0.8 }
  );

  cards.forEach((card) => observer.observe(card));
}

/* ─────────────────────────────────────────────────────────────────────────────
   TOAST NOTIFICATIONS (utility, used across pages)
   ───────────────────────────────────────────────────────────────────────── */

/**
 * Show a small toast notification at the bottom-right corner of the screen.
 *
 * @param {string}  message - Text to display.
 * @param {'info'|'success'|'error'} [type='info']
 * @param {number}  [duration=3500] - Milliseconds before auto-dismiss.
 */
function showToast(message, type = 'info', duration = 3500) {
  // Create a container the first time it's needed.
  let container = document.getElementById('toast-container');
  if (!container) {
    container           = document.createElement('div');
    container.id        = 'toast-container';
    container.style.cssText = [
      'position:fixed',
      'bottom:1.5rem',
      'right:1.5rem',
      'z-index:9999',
      'display:flex',
      'flex-direction:column',
      'gap:0.5rem',
      'pointer-events:none',
    ].join(';');
    document.body.appendChild(container);
  }

  const colorMap = {
    info:    'var(--accent)',
    success: 'var(--success)',
    error:   'var(--danger)',
  };
  const iconMap = { info: 'ℹ️', success: '✅', error: '❌' };

  const toast           = document.createElement('div');
  toast.style.cssText   = [
    'background:var(--card)',
    'border:1px solid var(--border)',
    'border-left:3px solid ' + (colorMap[type] || colorMap.info),
    'border-radius:10px',
    'padding:0.75rem 1.1rem',
    'font-size:0.85rem',
    'color:var(--text)',
    'box-shadow:0 4px 20px rgba(0,0,0,0.3)',
    'pointer-events:auto',
    'opacity:0',
    'transform:translateX(20px)',
    'transition:opacity 0.25s,transform 0.25s',
    'max-width:320px',
    'display:flex',
    'align-items:center',
    'gap:0.5rem',
  ].join(';');
  toast.innerHTML = `<span>${iconMap[type] || ''}</span><span>${message}</span>`;
  container.appendChild(toast);

  // Trigger enter animation.
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      toast.style.opacity   = '1';
      toast.style.transform = 'translateX(0)';
    });
  });

  // Auto-dismiss.
  setTimeout(() => {
    toast.style.opacity   = '0';
    toast.style.transform = 'translateX(20px)';
    setTimeout(() => toast.remove(), 280);
  }, duration);
}

/* ─────────────────────────────────────────────────────────────────────────────
   UTILITY — expose on window for use in other modules
   ───────────────────────────────────────────────────────────────────────── */

/** Simple HTML entity escaper to prevent XSS when injecting user input. */
function escHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

/** Format seconds as MM:SS. */
function fmtTime(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/* ─────────────────────────────────────────────────────────────────────────────
   BOOT
   ───────────────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  // Sync the theme icon now that the DOM is ready.
  const theme = localStorage.getItem('theme') || 'dark';
  syncThemeIcon(theme);

  // Footer year.
  setFooterYear();

  // Particles (only on landing page).
  spawnParticles();

  // Modal keyboard & backdrop interactions.
  initModalKeyboard();
  initModalBackdropClose();

  // Role pill click-to-prefill.
  initRolePillClicks();

  // Scroll-spy (no-op if no [data-section] nav buttons present).
  initScrollSpy();

  // Count-up animations.
  animateMockupScores();
  initStatCountUp();
});

/* ─────────────────────────────────────────────────────────────────────────────
   GLOBAL EXPORTS
   Functions are already global because this file is not wrapped in a module.
   Explicitly listing them here for documentation.

   toggleTheme()       — called by #themeToggle onclick
   scrollTo(id)        — called by nav button onclicks
   openSetupModal()    — called by "Start Interview" buttons
   closeSetupModal()   — called by modal Cancel button
   startInterview()    — called by modal Start button
   showToast(msg,type) — utility, callable from other scripts
   escHtml(str)        — utility
   fmtTime(secs)       — utility
   ───────────────────────────────────────────────────────────────────────── */
