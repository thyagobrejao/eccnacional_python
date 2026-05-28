document.addEventListener('DOMContentLoaded', function () {
  var controls = document.querySelectorAll('.field-shell .auth-input');

  function syncState(input) {
    var shell = input.closest('.field-shell');
    if (!shell) {
      return;
    }

    shell.classList.toggle('is-filled', Boolean(input.value));
  }

  controls.forEach(function (input) {
    syncState(input);
    input.addEventListener('input', function () {
      syncState(input);
    });
    input.addEventListener('blur', function () {
      syncState(input);
    });
  });
});