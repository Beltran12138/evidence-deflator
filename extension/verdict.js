// Shared rendering for the popup and the page panel: one result object in, HTML out.
const ED_VIEW = (() => {
  const SAY = {  // same labels as the site (tools/build_site.py WALLET_T_EN)
    loses: ['Losing, and not by chance', 'red', 't is −2 or lower: it lost too consistently for luck to explain.'],
    luck: ['Looks like luck', 'red', 't is below 2: a record like this turns up by chance often enough that it says little about skill.'],
    clears_single: ['Promising, not proven', 'amber', 'Strong enough if picked blind: luck alone gets that far about 1 time in 44. Found among {N} {U}, it needs t ≥ {BAR}.'],
    clears_board: ['Strong evidence', 'green', 'Clears t ≥ {BAR}, the bar for being picked from {N} {U}.'],
    too_short: ['Too early to tell', 'grey', 'Fewer than 8 weeks of record that can be measured. Not a verdict on the trader.'],
  };
  const TAG = {loses: 'losing', luck: 'looks like luck', clears_single: 'promising', clears_board: 'strong', too_short: 'too early'};
  // luck as odds and a percentage, as on the site
  const odds = p => {
    if (p == null) return ['—', ''];
    const pct = p >= 0.1 ? (100 * p).toFixed(0) + '%' : p >= 0.01 ? (100 * p).toFixed(1) + '%' : p >= 1e-6 ? (100 * p).toPrecision(2) + '%' : '< 0.0001%';
    if (p >= 0.99) return ['almost certain', pct];
    if (p >= 0.5) return ['more likely than not', pct];
    const x = 1 / p, r = x < 100 ? Math.round(x) : Number(x.toPrecision(2));
    const u = [[1e12, ' trillion'], [1e9, ' billion'], [1e6, ' million']].find(([d]) => r >= d);
    return [u ? `1 in ${Number((r / u[0]).toPrecision(2))}${u[1]}` : '1 in ' + r.toLocaleString('en'), pct];
  };
  const FLAGS = {no_losing_week: 'No losing week: consistent with market making or selling tail risk.',
                 one_week_majority: 'One week produced more than half the gains.',
                 pnl_outside_record: 'Most PnL was booked on a near-empty account; t covers only the measurable weeks.'};
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const f = (x, d = 2) => x == null ? '—' : Number(x).toFixed(d);

  function html(r) {
    if (r.error) return `<div class="ed-h">Could not check</div><div class="ed-s">${esc(r.error)}</div>`;
    const [title, tone, sub] = SAY[r.verdict];
    const n = Number(r.n).toLocaleString('en');
    let months = '—';
    if (r.sharpe != null && r.months != null) {
      const more = Math.max(r.months - (r.weeks || 0) / 4.345, 0);
      months = more === 0 ? '0' : more >= 1188 ? '> 99 yr' : more >= 24 ? (more / 12).toFixed(1) + ' yr' : Math.round(more) + ' mo';
    } else if (r.sharpe != null) months = 'never';
    const [lo, lp] = odds(r.luck);
    return `<div class="ed-tag ed-${tone}">${esc(TAG[r.verdict] || r.verdict)}</div>
<div class="ed-h">${esc(title)}</div>
${r.name ? `<div class="ed-s">Vault: ${esc(r.name)}</div>` : ''}
<div class="ed-s">${esc(sub.replace('{BAR}', f(r.bar)).replace('{N}', n).replace('{U}', r.unit))}</div>
<div class="ed-grid"><div><b>${esc(lo)}</b><span>${esc(lp)} · luck alone, among ${esc(n)}</span></div><div><b>${f(r.t)}</b><span>t · bar ${f(r.bar)}</span></div>
<div><b>${r.weeks ?? '—'}</b><span>weeks</span></div><div><b>${months}</b><span>more to clear</span></div></div>
${(r.flags || []).map(k => `<div class="ed-flag">${esc(FLAGS[k] || k)}</div>`).join('')}
${r.note ? `<div class="ed-flag">${esc(r.note)}</div>` : ''}
<a class="ed-link" href="${esc(r.link)}" target="_blank" rel="noopener">How this is computed →</a>`;
  }

  const CSS = `.ed-tag{display:inline-block;font:600 11px/1 system-ui;text-transform:uppercase;letter-spacing:.04em;padding:4px 7px;border-radius:4px;margin-bottom:8px}
.ed-red{background:#fbe4df;color:#a5321a}.ed-amber{background:#fbf0d6;color:#8a5a00}.ed-green{background:#dff3e4;color:#1d6b35}.ed-grey{background:#eceae5;color:#555}
.ed-h{font:600 16px/1.3 Georgia,serif;margin:0 0 6px}.ed-s{font:13px/1.45 system-ui;color:#555;margin:0 0 8px}
.ed-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0}.ed-grid div{background:#f4f2ee;border-radius:6px;padding:8px}
.ed-grid b{display:block;font:600 18px/1.1 ui-monospace,Consolas,monospace}.ed-grid span{font:11px system-ui;color:#666}
.ed-flag{font:12px/1.4 system-ui;color:#444;border-left:3px solid #e66a4b;padding-left:8px;margin:6px 0}
.ed-link{display:inline-block;margin-top:6px;font:13px system-ui;color:#15171c}`;
  return {html, CSS};
})();
