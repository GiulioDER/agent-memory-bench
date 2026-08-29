/* Theme switch. The pre-paint snippet in each page's head has already stamped
   data-theme on <html>; this wires the masthead button and persists the choice. */

(function () {
  var btn = document.querySelector(".theme-toggle");
  if (!btn) return;

  function current() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }
  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    try { localStorage.setItem("amb-theme", theme); } catch (e) { /* private mode etc. */ }
  }

  btn.setAttribute("aria-pressed", current() === "dark" ? "true" : "false");
  btn.addEventListener("click", function () {
    apply(current() === "dark" ? "light" : "dark");
  });
})();

/* Renders the leaderboard tables from window.AMB_LEADERBOARD (data/leaderboard.js).
   No frameworks, no fetch, no innerHTML: the data ships as a script so file:// works,
   and every node is built with DOM methods. */

(function () {
  var D = window.AMB_LEADERBOARD;
  var board = document.getElementById("board-body");
  if (!D || !board) return;

  var official = !!D.run;

  function pct(x) { return x == null ? null : (100 * x).toFixed(1) + "%"; }
  function pts(x) {
    if (x == null) return null;
    return (x > 0 ? "+" : "") + (100 * x).toFixed(1) + " pts";
  }
  function ciTxt(c) {
    return c ? "[" + (100 * c[0]).toFixed(1) + ", " + (100 * c[1]).toFixed(1) + "]" : null;
  }

  function span(cls, text, bold) {
    var s = document.createElement(bold ? "strong" : "span");
    if (cls) s.className = cls;
    s.textContent = text;
    return s;
  }

  function cell(cls) {
    var td = document.createElement("td");
    if (cls) td.className = cls;
    for (var i = 1; i < arguments.length; i++) {
      if (arguments[i]) td.appendChild(arguments[i]);
    }
    if (!td.firstChild) td.appendChild(span("m-dim", "pending"));
    return td;
  }

  /* Rank only when official: by success desc; list order otherwise. */
  var arms = D.arms.slice();
  if (official) {
    arms.sort(function (a, b) { return (b.success || 0) - (a.success || 0); });
  }

  arms.forEach(function (a, i) {
    var tr = document.createElement("tr");

    tr.appendChild(cell("num", official ? span("m", String(i + 1)) : span("m-dim", "·")));

    var nameTd = cell(null, span("m", "", false));
    nameTd.firstChild.appendChild(span(null, a.name, true));
    if (a.role) nameTd.appendChild(span("m-dim", " · " + a.role));
    tr.appendChild(nameTd);

    tr.appendChild(cell(null, span("dim", a.type)));
    tr.appendChild(cell("num", pct(a.success) && span("m", pct(a.success))));
    tr.appendChild(cell("num",
      a.delta === 0 ? span("m-dim", "baseline") : (pts(a.delta) && span("m", pts(a.delta)))));
    tr.appendChild(cell("num", ciTxt(a.ci) && span("m", ciTxt(a.ci))));
    tr.appendChild(cell("num", a.discarded == null ? null : span("m", String(a.discarded))));
    tr.appendChild(cell("num",
      a.costPerTask == null ? null : span("m", "$" + a.costPerTask.toFixed(2))));

    board.appendChild(tr);
  });

  var ref = document.getElementById("reference-body");
  if (ref) {
    D.reference.forEach(function (r) {
      var tr = document.createElement("tr");
      var nameTd = cell(null, span("m", ""));
      nameTd.firstChild.appendChild(span(null, r.name, true));
      tr.appendChild(nameTd);
      tr.appendChild(cell(null, span("dim", r.what)));
      tr.appendChild(cell("num", pct(r.success) && span("m", pct(r.success))));
      tr.appendChild(cell("num", pts(r.delta) && span("m", pts(r.delta))));
      ref.appendChild(tr);
    });
  }

  /* What the ranking is a ranking OF. The generator decides the wording; the page only
     places it, so a launch cannot quietly drop the qualification from the copy. */
  var scopeBox = document.getElementById("scope-note");
  if (scopeBox && D.scope) {
    var h = document.createElement("strong");
    h.textContent = D.scope.title;
    scopeBox.appendChild(h);
    var p = document.createElement("p");
    p.textContent = D.scope.qualification;
    scopeBox.appendChild(p);
  }

  /* Run banner */
  var meta = document.getElementById("run-meta");
  if (meta) {
    function item(text, live) {
      var s = document.createElement("span");
      if (live) s.className = "live";
      s.textContent = text;
      return s;
    }
    if (official) {
      meta.appendChild(item("run " + D.run.id + " · " + D.run.date, true));
      meta.appendChild(item("model " + D.run.model));
      meta.appendChild(item("CLI " + D.run.cli));
      meta.appendChild(item(D.run.tasks + " tasks"));
      var link = document.createElement("span");
      var a = document.createElement("a");
      a.href = "https://github.com/GiulioDER/agent-memory-bench/tree/master/" + D.run.prereg;
      a.textContent = "preregistration";
      link.appendChild(a);
      meta.appendChild(link);
    } else {
      meta.appendChild(item("no official run yet", true));
      meta.appendChild(item("Phase 0 · harness bring-up and internal pilots"));
      meta.appendChild(item("the first preregistered run is announced before it happens"));
      meta.appendChild(item("page data updated " + D.updated));
    }
  }
})();
