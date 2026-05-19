(function () {
    'use strict';

    function getTurnstileResponse(form) {
        var input = form.querySelector('input[name="cf-turnstile-response"]');
        return input ? input.value.trim() : null;
    }

    function isFormReady(form) {
        if (!form.checkValidity()) return false;
        if (form.querySelector('.cf-turnstile')) {
            var resp = getTurnstileResponse(form);
            if (resp === null || resp === '') return false;
        }
        return true;
    }

    function updateButton(form) {
        var btn = form.querySelector('button[type="submit"]');
        if (!btn || !form.classList.contains('form--touched')) return;
        var ready = isFormReady(form);
        btn.classList.toggle('btn--ready', ready);
        btn.classList.toggle('btn--not-ready', !ready);
    }

    function onInteract(form) {
        form.classList.add('form--touched');
        updateButton(form);
    }

    document.querySelectorAll('form[data-validate]').forEach(function (form) {
        form.addEventListener('input', function () { onInteract(form); });
        form.addEventListener('change', function () { onInteract(form); });

        if (form.querySelector('.cf-turnstile')) {
            var poll = setInterval(function () {
                var resp = getTurnstileResponse(form);
                if (resp !== null && resp !== '') {
                    clearInterval(poll);
                    onInteract(form);
                }
            }, 300);
        }
    });
}());
