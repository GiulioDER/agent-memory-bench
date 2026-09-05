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
  function tokenTxt(x) {
    return x == null ? null : Number(x).toLocaleString("en-US");
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

    /* Held and pending arms are NOT ranked. A held arm's numbers are withheld, while a pending
       arm has not been measured yet; neither should carry a rank that implies it placed there. */
    tr.appendChild(cell("num",
      (official && !a.held && !a.pending) ? span("m", String(i + 1)) : span("m-dim", "·")));

    var nameTd = cell(null, span("m", "", false));
    nameTd.firstChild.appendChild(span(null, a.name, true));
    if (a.role) nameTd.appendChild(span("m-dim", " · " + a.role));
    if (a.comparison) nameTd.appendChild(span("m-dim", " · " + a.comparison));
    /* Say WHY the row is blank. A blank row with no reason reads as "measured nothing", which is
       the opposite of what a hold means. */
    if (a.held) {
      nameTd.appendChild(span("m-dim", " · " + a.held +
        (a.heldUntil ? " until " + a.heldUntil : "")));
      /* The thread is the evidence for the promise, so a reader can check it against the
         vendor's own repository rather than taking this page's word for it. */
      if (a.heldIssue) {
        var hi = document.createElement("a");
        hi.href = a.heldIssue;
        hi.rel = "noopener";
        hi.className = "m-dim";
        hi.appendChild(document.createTextNode(" · thread"));
        nameTd.appendChild(hi);
      }
    }
    if (a.pending) nameTd.appendChild(span("m-dim", " · pending"));
    tr.appendChild(nameTd);

    tr.appendChild(cell(null, span("dim", a.type)));
    tr.appendChild(cell("num", pct(a.success) && span("m", pct(a.success))));
    tr.appendChild(cell("num",
      a.delta === 0 ? span("m-dim", "baseline") : (pts(a.delta) && span("m", pts(a.delta)))));
    tr.appendChild(cell("num", ciTxt(a.ci) && span("m", ciTxt(a.ci))));
    tr.appendChild(cell("num", a.discarded == null ? null : span("m", String(a.discarded))));
    /* Total token spend is meaningful for vendors only. Controls retain a deliberate dash so
       this column cannot be mistaken for a missing measurement. */
    tr.appendChild(cell("num", !a.role && a.totalTokens != null
      ? span("m", tokenTxt(a.totalTokens))
      : span("m-dim", "—")));
    /* Costs here are sub-cent per task: toFixed(2) rendered every arm as $0.00 and made the
       column useless. Scale the precision to the magnitude so a real difference is visible. */
    tr.appendChild(cell("num", a.costPerTask == null ? null : span("m", "$" + (
      a.costPerTask >= 1 ? a.costPerTask.toFixed(2)
      : a.costPerTask >= 0.01 ? a.costPerTask.toFixed(3)
      : a.costPerTask.toFixed(4)))));

    board.appendChild(tr);
  });

  /* Products, condition by condition. Columns are built from the data rather than the markup,
     because which arms are products is decided by the generator and can change between runs. */
  var condHead = document.getElementById("condition-head");
  var condBody = document.getElementById("condition-body");
  if (condHead && condBody) {
    var products = D.arms.filter(function (a) { return "byCondition" in a; });
    var conds = [];
    products.forEach(function (a) {
      if (a.byCondition) {
        Object.keys(a.byCondition).forEach(function (c) {
          if (conds.indexOf(c) === -1) conds.push(c);
        });
      }
    });

    if (products.length && conds.length) {
      var hc = document.createElement("th");
      hc.appendChild(document.createTextNode("condition"));
      condHead.appendChild(hc);
      products.forEach(function (a) {
        var th = document.createElement("th");
        th.className = "num";
        th.appendChild(document.createTextNode(a.name));
        condHead.appendChild(th);
      });

      conds.forEach(function (c) {
        var tr = document.createElement("tr");
        tr.appendChild(cell(null, span("m", c)));
        products.forEach(function (a) {
          if (!a.byCondition) {
            tr.appendChild(cell("num", span("m-dim", "pending")));
            return;
          }
          var v = a.byCondition[c];
          if (!v || !v.cells) { tr.appendChild(cell("num", null)); return; }
          var td = cell("num", span("m", v.solved + "/" + v.cells));
          td.appendChild(span("m-dim", " " + Math.round((v.solved / v.cells) * 100) + "%"));
          tr.appendChild(td);
        });
        condBody.appendChild(tr);
      });
    }
  }

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

  /* The generated analysis is the reader-facing interpretation layer. It is deliberately kept
     separate from the ranking table: a high score is not automatically a good tradeoff when it
     costs more tokens, takes longer, or comes from a held vendor. */
  var analysis = D.analysis;
  var analysisPanel = document.getElementById("run-analysis");
  if (analysis && analysisPanel) {
    analysisPanel.hidden = false;
    var analysisHeadline = document.getElementById("analysis-headline");
    var analysisSummary = document.getElementById("analysis-summary");
    if (analysisHeadline) analysisHeadline.textContent = analysis.headline || "Run analysis";
    if (analysisSummary) {
      var winner = analysis.overall_winner;
      var memory = analysis.best_visible_memory;
      analysisSummary.textContent = "Audit " + analysis.status + " · " +
        (winner ? winner.arm + " leads the visible arms at " + pct(winner.success) : "no visible winner") +
        (memory ? " · " + memory.arm + " is the strongest visible memory product" : "") +
        " · " + (analysis.admitted_cells || "pending") + " admitted cells";
    }

    var metrics = document.getElementById("analysis-metrics");
    function metric(label, value, note) {
      var box = document.createElement("div");
      box.className = "analysis-metric";
      box.appendChild(span("label m-dim", label));
      box.appendChild(span("value", value, true));
      if (note) box.appendChild(span("note m-dim", note));
      metrics.appendChild(box);
    }
    if (metrics) {
      metric("overall winner", analysis.overall_winner ? analysis.overall_winner.arm : "pending", analysis.overall_winner ? pct(analysis.overall_winner.success) : null);
      metric("best memory product", analysis.best_visible_memory ? analysis.best_visible_memory.arm : "pending", analysis.best_visible_memory ? pts(analysis.best_visible_memory.delta_vs_baseline) : null);
      metric("audit", String(analysis.status).toUpperCase(), "derived from published evidence");
      metric("comparison frame", (analysis.conditions || []).length + " conditions", (analysis.admitted_cells || "pending") + " admitted cells");
    }

    var links = document.getElementById("analysis-links");
    function repoLink(path, label) {
      var link = document.createElement("a");
      link.href = "https://github.com/GiulioDER/agent-memory-bench/blob/master/" + path;
      link.rel = "noopener";
      link.textContent = label;
      return link;
    }
    if (links && analysis.report_markdown) {
      links.appendChild(repoLink(analysis.report_markdown, "full report ↗"));
      if (analysis.audit_json) links.appendChild(repoLink(analysis.audit_json, "audit JSON ↗"));
    }

    var analysisBody = document.getElementById("analysis-body");
    function money(x) {
      return x == null ? "pending" : "$" + (x >= 0.01 ? x.toFixed(3) : x.toFixed(4));
    }
    function seconds(x) { return x == null ? "pending" : x.toFixed(1) + " s"; }
    if (analysisBody) Object.keys(analysis.arms || {}).forEach(function (name) {
      var a = analysis.arms[name];
      var tr = document.createElement("tr");
      if (a.status === "held") tr.setAttribute("data-held", "true");
      tr.appendChild(cell(null, span("m", name, true)));
      tr.appendChild(cell("num", a.success == null ? null : span("m", pct(a.success))));
      var costValue = a.cost && a.cost.usd_per_admitted_cell != null ? a.cost.usd_per_admitted_cell : (a.cost ? a.cost.reported_usd_per_task : null);
      tr.appendChild(cell("num", costValue == null ? null : span("m", money(costValue))));
      tr.appendChild(cell("num", a.speed && a.speed.mean_session_s != null ? span("m", seconds(a.speed.mean_session_s)) : null));
      tr.appendChild(cell("num", a.delta_vs_baseline == null ? null : span("m", pts(a.delta_vs_baseline))));
      var read = "";
      if (a.status === "held") read = a.hold.reason;
      else if (name === "claude_md") read = "designated baseline";
      else if (analysis.best_visible_memory && name === analysis.best_visible_memory.arm) read = "best visible memory product";
      else if (a.comparison) read = "joined vendor submission";
      else if (a.cost && a.speed) read = (a.cost.relative_to_baseline > 0 ? "higher spend" : "lower spend") + ", " + (a.speed.relative_to_baseline > 0 ? "slower" : "faster");
      tr.appendChild(cell(null, span("analysis-read", read)));
      analysisBody.appendChild(tr);
    });

    var insights = document.getElementById("analysis-insights");
    if (insights) (analysis.insights || []).forEach(function (text) {
      var p = document.createElement("p");
      p.textContent = text;
      insights.appendChild(p);
    });
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
