import os
"""AN28 — the ORIGINAL startup defect, reproduced under six load profiles.

The defect the Owner saw:

    Arena shell appears
    Rank Ladder appears in the CENTRE of the page
    Octagon is still absent
    Octagon loads
    Rank Ladder JUMPS to its final position

That is a RENDER-LIFECYCLE question, and the only way to answer it is to watch
the page from before its first paint. This builds six variants of the harness
page - the real arena DOM, the real stylesheets, the real renderer - each with
a different profile applied, and a parent page that iframes one of them and
samples every animation frame from t0.

The profiles stand in for the CDP knobs I cannot reach:

    A normal      as served
    B hard        every asset uniquely cache-busted
    C cold        as B, plus the renderer requested last
    D cpu         the main thread blocked in 120ms bursts for 1.5s from
                  DOMContentLoaded - this is what CPU throttling DOES to a
                  page, and it is deliberately more brutal than 4x
    E net         the renderer's <script> arrives 900ms late
    F cpu+net     both

D, E and F widen the exact window the defect lives in - the interval between
the shell being painted and the geometry being known. If a geometry-dependent
element can appear early, these are the conditions that show it.
"""
import io, os, re, sys

OUT = os.environ.get("ARENA_HARNESS_OUT",
       os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out"))

base = io.open(os.path.join(OUT, "b.html"), encoding="utf-8").read()

BLOCK = """
<script>
(function(){
  var until = 0;
  function burn(){
    var t = performance.now();
    while (performance.now() - t < 120) { Math.sqrt(t); }
    if (performance.now() < until) { setTimeout(burn, 0); }
  }
  document.addEventListener('DOMContentLoaded', function(){
    until = performance.now() + 1500;
    burn();
  });
}());
</script>
"""


def variant(name, bust=False, delay_renderer=0, cpu=False):
    html = base
    if bust:
        html = re.sub(r'(localhost:8765/[^"?]+)\?v=\d+',
                      lambda m: m.group(1) + "?v=" + name + str(os.getpid()), html)
    if delay_renderer:
        # take the renderer out of the parser's hands and append it late
        m = re.search(r'<script[^>]+src="([^"]*arena_render[^"]*)"[^>]*></script>', html)
        if not m:
            sys.exit("renderer script tag not found")
        src = m.group(1)
        html = html.replace(m.group(0), "")
        html = html.replace("</body>", """
<script>
setTimeout(function(){
  var s = document.createElement('script');
  s.src = %r;
  document.body.appendChild(s);
}, %d);
</script>
</body>""" % (src, delay_renderer), 1)
    if cpu:
        html = html.replace("</head>", BLOCK + "</head>", 1)
    path = os.path.join(OUT, "an28_%s.html" % name)
    io.open(path, "w", encoding="utf-8").write(html)
    return os.path.basename(path)


PROFILES = [
    ("a_normal", dict()),
    ("b_hard", dict(bust=True)),
    ("c_cold", dict(bust=True, delay_renderer=250)),
    ("d_cpu", dict(cpu=True)),
    ("e_net", dict(delay_renderer=900)),
    ("f_both", dict(cpu=True, delay_renderer=900)),
]

names = [variant(n, **kw) for n, kw in PROFILES]

OBSERVER = """<!doctype html>
<meta charset="utf-8">
<title>AN28 rig</title>
<style>html,body{margin:0}iframe{border:0;width:1280px;height:800px;display:block}</style>
<script>
window.__AN28 = null;
function run(page){
  window.__AN28 = null;
  var old = document.querySelector('iframe');
  if (old) { old.remove(); }
  var f = document.createElement('iframe');
  var t0 = performance.now();
  var seen = { shell:null, octagon:null, ladder:null, ready:null };
  var first = { ladder:null, octagon:null };
  var last  = { ladder:null, octagon:null };
  var jumps = { ladder:0, octagon:0 };
  var states = [];
  var frames = 0;

  function box(el){
    if (!el) { return null; }
    var r = el.getBoundingClientRect();
    if (!(r.width > 0) || !(r.height > 0)) { return null; }
    var s = f.contentWindow.getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || parseFloat(s.opacity) === 0) {
      return null;
    }
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)];
  }
  function same(a,b){ return a&&b&&a[0]===b[0]&&a[1]===b[1]&&a[2]===b[2]&&a[3]===b[3]; }

  function sample(){
    frames++;
    var d = f.contentDocument;
    if (d) {
      var t = performance.now() - t0;
      var shell = d.querySelector('.arena-command-deck');
      var svg = d.getElementById('arena-render');
      var spine = d.querySelector('.arena-rank-spine');
      var st = d.documentElement.getAttribute('data-arena-state')
            || (d.body && d.body.getAttribute('data-arena-state'));
      if (st && (!states.length || states[states.length-1][0] !== st)) { states.push([st, +t.toFixed(1)]); }
      if (!seen.shell && box(shell)) { seen.shell = +t.toFixed(1); }
      var ob = svg && svg.querySelector('.arena-cell') ? box(svg) : null;
      if (ob) {
        if (!seen.octagon) { seen.octagon = +t.toFixed(1); first.octagon = ob; }
        if (last.octagon && !same(last.octagon, ob)) { jumps.octagon++; }
        last.octagon = ob;
      }
      var lb = box(spine);
      if (lb) {
        if (!seen.ladder) { seen.ladder = +t.toFixed(1); first.ladder = lb; }
        if (last.ladder && !same(last.ladder, lb)) { jumps.ladder++; }
        last.ladder = lb;
      }
    }
    if (performance.now() - t0 < 5000) { requestAnimationFrame(sample); }
    else {
      window.__AN28 = { page:page, frames:frames, firstVisible:seen, states:states,
                        ladder:{ atFirst:first.ladder, stable:last.ladder, changes:jumps.ladder },
                        octagon:{ atFirst:first.octagon, stable:last.octagon, changes:jumps.octagon } };
    }
  }
  f.src = page;
  document.body.appendChild(f);
  requestAnimationFrame(sample);
  return 'running ' + page;
}
</script>
<body></body>
"""
io.open(os.path.join(OUT, "an28_rig.html"), "w", encoding="utf-8").write(OBSERVER)
print("built:", ", ".join(names))
