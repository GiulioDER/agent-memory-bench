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

/* Renders the leaderboard from window.AMB_LEADERBOARD (data/leaderboard.js).
   No frameworks, no fetch, no innerHTML: the data ships as a script so file:// works,
   and every node is built with DOM methods.

   Layout, decided 2026-09-26 after a reader found one mixed table unreadable: memory products
   first, each read against claude_md with its interval drawn; then the same products condition
   by condition; then the controls and reference tracks, which price the grid rather than compete
   in it, at the bottom. */

(function () {
  var D = window.AMB_LEADERBOARD;
  var board = document.getElementById("board-body");
  if (!D || !board) return;

  var official = !!D.run;
  var BASELINE = D.baseline || "claude_md";
  var MINUS = "−";

  function pct(x) { return x == null ? null : (100 * x).toFixed(1) + "%"; }
  function pts(x) {
    if (x == null) return null;
    return (x > 0 ? "+" : x < 0 ? MINUS : "") + Math.abs(100 * x).toFixed(1) + " pts";
  }
  function signed(x) { return (x > 0 ? "+" : x < 0 ? MINUS : "") + Math.abs(100 * x).toFixed(1); }
  function ciTxt(c) { return c ? signed(c[0]) + " to " + signed(c[1]) : null; }
  function money(x) {
    if (x == null) return null;
    return "$" + (x >= 1 ? x.toFixed(2) : x >= 0.01 ? x.toFixed(3) : x.toFixed(4));
  }

  function span(cls, text, bold) {
    var s = document.createElement(bold ? "strong" : "span");
    if (cls) s.className = cls;
    s.textContent = text;
    return s;
  }
  function block(cls, text) {
    var d = document.createElement("div");
    d.className = cls;
    d.textContent = text;
    return d;
  }
  function cell(cls) {
    var td = document.createElement("td");
    if (cls) td.className = cls;
    for (var i = 1; i < arguments.length; i++) {
      if (arguments[i]) td.appendChild(arguments[i]);
    }
    if (!td.firstChild) td.appendChild(span("m-dim", "—"));
    return td;
  }

  /* A product is an arm with no role. Controls carry one (baseline, floor, control). */
  var products = D.arms.filter(function (a) { return !a.role; });
  var controls = D.arms.filter(function (a) { return !!a.role; });
  var baselineArm = D.arms.filter(function (a) { return a.name === BASELINE; })[0];

  /* The words a reader acts on. An interval wholly on one side of zero is a distinguishable
     result; one that crosses zero is not, whatever the point estimate says. */
  var SAME = "no clear difference";
  function verdict(a) {
    if (a.held) return "held for vendor review";
    if (a.pending) return "not yet measured";
    if (a.name === BASELINE) return "baseline";
    if (!a.ci) return null;
    if (a.ci[0] > 0) return "better than " + BASELINE;
    if (a.ci[1] < 0) return "worse than " + BASELINE;
    return SAME;
  }

  function scoredCells(a) {
    if (!a.byCondition) return null;
    return Object.keys(a.byCondition).reduce(function (n, c) {
      return n + (a.byCondition[c].cells || 0);
    }, 0);
  }

  /* One shared axis for every interval in the product table, always including zero. */
  var lo = 0, hi = 0;
  products.forEach(function (a) {
    if (a.ci && !a.held) { lo = Math.min(lo, a.ci[0]); hi = Math.max(hi, a.ci[1]); }
  });
  var axisPad = Math.max(0.02, (hi - lo) * 0.06);
  lo -= axisPad; hi += axisPad;
  function at(x) { return (100 * (x - lo) / (hi - lo)).toFixed(2) + "%"; }

  function ciPlot(a) {
    var box = document.createElement("div");
    box.className = "ci-plot";
    box.setAttribute("role", "img");
    var zero = document.createElement("span");
    zero.className = "ci-zero";
    zero.style.left = at(0);
    box.appendChild(zero);
    if (!a.ci || a.held) {
      box.setAttribute("aria-label", "no interval");
      return box;
    }
    var bar = document.createElement("span");
    bar.className = "ci-bar" + (verdict(a) === SAME ? "" : " ci-bar-clear");
    bar.style.left = at(a.ci[0]);
    bar.style.width = (100 * (a.ci[1] - a.ci[0]) / (hi - lo)).toFixed(2) + "%";
    box.appendChild(bar);
    if (a.delta != null) {
      var dot = document.createElement("span");
      dot.className = "ci-dot";
      dot.style.left = at(a.delta);
      box.appendChild(dot);
    }
    box.setAttribute("aria-label",
      "95% interval " + ciTxt(a.ci) + " points, estimate " + signed(a.delta));
    return box;
  }

  /* ---------- 01 memory products ---------- */

  var ranked = products.slice();
  if (official) {
    ranked.sort(function (a, b) {
      /* Held and pending arms carry no numbers and sort last, unranked. */
      var ah = a.held || a.pending ? 1 : 0, bh = b.held || b.pending ? 1 : 0;
      if (ah !== bh) return ah - bh;
      return (b.success || 0) - (a.success || 0);
    });
  }

  var rank = 0;
  ranked.forEach(function (a) {
    var tr = document.createElement("tr");
    var v = verdict(a);
    if (v === "worse than " + BASELINE) tr.className = "row-worse";

    /* Held and pending arms are NOT ranked. A held arm's numbers are withheld, while a pending
       arm has not been measured yet; neither should carry a rank that implies it placed there. */
    tr.appendChild(cell("num",
      (official && !a.held && !a.pending) ? span("m", String(++rank)) : span("m-dim", "·")));

    var nameTd = cell("product", span("product-name", a.name, true));
    nameTd.appendChild(block("product-type dim", a.type));
    if (a.comparison) {
      /* The run id is long and a reader rarely needs it inline; it stays one hover away. */
      var own = block("m-dim", "own run, " + a.comparison);
      own.title = a.sourceRun;
      nameTd.appendChild(own);
    }
    /* Say WHY the row is blank. A blank row with no reason reads as "measured nothing", which is
       the opposite of what a hold means. */
    if (a.held) {
      var why = block("m-dim", a.held + (a.heldUntil ? " until " + a.heldUntil : ""));
      /* The thread is the evidence for the promise, so a reader can check it against the
         vendor's own repository rather than taking this page's word for it. */
      if (a.heldIssue) {
        var thread = document.createElement("a");
        thread.href = a.heldIssue;
        thread.rel = "noopener";
        thread.appendChild(document.createTextNode(" · thread"));
        why.appendChild(thread);
      }
      nameTd.appendChild(why);
    }
    tr.appendChild(nameTd);

    tr.appendChild(cell("num", pct(a.success) && span("m strong-num", pct(a.success))));
    tr.appendChild(cell("num", pts(a.delta) && span("m", pts(a.delta)),
      a.ci && block("m-dim", ciTxt(a.ci))));
    tr.appendChild(cell("ci-col", ciPlot(a)));
    tr.appendChild(cell("verdict", v && span(v === SAME ? "dim" : "verdict-strong", v)));
    var scored = scoredCells(a);
    tr.appendChild(cell("num", scored != null && span("m", String(scored)),
      a.discarded != null && block("m-dim", a.discarded + " discarded")));
    tr.appendChild(cell("num", money(a.costPerTask) && span("m", money(a.costPerTask))));
    board.appendChild(tr);
  });

  /* ---------- 02 condition by condition, products as rows ---------- */

  var condHead = document.getElementById("condition-head");
  var condBody = document.getElementById("condition-body");
  if (condHead && condBody) {
    var conds = [];
    D.arms.forEach(function (a) {
      if (a.byCondition) Object.keys(a.byCondition).forEach(function (c) {
        if (conds.indexOf(c) === -1) conds.push(c);
      });
    });
    var ref = baselineArm && baselineArm.byCondition;
    var rate = function (v) { return v && v.cells ? v.solved / v.cells : null; };

    var condRow = function (a, isBaseline) {
      var tr = document.createElement("tr");
      if (isBaseline) tr.className = "row-baseline";
      var nameTd = cell(null, span("product-name", a.name, true));
      if (isBaseline) nameTd.appendChild(block("m-dim", "baseline"));
      tr.appendChild(nameTd);
      conds.forEach(function (c) {
        var v = a.byCondition ? a.byCondition[c] : null;
        var r = rate(v);
        if (r == null) { tr.appendChild(cell("num", null)); return; }
        var td = cell("num", span("m strong-num", Math.round(100 * r) + "%"));
        var sub = v.solved + "/" + v.cells;
        var base = ref ? rate(ref[c]) : null;
        if (!isBaseline && base != null) {
          var d = Math.round(100 * (r - base));
          sub = (d > 0 ? "+" : d < 0 ? MINUS : "±") + Math.abs(d) + " · " + sub;
        }
        td.appendChild(block("m-dim", sub));
        tr.appendChild(td);
      });
      condBody.appendChild(tr);
    };

    if (conds.length) {
      var th0 = document.createElement("th");
      th0.textContent = "arm";
      condHead.appendChild(th0);
      conds.forEach(function (c) {
        var th = document.createElement("th");
        th.className = "num";
        th.textContent = c;
        condHead.appendChild(th);
      });
      if (baselineArm && baselineArm.byCondition) condRow(baselineArm, true);
      ranked.forEach(function (a) { if (a.byCondition) condRow(a, false); });
    }
  }

  /* ---------- 03 controls and reference tracks ---------- */

  var controlsBody = document.getElementById("controls-body");
  if (controlsBody) {
    var roleOrder = { baseline: 0, floor: 1, control: 2 };
    controls.slice().sort(function (a, b) {
      return (roleOrder[a.role] == null ? 9 : roleOrder[a.role]) -
        (roleOrder[b.role] == null ? 9 : roleOrder[b.role]);
    }).forEach(function (a) {
      var tr = document.createElement("tr");
      if (a.role === "baseline") tr.className = "row-baseline";
      var nameTd = cell(null, span("product-name", a.name, true));
      nameTd.appendChild(block("m-dim", a.role));
      tr.appendChild(nameTd);
      tr.appendChild(cell(null, span("dim", a.type)));
      tr.appendChild(cell("num", pct(a.success) && span("m strong-num", pct(a.success))));
      tr.appendChild(cell("num", a.role === "baseline" ? span("m-dim", "reference")
        : pts(a.delta) && span("m", pts(a.delta))));
      tr.appendChild(cell("num",
        a.role === "baseline" ? null : ciTxt(a.ci) && span("m-dim", ciTxt(a.ci))));
      controlsBody.appendChild(tr);
    });
    (D.reference || []).forEach(function (r) {
      var tr = document.createElement("tr");
      var nameTd = cell(null, span("product-name", r.name, true));
      nameTd.appendChild(block("m-dim", "reference track"));
      tr.appendChild(nameTd);
      tr.appendChild(cell(null, span("dim", r.what)));
      tr.appendChild(cell("num", pct(r.success) && span("m strong-num", pct(r.success))));
      tr.appendChild(cell("num", pts(r.delta) && span("m", pts(r.delta))));
      tr.appendChild(cell("num", null));
      controlsBody.appendChild(tr);
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

  /* ---------- the result in one line ---------- */

  var analysis = D.analysis;
  var analysisPanel = document.getElementById("run-analysis");
  if (analysis && analysisPanel) {
    analysisPanel.hidden = false;
    var measured = products.filter(function (a) { return !a.held && !a.pending && a.ci; });
    var better = measured.filter(function (a) { return a.ci[0] > 0; });
    var worse = measured.filter(function (a) { return a.ci[1] < 0; });
    var notYet = products.filter(function (a) { return a.pending || a.held; });
    var bestProduct = measured.slice().sort(function (a, b) { return b.success - a.success; })[0];
    var topControl = controls.slice().sort(function (a, b) {
      return (b.success || 0) - (a.success || 0);
    })[0];
    var controlOnTop = topControl && bestProduct && topControl.success > bestProduct.success;
    var names = function (list) { return list.map(function (a) { return a.name; }).join(", "); };

    var analysisHeadline = document.getElementById("analysis-headline");
    if (analysisHeadline) analysisHeadline.textContent = analysis.headline || "Run analysis";
    var analysisSummary = document.getElementById("analysis-summary");
    if (analysisSummary) {
      analysisSummary.textContent =
        measured.length + " memory products measured" +
        (notYet.length ? ", " + notYet.length + " without published numbers" : "") + ". " +
        (better.length ? names(better) + " clearly better than " + BASELINE
          : "None is clearly better than " + BASELINE) +
        (worse.length ? "; " + names(worse) + " clearly worse" : "") + ". " +
        (controlOnTop ? "The highest score belongs to a control, " + topControl.name +
          ", not to a memory product." : "");
    }

    var metrics = document.getElementById("analysis-metrics");
    var metric = function (label, value, note) {
      var box = document.createElement("div");
      box.className = "analysis-metric";
      box.appendChild(span("label m-dim", label));
      box.appendChild(span("value", value, true));
      if (note) box.appendChild(span("note m-dim", note));
      metrics.appendChild(box);
    };
    if (metrics) {
      metric("best memory product", bestProduct ? bestProduct.name : "—",
        bestProduct ? pct(bestProduct.success) + ", " + pts(bestProduct.delta) + " vs " + BASELINE
          : null);
      metric("clearly better than " + BASELINE, better.length + " of " + measured.length,
        better.length ? names(better) : "95% interval wholly above zero");
      metric("clearly worse than " + BASELINE, worse.length + " of " + measured.length,
        worse.length ? names(worse) : "95% interval wholly below zero");
      metric("highest control", topControl ? topControl.name : "—",
        topControl ? pct(topControl.success) + (controlOnTop ? ", above every product" : "") : null);
    }

    var links = document.getElementById("analysis-links");
    var repoLink = function (path, label) {
      var link = document.createElement("a");
      link.href = "https://github.com/GiulioDER/agent-memory-bench/blob/master/" + path;
      link.rel = "noopener";
      link.textContent = label;
      return link;
    };
    if (links && analysis.report_markdown) {
      links.appendChild(repoLink(analysis.report_markdown, "full report ↗"));
      if (analysis.audit_json) links.appendChild(repoLink(analysis.audit_json, "audit JSON ↗"));
    }

    var insights = document.getElementById("analysis-insights");
    if (insights) (analysis.insights || []).forEach(function (text) {
      var para = document.createElement("p");
      para.textContent = text;
      insights.appendChild(para);
    });
  }

  /* Run banner */
  var meta = document.getElementById("run-meta");
  if (meta) {
    var item = function (text, live) {
      var s = document.createElement("span");
      if (live) s.className = "live";
      s.textContent = text;
      return s;
    };
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
