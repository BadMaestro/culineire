(function () {
  var details = document.querySelector('.mod-maintenance-details');
  if (details) {
    document.addEventListener('click', function (e) {
      if (details.open && !details.contains(e.target)) {
        details.open = false;
      }
    });
  }

  var countdown = document.querySelector('.mod-maintenance-countdown');
  if (countdown) {
    var until = new Date(countdown.dataset.until);
    function tick() {
      var diff = Math.max(0, Math.floor((until - Date.now()) / 1000));
      if (diff === 0) { countdown.textContent = 'ending soon'; return; }
      var h = Math.floor(diff / 3600);
      var m = Math.floor((diff % 3600) / 60);
      var s = diff % 60;
      countdown.textContent = (h ? h + 'h ' : '') + (m ? m + 'm ' : '') + s + 's';
      setTimeout(tick, 1000);
    }
    tick();
  }
})();
