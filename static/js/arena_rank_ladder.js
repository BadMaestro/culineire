/* Kitchen ranks — compact ladder, tap-to-expand into one shared panel.
 *
 * Owner's redesign, 2026-08-21: the old markup used native <details> per
 * row, no JS at all. The new 4x2 grid of tiles shares ONE detail panel
 * below the grid (server-rendered with all eight rank groups, only one
 * visible at a time) rather than eight independent panels, so this is the
 * one bit of JS that owns showing/hiding it. Re-tapping the open tile
 * collapses the panel; tapping another tile switches it without closing
 * first.
 */
(function () {
  "use strict";

  function init() {
    var grid = document.querySelector(".arena-rank-ladder__grid");
    var panel = document.getElementById("arena-rank-panel");
    if (!grid || !panel) return;

    var tiles = grid.querySelectorAll(".arena-rank-tile");
    var groups = panel.querySelectorAll(".arena-rank-panel__group");

    function collapse() {
      panel.hidden = true;
      for (var i = 0; i < tiles.length; i++) {
        tiles[i].setAttribute("aria-expanded", "false");
        tiles[i].classList.remove("arena-rank-tile--active");
      }
      for (var j = 0; j < groups.length; j++) {
        groups[j].hidden = true;
      }
    }

    function expand(ring, tile) {
      panel.hidden = false;
      for (var i = 0; i < tiles.length; i++) {
        var active = tiles[i] === tile;
        tiles[i].setAttribute("aria-expanded", active ? "true" : "false");
        tiles[i].classList.toggle("arena-rank-tile--active", active);
      }
      for (var j = 0; j < groups.length; j++) {
        groups[j].hidden = groups[j].getAttribute("data-ring") !== ring;
      }
    }

    grid.addEventListener("click", function (event) {
      var tile = event.target.closest(".arena-rank-tile");
      if (!tile || !grid.contains(tile)) return;
      var ring = tile.getAttribute("data-ring");
      var wasActive = tile.classList.contains("arena-rank-tile--active");
      if (wasActive) {
        collapse();
      } else {
        expand(ring, tile);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
