// Wallet check page: one script for every language. The page sets window.WALLET =
// {N, NV, T}: N is the trader board size, NV the number of vaults Hyperliquid lists (null if
// unknown), T the strings (built by tools/build_site.py).
(() => {
 const {N, NV, T} = window.WALLET, $ = id => document.getElementById(id), f = (x, d=2) => x == null ? '—' : Number(x).toFixed(d);
 const fill = (s, o) => s.replace(/\{(\w+)\}/g, (m, k) => k in o ? o[k] : m);
 // ?team=1 once marks this browser as ours (?team=0 clears it), so the counts can leave our own testing out.
 const team = (() => { try { const q = new URLSearchParams(location.search).get('team'); if (q === '1') localStorage.setItem('ed_team', '1'); if (q === '0') localStorage.removeItem('ed_team'); return localStorage.getItem('ed_team') === '1'; } catch (e) { return false; } })();
 const tally = u => { try { fetch(u + (team ? '&s=team' : ''), {method: 'POST', mode: 'no-cors', keepalive: true}); } catch (e) {} };
 function meter(t, bar, n) {
  // drawn at the box's own pixel width, so the labels stay readable on a phone
  const W = Math.max(320, Math.round(($('wmeter').clientWidth || 1028) - 28));
  const lo = Math.min(-1, Math.floor(t ?? 0)), hi = Math.max(Math.ceil(bar + .5), Math.ceil(t ?? 0)), H = 92, L = 14, R = 14;
  const x = v => L + (v - lo) / (hi - lo) * (W - L - R);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${T.meterAria}">`;
  s += `<rect class="zone" x="${x(bar)}" y="22" width="${W - R - x(bar)}" height="40"/>`;
  const step = W < 600 && hi - lo > 10 ? 2 : 1;
  for (let v = lo; v <= hi; v++) if ((v - lo) % step === 0 || v === 2) s += `<line class="ax" x1="${x(v)}" x2="${x(v)}" y1="22" y2="62"/><text class="lab" x="${x(v)}" y="84" text-anchor="middle">${v}</text>`;
  s += `<line class="t2" x1="${x(2)}" x2="${x(2)}" y1="8" y2="62"/><text class="t2lab" x="${x(2) - 6}" y="16" text-anchor="end">${T.meterT2}</text>`;
  if (bar - 2 > 0.05) s += `<line class="bar" x1="${x(bar)}" x2="${x(bar)}" y1="8" y2="62"/><text class="barlab" x="${x(bar) - 6}" y="16" text-anchor="end" dy="${W >= 600 && x(bar) - x(2) < 170 ? 14 : 0}">${W < 600 ? f(bar) : fill(T.meterBest, {N: n, bar: f(bar)})}</text>`;
  // the dot starts at t = 0 and slides to the reading (see .chart .pt.slide; skipped with reduced motion)
  if (t != null) s += `<circle class="pt best slide" cx="${x(0)}" cy="42" r="7" data-dx="${x(Math.max(lo, Math.min(hi, t))) - x(0)}"/>`;
  return s + '</svg>';
 }
 // Luck as odds and as a percentage: "1 in 44" and "2.3%" (both, so either reading works)
 function odds(p) {
  const pct = p >= 0.1 ? (100 * p).toFixed(0) + '%' : p >= 0.01 ? (100 * p).toFixed(1) + '%' : p >= 1e-6 ? (100 * p).toPrecision(2) + '%' : '< 0.0001%';
  if (p >= 0.99) return [T.luck.certain, pct];
  if (p >= 0.5) return [T.luck.most, pct];
  const x = 1 / p, r = x < 100 ? Math.round(x) : Number(x.toPrecision(2));
  const X = T.luck.wan && r >= 1e5 ? fill(T.luck.wan, {W: Number((r / 1e4).toPrecision(2)).toLocaleString('en')})
   : r >= 1e6 && T.luck.million ? fill(T.luck.million, {M: (r / 1e6).toPrecision(2)}) : r.toLocaleString('en');
  return [fill(T.luck.one, {X}), pct];
 }
 const W0 = id => Math.max(300, Math.round(($(id).clientWidth || 520) - 28));
 // The record itself: weekly returns added up (the same returns t is built from), the running
 // peak, the current drawdown shaded, and the freeze date if the wallet is in the frozen cohort.
 function curve(rets, start, frozenMs) {
  const W = W0('wcurve'), H = 190, L = 44, R = 10, Tp = 12, B = 26, C = T.charts;
  const xs = [start], ys = [0];
  for (const [r, dt] of rets) { xs.push(xs[xs.length - 1] + dt * HL.WEEK_MS); ys.push(ys[ys.length - 1] + r); }
  const lo = Math.min(0, ...ys), hi = Math.max(0, ...ys), span = hi - lo || 1;
  const x = t => L + (t - xs[0]) / (xs[xs.length - 1] - xs[0] || 1) * (W - L - R), y = v => Tp + (hi - v) / span * (H - Tp - B);
  let pk = 0;
  ys.forEach((v, i) => { if (v >= ys[pk]) pk = i; });
  const pct = v => (100 * v).toFixed(0) + '%', day = t => new Date(t).toISOString().slice(0, 7);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${C.curveAria}">`;
  for (const v of [lo, 0, hi]) s += `<line class="ax" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text class="lab" x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${pct(v)}</text>`;
  if (pk < ys.length - 1) {  // current drawdown: from the peak to now, between the peak level and the path
   let a = `M${x(xs[pk])} ${y(ys[pk])}`;
   for (let i = pk; i < ys.length; i++) a += `L${x(xs[i])} ${y(ys[i])}`;
   a += `L${x(xs[ys.length - 1])} ${y(ys[pk])}Z`;
   s += `<path class="ddzone" d="${a}"/><line class="t2" x1="${x(xs[pk])}" x2="${W - R}" y1="${y(ys[pk])}" y2="${y(ys[pk])}"/>`;
  }
  if (frozenMs && frozenMs > xs[0] && frozenMs < xs[xs.length - 1]) s += `<line class="frz" x1="${x(frozenMs)}" x2="${x(frozenMs)}" y1="${Tp}" y2="${H - B}"/><text class="lab" x="${x(frozenMs) - 4}" y="${Tp + 10}" text-anchor="end">${C.frozen}</text>`;
  s += `<path class="line" d="${ys.map((v, i) => (i ? 'L' : 'M') + x(xs[i]).toFixed(1) + ' ' + y(v).toFixed(1)).join('')}"/>`;
  s += `<circle class="pk" cx="${x(xs[pk])}" cy="${y(ys[pk])}" r="3.5"/>`;
  s += `<text class="lab" x="${L}" y="${H - 8}">${day(xs[0])}</text><text class="lab" x="${W - R}" y="${H - 8}" text-anchor="end">${day(xs[xs.length - 1])}</text>`;
  return s + '</svg>';
 }
 // How t grows with record length at the measured Sharpe (t ~ Sharpe x sqrt(years)), and when it
 // would reach the two bars. A projection, not a forecast: it assumes the Sharpe holds.
 function projection(sc, bar) {
  const W = W0('wproj'), H = 190, L = 34, R = 10, Tp = 12, B = 26, C = T.charts, S = sc.sharpe, have = sc.weeks / 52;
  const need = y => (y / S) ** 2, cap = 30;
  const end = Math.min(cap, Math.max(have * 1.5, need(bar) * 1.15, 1));
  const top = Math.max(bar + 0.6, S * Math.sqrt(end));
  const x = v => L + v / end * (W - L - R), y = v => Tp + (top - v) / top * (H - Tp - B);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${C.projAria}">`;
  s += `<line class="ax" x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}"/>`;
  s += `<line class="t2" x1="${L}" x2="${W - R}" y1="${y(2)}" y2="${y(2)}"/><text class="t2lab" x="${L - 4}" y="${y(2) + 4}" text-anchor="end">2</text>`;
  const two = bar - 2 > 0.05;  // picked blind, the bar is t = 2 itself
  if (two) s += `<line class="bar" x1="${L}" x2="${W - R}" y1="${y(bar)}" y2="${y(bar)}"/><text class="barlab" x="${L - 4}" y="${y(bar) + 4}" text-anchor="end">${bar.toFixed(1)}</text>`;
  let d = '';
  for (let i = 0; i <= 80; i++) { const v = end * i / 80; d += (i ? 'L' : 'M') + x(v).toFixed(1) + ' ' + y(S * Math.sqrt(v)).toFixed(1); }
  s += `<path class="line proj" d="${d}"/>`;
  const fmt = yrs => yrs * 12 < 24 ? Math.round(yrs * 12) + T.months.mo : yrs.toFixed(1) + T.months.yr;
  for (const [b, cls] of two ? [[2, 't2lab'], [bar, 'barlab']] : [[2, 't2lab']]) {
   const yr = need(b);
   if (yr > have && yr <= end) s += `<circle class="pt" cx="${x(yr)}" cy="${y(b)}" r="3"/><text class="${cls}" x="${Math.min(x(yr), W - R - 2)}" y="${y(b) - 7}" text-anchor="end">${fmt(yr)}</text>`;
  }
  s += `<circle class="pt best" cx="${x(have)}" cy="${y(S * Math.sqrt(have))}" r="5"/><text class="lab" x="${x(have) + 8}" y="${y(S * Math.sqrt(have)) + 4}">${C.now}</text>`;
  s += `<text class="lab" x="${L}" y="${H - 8}">0</text><text class="lab" x="${W - R}" y="${H - 8}" text-anchor="end">${fmt(end)}${need(bar) > cap ? ' →' : ''}</text>`;
  return s + '</svg>';
 }
 let cohort = null;
 const cohortP = fetch('/data/hl/cohort-2026-10-14.json').then(r => r.ok ? r.json() : null).then(j => { cohort = j; }).catch(() => {});
 async function run(a) {
  a = a.trim().toLowerCase();
  if (!/^0x[0-9a-f]{40}$/.test(a)) { $('wout').hidden = false; $('whead').textContent = T.notAddr[0]; $('wsub').textContent = T.notAddr[1]; return; }
  history.replaceState(null, '', T.selfPath + '?a=' + a + (pick ? '&n=' + pick : ''));
  if (await show(a)) {
   // one count per verdict shown: page language only, never the address
   tally(T.countUrl);
  }
 }
 async function show(a) {
  $('wout').hidden = false; $('whead').textContent = T.reading; $('wsub').textContent = ''; $('wflags').innerHTML = '';
  $('wcharts').hidden = true; $('wnextbox').hidden = true; $('wdd').hidden = true; $('wfound').hidden = true;
  $('wid').textContent = a; $('whl').href = 'https://app.hyperliquid.xyz/explorer/address/' + a; $('wvault').hidden = true;
  let pf, vd;
  try { [pf, vd] = await Promise.all([HL.fetchPortfolio(a), HL.fetchVault(a)]); } catch (e) { $('whead').textContent = T.noReach; $('wsub').textContent = String(e.message || e); return; }
  if (!Array.isArray(pf) || !pf.length) { $('whead').textContent = T.noHist; return; }
  // a vault was picked from the vault list, not the trader board
  const vault = vd && vd.name ? vd : null, NN = vault && NV ? NV : N, n = NN.toLocaleString('en'), U = vault && NV ? T.unitVault : T.unitAcct;
  if (vault) {
   $('whl').href = 'https://app.hyperliquid.xyz/vaults/' + a; $('wvault').hidden = false;
   $('wvault').textContent = fill(T.vault, {name: vault.name, lf: f(100 * (vault.leaderFraction || 0), 1), c: f(100 * (vault.leaderCommission || 0), 0)})
    + (NV ? fill(T.vaultBar, {NV: n}) : '');
  }
  const {rets, start, counted, iv} = HL.weeklyReturns(pf), sc = HL.score(rets), fl = HL.flags(pf, rets, counted);
  // the BTC-adjusted t is shown next to the verdict, not in it (until a dated method change)
  let adj = null;
  try { if (sc.t != null) adj = HL.alphaVs(rets, HL.benchReturns(await HL.fetchCandles('BTC', start), iv)); } catch (e) { adj = null; }
  await cohortP;
  const inCohort = cohort && cohort.members.some(m => m.address === a);
  last = {a, rets, start, sc, fl, adj, NN, n, U, vault: !!vault, inCohort, frozenMs: inCohort ? cohort.frozen_at_ms : null};
  pool(); render();
  $('wcopy').dataset.copy = location.origin + T.selfPath + '?a=' + a;
  $('wnote').textContent = start ? fill(T.wnote, {start: new Date(start).toISOString().slice(0, 10), now: new Date().toISOString().slice(0, 16).replace('T', ' ')}) : '';
  return true;
 }
 // "How did you find this wallet?": the pool it was picked from sets the bar. 0 stands for the
 // whole board (or the vault list); the choice goes in the URL as &n= so a shared link keeps it.
 let last = null, pick = (() => { const q = +new URLSearchParams(location.search).get('n'); return [1, 10, 100].includes(q) ? q : 0; })();
 function pool() {
  const F = T.found, L = last;
  $('wfound').innerHTML = `<span class="wfq">${F.q}</span>` + F.opts.map(([k, label]) =>
   `<button type="button" data-n="${k}" aria-pressed="${k === pick}">${fill(label, {N: L.n, U: L.vault && NV ? T.unitVault : T.unitAcct})}</button>`).join('') + `<span class="wfh">${F.hint}</span>`;
  $('wfound').querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
   pick = +b.dataset.n; $('wfound').querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b));
   history.replaceState(null, '', T.selfPath + '?a=' + L.a + (pick ? '&n=' + pick : '')); render();
  }));
 }
 function render() {
  const {rets, start, sc, fl, adj, NN, n, U, inCohort, frozenMs} = last, M = T.months, C = T.charts;
  const NP = pick || NN, opt = T.found.opts.find(o => o[0] === pick), FROM = fill(opt[2], {N: n, U});
  const v = HL.verdict(sc, NP), [title, tag, sub] = T.say[v.key];
  $('whead').textContent = title; $('wtag').innerHTML = `<span class="tag ${tag}">${T.tag[v.key]}</span>`;
  $('wsub').textContent = fill(NP === 1 && v.key === 'clears_board' ? T.found.blindStrong : sub, {BAR: f(v.bar), N: n, U, FROM});
  $('wmeter').innerHTML = meter(sc.t, v.bar, NP.toLocaleString('en'));
  const dot = $('wmeter').querySelector('.slide');
  if (dot) requestAnimationFrame(() => requestAnimationFrame(() => { dot.style.transform = `translateX(${dot.dataset.dx}px)`; }));
  $('wt').textContent = f(sc.t); $('ws').textContent = fill(T.tLabel, {S: f(sc.sharpe)}); $('ww').textContent = sc.weeks ?? '—';
  const lk = HL.luck(sc.t, NP);
  if (lk == null) { $('wl').textContent = '—'; $('wlp').textContent = ''; }
  else { const [o, pc] = odds(lk); $('wl').textContent = o; $('wlp').textContent = pc; }
  $('wl').style.fontSize = lk != null && lk >= 0.5 ? '0.72em' : '';
  $('wll').textContent = fill(T.luck.label, {FROM});
  $('wbtc').hidden = !(adj && adj.t_btc != null);
  if (adj && adj.t_btc != null) $('wbtc').textContent = fill(T.btc, {T: f(adj.t_btc), B: f(adj.beta_btc), N: adj.n_btc});
  const need = HL.monthsToClear(v.bar, sc.sharpe), have = (sc.weeks || 0) / 4.345;
  if (sc.sharpe == null) { $('wm').textContent = '—'; $('wml').textContent = M.noSharpe; }
  else if (need == null) { $('wm').textContent = M.never[0]; $('wml').textContent = M.never[1]; }
  else if (need <= have && v.key === 'clears_board') { $('wm').textContent = '0'; $('wml').textContent = M.done; }
  else if (need <= have) { $('wm').textContent = '< 1' + M.mo; $('wml').textContent = M.more; }
  else { const m = need - have; $('wm').textContent = m >= 1188 ? '> 99' + M.yr : m >= 24 ? (m / 12).toFixed(1) + M.yr : Math.round(m) + M.mo; $('wml').textContent = M.more; }
  $('wflags').innerHTML = fl.map(k => `<li>${T.notes[k]}</li>`).join('');
  // where the record stands against its own peak, and how ordinary that is for its measured edge
  const dd = HL.drawdown(rets), D = T.dd, pc = x => (100 * x).toFixed(1);
  $('wdd').hidden = !dd;
  if (dd) {
   let s = dd.now === 0 ? fill(D.peak, {deep: pc(dd.deepest)}) : fill(D.below, {now: pc(dd.now), wk: dd.weeks_below, deep: pc(dd.deepest)});
   if (dd.now > 0) s += dd.share_if_real == null ? D.noEdge : fill(D.share, {share: dd.share_if_real < 0.01 ? '<1' : Math.round(100 * dd.share_if_real),
     read: dd.share_if_real >= 0.10 ? D.ordinary : dd.share_if_real >= 0.02 ? D.unusual : D.rare});
   $('wddt').textContent = s;
  }
  // charts and what would change the verdict
  $('wcharts').hidden = !(rets.length >= HL.MIN_WEEKS);
  if (rets.length >= HL.MIN_WEEKS) {
   $('wcurvecap').textContent = C.curveCap; $('wcurve').innerHTML = curve(rets, start, frozenMs);
   if (sc.sharpe > 0) { $('wprojcap').textContent = fill(C.projCap, {S: f(sc.sharpe)}); $('wproj').innerHTML = projection(sc, v.bar); }
   else { $('wprojcap').textContent = C.projNone; $('wproj').innerHTML = ''; }
  }
  const nx = [];
  if (sc.sharpe > 0 && need > have) nx.push(fill(C.nextMore, {m: (need - have) > 360 ? C.over30 : (need - have) >= 24 ? ((need - have) / 12).toFixed(1) + M.yr : Math.round(need - have) + M.mo, S: f(sc.sharpe), BAR: f(v.bar)}));
  if (sc.sharpe != null && sc.sharpe <= 0) nx.push(C.nextNoEdge);
  nx.push(inCohort ? C.nextCohort : C.nextNotCohort);
  if (dd && dd.share_if_real != null) nx.push(C.nextDd);
  $('wnext').innerHTML = nx.map(t => `<li>${t}</li>`).join('');
  $('wnextbox').hidden = sc.t == null;
  $('wfound').hidden = sc.t == null;
 }
 $('wform').addEventListener('submit', e => { e.preventDefault(); run($('waddr').value); });
 // a click from a result to the sample memo: the one step on this site toward asking for a memo
 document.querySelectorAll('.wcta a').forEach(l => l.addEventListener('click', () => tally(T.countUrl.replace('k=web', l.href.includes('/memo/') ? 'k=memo' : 'k=ask'))));
 document.querySelectorAll('[data-ex]').forEach(b => b.addEventListener('click', () => { $('waddr').value = b.dataset.ex; run(b.dataset.ex); }));
 const q = new URLSearchParams(location.search).get('a'); if (q) { $('waddr').value = q; run(q); }
})();
