// Your own trades, checked for luck. Pure functions only (the page wires them to the DOM), so
// tests/test_journal_js.py can run them under Node. Uses HL.score / HL.bar / HL.verdict / HL.luck
// from hl.js: the same estimator as the wallet check, on weekly returns built from the trade list.
// Nothing here sends the file anywhere.
const JOURNAL = ((HL) => {
  const WEEK_MS = HL.WEEK_MS;

  // RFC 4180-ish: quoted fields, doubled quotes, commas/newlines inside quotes; ; or tab if the
  // header has more of those than commas (European exports).
  function parseCSV(text) {
    text = text.replace(/^﻿/, '');
    const head = text.split(/\r?\n/, 1)[0] || '';
    const count = c => head.split(c).length - 1;
    const sep = [',', ';', '\t'].sort((a, b) => count(b) - count(a))[0];
    const rows = [];
    let row = [], f = '', q = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (q) {
        if (ch === '"' && text[i + 1] === '"') { f += '"'; i++; }
        else if (ch === '"') q = false;
        else f += ch;
      } else if (ch === '"') q = true;
      else if (ch === sep) { row.push(f); f = ''; }
      else if (ch === '\n' || ch === '\r') {
        if (ch === '\r' && text[i + 1] === '\n') i++;
        row.push(f); f = '';
        if (row.some(x => x.trim() !== '')) rows.push(row);
        row = [];
      } else f += ch;
    }
    row.push(f);
    if (row.some(x => x.trim() !== '')) rows.push(row);
    const header = (rows.shift() || []).map(h => h.trim());
    return {header, rows};
  }

  // "$1,234.50", "(12.30)", "-12.3", "1.234,50 €" -> number; null if not a number.
  function money(s) {
    if (s == null) return null;
    let x = String(s).trim();
    if (!x) return null;
    let neg = false;
    if (/^\(.*\)$/.test(x)) { neg = true; x = x.slice(1, -1); }
    x = x.replace(/[^\d.,\-+eE]/g, '');
    if (/^-/.test(x)) { neg = !neg; x = x.slice(1); }
    if (/,\d{1,2}$/.test(x) && !/\.\d{1,2}$/.test(x)) x = x.replace(/\./g, '').replace(',', '.');  // 1.234,50
    else x = x.replace(/,/g, '');
    const v = Number(x);
    return Number.isFinite(v) && x !== '' ? (neg ? -v : v) : null;
  }

  // Common export formats: ISO, "YYYY-MM-DD HH:MM", "MM/DD/YYYY" (US journals), "DD.MM.YYYY".
  function when(s) {
    if (s == null) return null;
    const x = String(s).trim();
    let m = x.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?)?/i);
    if (m) {
      let y = +m[3]; if (y < 100) y += 2000;
      let h = +(m[4] || 0); const ap = (m[7] || '').toUpperCase();
      if (ap === 'PM' && h < 12) h += 12; if (ap === 'AM' && h === 12) h = 0;
      return Date.UTC(y, +m[1] - 1, +m[2], h, +(m[5] || 0), +(m[6] || 0));
    }
    m = x.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})/);
    if (m) return Date.UTC(+m[3], +m[2] - 1, +m[1]);
    m = x.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
    if (m) return Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0));
    const t = Date.parse(x);
    return Number.isFinite(t) ? t : null;
  }

  const PNL_NAMES = [/^net\s*p\s*&?\s*\/?l/i, /^net\s*pnl/i, /^net\s*profit/i, /^realized/i, /^p\s*&?\s*\/?\s*l/i, /^pnl/i, /profit/i, /^net$/i, /^gross\s*p/i, /return \$/i];
  const DATE_NAMES = [/close.*(date|time)/i, /exit.*(date|time)/i, /^date$/i, /date/i, /time/i, /open.*(date|time)/i];

  // Best guess at the P&L and date columns: by name first, then by how many cells parse.
  function guessColumns(header, rows) {
    const sample = rows.slice(0, 200);
    const share = (i, fn) => sample.length ? sample.filter(r => fn(r[i]) != null).length / sample.length : 0;
    const pick = (names, fn) => {
      for (const re of names) {
        const i = header.findIndex((h, k) => re.test(h) && share(k, fn) > 0.8);
        if (i >= 0) return i;
      }
      return -1;
    };
    return {pnl: pick(PNL_NAMES, money), date: pick(DATE_NAMES, when)};
  }

  // Trades -> [{t, pnl, row}] keeping only rows where both cells parse.
  function trades(rows, dateCol, pnlCol) {
    const out = [];
    let skipped = 0;
    for (const r of rows) {
      const t = when(r[dateCol]), p = money(r[pnlCol]);
      if (t == null || p == null) { skipped++; continue; }
      out.push({t, pnl: p, row: r});
    }
    out.sort((a, b) => a.t - b.t);
    return {list: out, skipped};
  }

  // Weekly returns on a fixed capital: every week from the first trade's week to the last trade's
  // week counts, weeks without trades as 0 (a quiet week is part of the record, and dropping it
  // would overstate the edge per week). Weeks start at the first trade's week start (Monday UTC).
  function weekly(list, capital, span) {
    if (!list.length || !(capital > 0)) return [];
    const monday = t => { const d = new Date(t); const dow = (d.getUTCDay() + 6) % 7; return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - dow * 86400000; };
    const t0 = monday(span ? span[0] : list[0].t), t1 = monday(span ? span[1] : list[list.length - 1].t);
    const n = Math.round((t1 - t0) / WEEK_MS) + 1;
    const sums = new Array(n).fill(0);
    for (const x of list) sums[Math.round((monday(x.t) - t0) / WEEK_MS)] += x.pnl;
    return sums.map(s => [s / capital, 1]);
  }

  // The whole record, checked as if picked from `tried` records or strategies.
  function check(list, capital, tried = 1) {
    const rets = weekly(list, capital);
    const sc = HL.score(rets);
    const v = HL.verdict(sc, Math.max(1, tried));
    return {weeks: rets.length, trades: list.length, total: list.reduce((a, x) => a + x.pnl, 0), score: sc, verdict: v,
            luckBlind: HL.luck(sc.t, 1), luckPicked: HL.luck(sc.t, Math.max(1, tried))};
  }

  // Every value of one column (setup, tag, weekday...) as its own record over the same weeks; the
  // best slice is then judged as the best of all slices scored, times what was tried before.
  function slices(list, capital, col, tried = 1) {
    if (!list.length) return null;
    const span = [list[0].t, list[list.length - 1].t];
    const groups = new Map();
    for (const x of list) {
      const k = (x.row[col] == null ? '' : String(x.row[col]).trim()) || '(blank)';
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(x);
    }
    const scored = [];
    for (const [k, g] of groups) {
      const sc = HL.score(weekly(g, capital, span));
      scored.push({value: k, trades: g.length, total: g.reduce((a, x) => a + x.pnl, 0), t: sc.t, sharpe: sc.sharpe});
    }
    scored.sort((a, b) => (b.t ?? -1e9) - (a.t ?? -1e9));
    const n = scored.filter(s => s.t != null).length;
    const best = scored[0];
    const pool = Math.max(1, n) * Math.max(1, tried);
    return {slices: scored, scoredCount: n, best, pool, bar: HL.bar(pool),
            verdictBest: best && best.t != null ? HL.verdict({t: best.t}, pool) : {key: 'too_short', bar: HL.bar(pool)},
            luckBestBlind: best ? HL.luck(best.t, 1) : null, luckBestPicked: best ? HL.luck(best.t, pool) : null};
  }

  return {parseCSV, money, when, guessColumns, trades, weekly, check, slices};
})(typeof HL !== 'undefined' ? HL : require('./hl.js'));
if (typeof module !== 'undefined') module.exports = JOURNAL;
