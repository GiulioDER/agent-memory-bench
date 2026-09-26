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

  function tokens(n) {
    if (n == null) return null;
    return n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "k" : String(n);
  }
  function times(x) { return x == null ? null : "×" + x.toFixed(1); }

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

  /* Cost is the AGENT's tokens per task, metered the same way for every arm and priced at one
     rate; the ingest that built each product's store is a separate column because it was not
     metered the same way for every arm, and one number for both would compare unlike things. */
  function costCell(a) {
    var c = a.cost;
    if (!c) return cell("num", null);
    var td = cell("num", span("m strong-num", tokens(c.agentTokensPerTask)));
    if (c.relativeToBaseline != null) {
      td.appendChild(block("m-dim", times(c.relativeToBaseline) + " " + BASELINE));
    }
    if (c.agentUsdPerTask != null) td.appendChild(block("m-dim", money(c.agentUsdPerTask)));
    return td;
  }

  var INGEST = {
    "metered": "metered",
    "not metered": "not metered",
    "local model": "local model",
    "none recorded": "not in ledger"
  };
  function ingestCell(a) {
    var c = a.cost;
    if (!c) return cell("ingest", null);
    var i = c.ingest;
    var td = cell("ingest", span(i.status === "not metered" ? "m verdict-strong" : "m",
      INGEST[i.status] || i.status));
    if (i.tokens) td.appendChild(block("m-dim", tokens(i.tokens) + " tokens"));
    if (i.status === "not metered") td.appendChild(block("m-dim", "cost missing, not zero"));
    else if (i.localModel) td.appendChild(block("m-dim", "not billed in tokens"));
    return td;
  }

  /* Pros and cons are editorial, written by the author in data/analysis.js and dated there.
     They carry no number: every number on this page is generated from run artifacts. */
  var NOTES = (window.AMB_ANALYSIS && window.AMB_ANALYSIS.vendors) || {};
  function notesList(items, kind) {
    var box = document.createElement("div");
    box.className = "notes-col";
    box.appendChild(span("notes-label m-dim", kind));
    var ul = document.createElement("ul");
    ul.className = "notes-list notes-" + kind;
    items.forEach(function (text) {
      var li = document.createElement("li");
      li.textContent = text;
      ul.appendChild(li);
    });
    box.appendChild(ul);
    return box;
  }
  function notesRow(a) {
    var n = NOTES[a.name];
    if (!n || !((n.pros && n.pros.length) || (n.cons && n.cons.length))) return null;
    var tr = document.createElement("tr");
    tr.className = "notes-row";
    tr.appendChild(document.createElement("td"));
    var td = document.createElement("td");
    td.colSpan = 7;
    var grid = document.createElement("div");
    grid.className = "notes-grid";
    grid.appendChild(notesList(n.pros || [], "pros"));
    grid.appendChild(notesList(n.cons || [], "cons"));
    td.appendChild(grid);
    tr.appendChild(td);
    return tr;
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
    tr.appendChild(cell("num", pts(a.delta) && span("m", pts(a.delta))));
    /* The interval as numbers, bold when it excludes zero: that is the only case in which the
       difference from the baseline is a result rather than noise. */
    tr.appendChild(cell("num", a.ci && !a.held &&
      span(v === SAME ? "m dim" : "m strong-num", ciTxt(a.ci))));
    var scored = scoredCells(a);
    tr.appendChild(cell("num", scored != null && span("m", String(scored)),
      a.discarded != null && block("m-dim", a.discarded + " discarded")));
    tr.appendChild(costCell(a));
    tr.appendChild(ingestCell(a));
    /* Pros and cons sit in a band under the numbers rather than in two more columns: as columns
       they pushed the table past the page width, and a reader scrolled sideways to find them. */
    var notes = notesRow(a);
    if (notes) {
      tr.className += " has-notes";
      if (tr.className.indexOf("row-worse") !== -1) notes.className += " row-worse";
      board.appendChild(tr);
      board.appendChild(notes);
    } else {
      board.appendChild(tr);
    }
  });

  /* ---------- 02 condition by condition, one ranked list per condition ----------
     Changed 2026-09-26 from one grid (products as rows, conditions as columns): a reader wanted to
     see who led each condition, which a grid makes you work out column by column. Each condition
     is now its own list, best first, with claude_md placed where it ranks. */

  var CONDITION_NOTES = {
    present: "a clean governing fact",
    absent: "no answer to find",
    superseded: "a stale fact, since replaced",
    contradictory: "two facts in conflict",
    adjacent: "a plausible fact from the wrong scope"
  };

  var condGrid = document.getElementById("condition-grid");
  if (condGrid) {
    var conds = [];
    D.arms.forEach(function (a) {
      if (a.byCondition) Object.keys(a.byCondition).forEach(function (c) {
        if (conds.indexOf(c) === -1) conds.push(c);
      });
    });
    var order = ["present", "absent", "superseded", "contradictory", "adjacent"];
    conds.sort(function (x, y) {
      var i = order.indexOf(x), j = order.indexOf(y);
      return (i < 0 ? 99 : i) - (j < 0 ? 99 : j);
    });
    var ref = baselineArm && baselineArm.byCondition;
    var rate = function (v) { return v && v.cells ? v.solved / v.cells : null; };
    var listed = [baselineArm].concat(ranked).filter(function (a) {
      return a && a.byCondition && !a.held;
    });

    conds.forEach(function (c) {
      var card = document.createElement("div");
      card.className = "cond-card";
      var head = document.createElement("div");
      head.className = "cond-head";
      head.appendChild(span("cond-name", c, true));
      if (CONDITION_NOTES[c]) head.appendChild(block("m-dim", CONDITION_NOTES[c]));
      card.appendChild(head);

      var base = ref ? rate(ref[c]) : null;
      var rows = listed.map(function (a) {
        return { arm: a, r: rate(a.byCondition[c]), v: a.byCondition[c] };
      }).filter(function (x) { return x.r != null; });
      rows.sort(function (x, y) { return y.r - x.r; });

      var ol = document.createElement("ol");
      ol.className = "cond-list";
      var place = 0;
      rows.forEach(function (x) {
        var isBase = x.arm.name === BASELINE;
        var li = document.createElement("li");
        if (isBase) li.className = "cond-baseline";
        else if (base != null && x.r < base) li.className = "cond-below";
        li.appendChild(span("cond-rank m-dim", isBase ? "·" : String(++place)));
        var who = document.createElement("span");
        who.className = "cond-who";
        who.appendChild(span("product-name", x.arm.name));
        who.appendChild(block("m-dim", x.v.solved + "/" + x.v.cells));
        li.appendChild(who);
        var num = document.createElement("span");
        num.className = "cond-num";
        num.appendChild(span("m strong-num", Math.round(100 * x.r) + "%"));
        var d = base == null ? null : Math.round(100 * (x.r - base));
        num.appendChild(block("m-dim", isBase ? "baseline" :
          d == null ? "" : (d > 0 ? "+" : d < 0 ? MINUS : "±") + Math.abs(d) + " pts"));
        li.appendChild(num);
        ol.appendChild(li);
      });
      card.appendChild(ol);
      condGrid.appendChild(card);
    });
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

  var priceBox = document.getElementById("price-basis");
  if (priceBox && D.priceBasis) {
    priceBox.textContent = D.priceBasis.model + " at $" + D.priceBasis.usdPerMtokInput +
      " input and $" + D.priceBasis.usdPerMtokOutput + " output per million tokens, as of " +
      D.priceBasis.asOf;
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

/* Renders the generated numbers on analysis.html. The prose on that page is written by hand and
   dated; the figures beside it are not, so a reader can check one against the other. Each
   `[data-arm]` placeholder receives that product's strip, condition row and pros and cons. */

(function () {
  var D = window.AMB_LEADERBOARD;
  var A = window.AMB_ANALYSIS;
  var slots = document.querySelectorAll("[data-arm]");
  if (!D || !slots.length) return;

  var BASELINE = D.baseline || "claude_md";
  var MINUS = "−";
  var byName = {};
  D.arms.forEach(function (a) { byName[a.name] = a; });
  var base = byName[BASELINE];

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function signed(x, digits) {
    return (x > 0 ? "+" : x < 0 ? MINUS : "±") + Math.abs(x).toFixed(digits == null ? 1 : digits);
  }
  function tokens(n) {
    return n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "k" : String(n);
  }
  function stat(box, label, value, note) {
    var s = el("div", "vstat");
    s.appendChild(el("span", "label m-dim", label));
    s.appendChild(el("strong", "value", value));
    if (note) s.appendChild(el("span", "note m-dim", note));
    box.appendChild(s);
  }

  Array.prototype.forEach.call(slots, function (slot) {
    var a = byName[slot.getAttribute("data-arm")];
    if (!a) return;
    var kind = slot.getAttribute("data-show");

    if (kind === "notes") {
      var n = A && A.vendors && A.vendors[a.name];
      if (!n) return;
      var grid = el("div", "notes-grid");
      ["pros", "cons"].forEach(function (k) {
        var col = el("div", "notes-col");
        col.appendChild(el("span", "notes-label m-dim", k));
        var ul = el("ul", "notes-list notes-" + k);
        (n[k] || []).forEach(function (t) { ul.appendChild(el("li", null, t)); });
        col.appendChild(ul);
        grid.appendChild(col);
      });
      slot.appendChild(grid);
      return;
    }

    var strip = el("div", "vstats");
    if (a.success != null) {
      stat(strip, "task success", (100 * a.success).toFixed(1) + "%",
        signed(100 * a.delta) + " pts vs " + BASELINE);
    }
    if (a.ci) {
      var clear = a.ci[0] > 0 || a.ci[1] < 0;
      stat(strip, "95% interval", signed(100 * a.ci[0]) + " to " + signed(100 * a.ci[1]),
        clear ? "excludes zero" : "crosses zero");
    }
    if (a.cost) {
      stat(strip, "agent tokens / task", tokens(a.cost.agentTokensPerTask),
        a.cost.relativeToBaseline == null ? null
          : "×" + a.cost.relativeToBaseline.toFixed(1) + " " + BASELINE);
      var i = a.cost.ingest;
      stat(strip, "ingest", i.status === "none recorded" ? "not in ledger" : i.status,
        i.tokens ? tokens(i.tokens) + " tokens" : i.localModel || null);
    }
    if (a.sourceRun) stat(strip, "run", a.sourceRun, a.discarded != null ? a.discarded + " cells discarded" : null);
    slot.appendChild(strip);

    if (a.byCondition && base && base.byCondition) {
      var row = el("div", "vconds");
      ["present", "absent", "superseded", "contradictory", "adjacent"].forEach(function (c) {
        var v = a.byCondition[c], b = base.byCondition[c];
        if (!v || !v.cells || !b || !b.cells) return;
        var d = Math.round(100 * (v.solved / v.cells - b.solved / b.cells));
        var cell = el("div", "vcond" + (d < 0 ? " vcond-below" : d > 0 ? " vcond-above" : ""));
        cell.appendChild(el("span", "m-dim", c));
        cell.appendChild(el("strong", null, Math.round(100 * v.solved / v.cells) + "%"));
        cell.appendChild(el("span", "m-dim", signed(d, 0) + " pts"));
        row.appendChild(cell);
      });
      slot.appendChild(row);
    }
  });
})();
