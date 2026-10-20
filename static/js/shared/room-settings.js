/* Owner-only retention settings. Dates are calculated by the server. */
(function (document) {
  'use strict';

  function bind(form) {
    var select = form.querySelector('[name="retention_hours"]');
    var preview = form.querySelector('[data-room-settings-preview]');
    var error = form.querySelector('[data-room-settings-error]');
    var status = form.querySelector('[data-room-settings-status]');
    var button = form.querySelector('button[type="submit"]');
    var pending = false;
    function updatePreview() {
      preview.textContent = select.selectedOptions[0].dataset.deletionDate;
    }
    select.addEventListener('change', updatePreview);
    updatePreview();
    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      if (pending) return;
      pending = true;
      error.hidden = true;
      status.textContent = '';
      var body = new FormData(form);
      // The enhanced select's trigger is a separate button; lock it with the native select.
      var trigger = form.querySelector('.retention-select-trigger');
      button.disabled = true;
      select.disabled = true;
      if (trigger) trigger.disabled = true;
      button.setAttribute('aria-busy', 'true');
      var errorMessage = form.dataset.errorMessage;
      try {
        var response = await fetch(form.action, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' },
          body: body
        });
        var payload = await response.json();
        if (!response.ok || !payload.data || !payload.data.deletion_date) {
          errorMessage = payload && payload.error || errorMessage;
          throw new Error(errorMessage);
        }
        document.querySelectorAll('[data-room-deletion-date]').forEach(function (output) {
          output.textContent = payload.data.deletion_date;
        });
        status.textContent = form.dataset.successMessage;
      } catch (_failure) {
        error.textContent = errorMessage;
        error.hidden = false;
      } finally {
        pending = false;
        button.disabled = false;
        select.disabled = false;
        if (trigger) trigger.disabled = false;
        button.setAttribute('aria-busy', 'false');
      }
    });
  }
  document.querySelectorAll('form[data-room-settings]').forEach(bind);
})(document);
