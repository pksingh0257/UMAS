(function () {
  const root = document.documentElement;
  const saved = localStorage.getItem('uams-theme') || 'dark';
  root.setAttribute('data-theme', saved);

  function updateLabel(theme) {
    const btn = document.getElementById('theme-toggle-btn');
    if (btn) btn.textContent = theme === 'light' ? 'Dark Mode' : 'Light Mode';
  }

  window.addEventListener('DOMContentLoaded', function () {
    updateLabel(saved);
    const btn = document.getElementById('theme-toggle-btn');
    if (btn) {
      btn.addEventListener('click', function () {
        const current = root.getAttribute('data-theme');
        const next = current === 'light' ? 'dark' : 'light';
        root.setAttribute('data-theme', next);
        localStorage.setItem('uams-theme', next);
        updateLabel(next);
      });
    }

    const toggleBtn = document.getElementById('pw-toggle');
    const pwField = document.getElementById('password');
    if (toggleBtn && pwField) {
      toggleBtn.addEventListener('click', function () {
        pwField.type = pwField.type === 'password' ? 'text' : 'password';
      });
    }
  });
})();