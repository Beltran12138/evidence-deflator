// Claim check: paste a performance claim (a tweet, a deck line, a fund factsheet sentence), read the
// numbers out of it, and say how much evidence they could carry. The reading is deterministic and
// shown field by field so the user can correct it; nothing is sent anywhere. The page sets
// window.CLAIM = {T} (strings). Needs hl.js (HL.bar, HL.luck).
(() => {
 const {T} = window.CLAIM, $ = id => document.getElementById(id);
 const num = s => s == null ? null : Number(String(s).replace(/,/g, ''));
 const pick = (txt, res) => { for (const re of res) { const m = txt.match(re); if (m) return m; } return null; };
 const N = '(-?\\d[\\d,]*(?:\\.\\d+)?)';
 const R = (src, f = 'i') => new RegExp(src, f);

 function extract(txt) {
  const t = txt.replace(/[＋]/g, '+').replace(/[％]/g, '%').replace(/[，]/g, ', ').replace(/[：]/g, ': ');
  const out = {};
  let m = pick(t, [R(`(?:sharpe(?: ratio)?|夏普(?:比率)?)\\D{0,12}?${N}`)]);
  if (m) out.sharpe = num(m[1]);
  m = pick(t, [R(`(?:annual(?:ized|ised)?(?: return)?|cagr|apy|apr|per year|a year|年化(?:收益(?:率)?)?)\\D{0,15}?\\+?${N}\\s*%`),
               R(`\\+?${N}\\s*%\\s*(?:a year|per year|annual(?:ly|ized|ised)?|年化|每年)`)]);
  if (m) out.annual = num(m[1]) / 100;
  m = pick(t, [R(`(?:volatility|vol\\.?|stdev|波动率|年化波动)\\D{0,12}?${N}\\s*%`)]);
  if (m) out.vol = num(m[1]) / 100;
  m = pick(t, [R(`(?:max(?:imum)? drawdown|mdd|最大回撤|回撤)\\D{0,12}?-?${N}\\s*%`)]);
  if (m) out.mdd = Math.abs(num(m[1])) / 100;
  m = pick(t, [R(`(?:total(?: return)?|cumulative|累计(?:收益)?|总收益|\\bup|gained|涨了|赚了|收益)\\D{0,12}?\\+?${N}\\s*%`)]);
  if (m) out.total = num(m[1]) / 100;
  // length: explicit years / months / days, or a year range
  m = pick(t, [R(`${N}\\s*(?:years?|yrs?|年(?!化))`)]);
  if (m && num(m[1]) <= 80) out.years = num(m[1]);
  if (out.years == null) { m = pick(t, [R(`${N}\\s*(?:months?|mos?|个月)`)]); if (m) out.years = num(m[1]) / 12; }
  if (out.years == null) { m = pick(t, [R(`${N}\\s*(?:days?|天|日)(?!内)`)]); if (m) out.years = num(m[1]) / 365; }
  if (out.years == null) {
   m = t.match(/((?:19|20)\d\d)\s*(?:年)?\s*(?:-|–|—|to|至|到)\s*((?:19|20)\d\d)/);
   if (m) out.years = Math.max(num(m[2]) - num(m[1]), 0) || null;
  }
  if (out.years == null) {  // "since 2023": from the start of that year to today
   m = t.match(/(?:since|from|自|从)\s*((?:19|20)\d\d)/i);
   if (m) { const y = (Date.now() - Date.UTC(num(m[1]), 0, 1)) / (365.25 * 864e5); if (y > 0 && y < 80) out.years = y; }
  }
  // how many were tried
  m = pick(t, [R(`${N}\\s*(?:strateg(?:y|ies)|variants?|parameter sets?|configurations?|models?|backtests?|个策略|组参数|种参数|套参数|个模型|个版本|次回测)`),
               R(`(?:out of|best of)\\s*${N}`), R(`从\\s*${N}\\s*(?:个|种|组|套)`)]);
  if (m && num(m[1]) > 1) out.trials = num(m[1]);
  out.backtest = /backtest|back-test|simulat|回测|模拟/i.test(t);
  out.live = /\blive\b|real money|audited|实盘|真金白银|审计/i.test(t);
  if (out.annual == null && out.total != null && out.years) out.annual = Math.pow(1 + out.total, 1 / out.years) - 1;
  return out;
 }

 const fmt = (x, d = 2) => x == null || !isFinite(x) ? '' : String(Math.round(x * 10 ** d) / 10 ** d);
 function fill(s, o) { return s.replace(/\{(\w+)\}/g, (m, k) => k in o ? o[k] : m); }

 function fields(x) {
  const rows = [['sharpe', fmt(x.sharpe)], ['annual', x.annual == null ? '' : fmt(100 * x.annual, 1)], ['vol', x.vol == null ? '' : fmt(100 * x.vol, 1)],
                ['mdd', x.mdd == null ? '' : fmt(100 * x.mdd, 1)], ['years', fmt(x.years, 2)], ['trials', x.trials == null ? '' : String(x.trials)]];
  $('cfields').innerHTML = rows.map(([k, v]) => `<label class="cf"><span>${T.f[k]}</span><input data-k="${k}" value="${v}" inputmode="decimal" placeholder="—"></label>`).join('');
  $('cfields').querySelectorAll('input').forEach(i => i.addEventListener('input', score));
 }

 function read() {
  const v = {};
  $('cfields').querySelectorAll('input').forEach(i => { const s = i.value.trim(); v[i.dataset.k] = s === '' ? null : Number(s); });
  return v;
 }

 function score() {
  const v = read(), miss = [];
  let S = v.sharpe, how = T.how.given;
  if (S == null && v.annual != null && v.vol) { S = v.annual / v.vol; how = T.how.derived; }
  if (S == null) miss.push(v.annual != null && v.mdd != null ? T.miss.ddNotVol : T.miss.sharpe);
  if (v.years == null) miss.push(T.miss.years);
  if (v.trials == null) miss.push(T.miss.trials);
  if (last.backtest && !last.live) miss.push(T.miss.backtest);
  const n = v.trials && v.trials > 1 ? v.trials : 1, bar = HL.bar(n);
  let head = T.verdict.incomplete, cls = 'tag-grey', body = '';
  if (S != null && v.years != null) {
   const t = S * Math.sqrt(v.years), need = (bar / S) ** 2, lk = HL.luck(t, n);
   const key = t >= bar && n > 1 ? 'strong' : t >= bar || t >= 2 ? (n > 1 ? 'promising' : 'strong1') : t <= -2 ? 'loses' : 'luck';
   head = T.verdict[key]; cls = {strong: 'tag-green', strong1: 'tag-amber', promising: 'tag-amber', luck: 'tag-red', loses: 'tag-red'}[key];
   body = fill(T.body, {S: fmt(S), HOW: how, Y: fmt(v.years, 1), T: fmt(t), BAR: fmt(bar), N: n.toLocaleString('en'),
                        L: lk >= 0.5 ? T.likely : fill(T.one, {X: Math.round(1 / lk).toLocaleString('en')}),
                        NEED: S > 0 ? (need >= 2 ? fmt(need, 1) + T.yr : Math.round(need * 12) + T.mo) : T.never});
  }
  else if (v.years != null && v.years > 0) {  // length but no Sharpe: say what Sharpe the length would need
   body = fill(n > 1 ? T.needS : T.needS1, {Y: fmt(v.years, 1), NS: fmt(2 / Math.sqrt(v.years)), BAR: fmt(bar),
                                            N: n.toLocaleString('en'), NSB: fmt(bar / Math.sqrt(v.years))});
  }
  $('cverdict').innerHTML = `<span class="tag ${cls}">${head}</span>`;
  $('cbody').textContent = body;
  $('cmiss').innerHTML = miss.map(s => `<li>${s}</li>`).join('');
  $('cmissbox').hidden = !miss.length;
 }

 let last = {};
 function run() {
  last = extract($('ctext').value);
  $('cout').hidden = false;
  fields(last);
  score();
 }
 $('cform').addEventListener('submit', e => { e.preventDefault(); run(); });
 document.querySelectorAll('[data-claim]').forEach(b => b.addEventListener('click', () => { $('ctext').value = b.dataset.claim; run(); }));
 const q = typeof location !== 'undefined' && new URLSearchParams(location.search).get('q');
 if (q) { $('ctext').value = q; run(); }
 if (typeof module !== 'undefined') module.exports = {extract};
})();
