/* Evidence Deflator — the evidence ranking as a scatter: record length (log scale) against t after the
   market, with lines of equal Sharpe (t ≈ Sharpe × √years) and the two bars. Used by /ranking/ and the
   Macau deck. RankPlot.mount(el, {rows, bar, barN, lang, labels, highlight, animate, font}) → {setFilter}.
   rows: [{id, group, name, who, z, years}]; records without a length in years are left out of the plot. */
(function (g) {
  'use strict';
  const GC = { markets: '#3B6BB5', press: '#8E6BC4', clones: '#8E959E', crypto: '#2E9A7A', ai: '#C46A8A' };
  const T = {
    en: { x: 'Length of record, years (log scale)', y: 't after the market', s: 'Sharpe', blind: 'picked blind · 2',
          best: n => `best of ${n} · `, yr: ' yr', luck: 'Luck alone, picked blind: ',
          groups: { markets: 'Stocks and funds', press: 'Hedge funds, as reported', clones: '13F estimates', crypto: 'Crypto' } },
    zh: { x: '记录长度（年，对数刻度）', y: '扣掉大盘后的 t', s: '夏普', blind: '随手挑一份 · 2',
          best: n => `${n} 里挑第一 · `, yr: ' 年', luck: '随手挑中时，单靠运气做到的概率：',
          groups: { markets: '美股与基金', press: '对冲基金（媒体报道）', clones: '13F 估算', crypto: '加密' } },
  };
  // Upper tail of the standard normal, 1 − Φ(x), with small relative error far into the tail (Numerical Recipes erfcc).
  function tail(x) {
    const z = Math.abs(x) / Math.SQRT2, t = 1 / (1 + 0.5 * z);
    const r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 +
      t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))));
    return x >= 0 ? r / 2 : 1 - r / 2;
  }
  function odds(z, lang) {
    const x = 1 / tail(z), f = v => Number(v.toPrecision(2)).toLocaleString('en-US');
    if (x < 2) return lang === 'zh' ? '超过一半' : 'more likely than not';
    if (lang === 'zh') return '1/' + (x >= 1e8 ? f(x / 1e8) + ' 亿' : x >= 1e4 ? f(x / 1e4) + ' 万' : f(x));
    return '1 in ' + (x >= 1e12 ? f(x / 1e12) + ' trillion' : x >= 1e9 ? f(x / 1e9) + ' billion' : x >= 1e6 ? f(x / 1e6) + ' million' : f(x));
  }
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function mount(el, o) {
    const L = T[o.lang === 'zh' ? 'zh' : 'en'], fs = o.font || 12;
    const rows = o.rows.filter(r => r.z != null && r.years > 0);
    const W = o.width || 960, H = o.height || 480, m = { l: fs * 3.4, r: fs * 1.5, t: fs * 1.5, b: fs * 3.6 };
    const x0 = 0.15, x1 = 80, y0 = Math.min(-3, Math.floor(Math.min(...rows.map(r => r.z)) - 0.5)),
      y1 = Math.max(7.5, Math.ceil(Math.max(...rows.map(r => r.z)) + 0.5));
    const X = v => m.l + (Math.log(v) - Math.log(x0)) / (Math.log(x1) - Math.log(x0)) * (W - m.l - m.r);
    const Y = v => m.t + (y1 - v) / (y1 - y0) * (H - m.t - m.b);
    const hl = new Set(o.highlight || Object.keys(o.labels || {}));
    let s = `<style>.rp text{font-family:var(--mono,'JetBrains Mono',Consolas,monospace);font-size:${fs}px;fill:var(--muted,#7A766D)}
.rp .grid{stroke:var(--rule,#E3DFD5);stroke-width:1}.rp .iso{stroke:var(--faint,#B9B3A6);stroke-width:1;stroke-dasharray:2 4;fill:none}
.rp .b2{stroke:var(--ink-2,#55524B);stroke-width:1.2;stroke-dasharray:5 5}.rp .bb{stroke:var(--accent,#B8361F);stroke-width:2}
.rp circle{stroke:var(--bg,#fff);stroke-width:1.2;transition:opacity .35s,transform .45s cubic-bezier(.2,.9,.3,1.3);transform-box:fill-box;transform-origin:center;cursor:pointer}
.rp circle.pre{opacity:0;transform:scale(0)}.rp .dim{opacity:.1}.rp .lab{fill:var(--ink,#17171B);font-weight:700}
.rp-tip{position:absolute;pointer-events:none;background:var(--surface,#fff);border:1px solid var(--rule,#E3DFD5);padding:8px 10px;font-size:${Math.max(12, fs - 1)}px;line-height:1.45;max-width:300px;box-shadow:0 2px 10px rgba(0,0,0,.08);z-index:5;color:var(--ink,#17171B)}
.rp-leg{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:${Math.max(12, fs - 1)}px;color:var(--ink-2,#55524B);margin-top:4px}.rp-leg i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}</style>`;
    // grid and axes
    for (const v of [0.25, 0.5, 1, 2, 5, 10, 20, 50]) s += `<line class="grid" x1="${X(v)}" x2="${X(v)}" y1="${m.t}" y2="${H - m.b}"/><text x="${X(v)}" y="${H - m.b + fs * 1.4}" text-anchor="middle">${v}</text>`;
    for (let v = Math.ceil(y0); v <= y1; v++) s += `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}"${v === 0 ? ' style="stroke:var(--ink-2,#55524B);stroke-width:1"' : ''}/><text x="${m.l - 8}" y="${Y(v) + fs * 0.35}" text-anchor="end">${v}</text>`;
    s += `<text x="${(m.l + W - m.r) / 2}" y="${H - fs * 0.6}" text-anchor="middle">${L.x}</text><text transform="translate(${fs},${(m.t + H - m.b) / 2}) rotate(-90)" text-anchor="middle">${L.y}</text>`;
    // lines of equal Sharpe: t = s·√years
    for (const k of [0.25, 0.5, 1, 2, 4]) {
      const pts = []; for (let i = 0; i <= 60; i++) { const v = x0 * Math.pow(x1 / x0, i / 60), t = k * Math.sqrt(v); if (t <= y1) pts.push([X(v), Y(t)]); }
      const e = pts[pts.length - 1];
      s += `<polyline class="iso" points="${pts.map(p => p.join(',')).join(' ')}"/><text x="${e[0] - 4}" y="${e[1] + (e[1] <= m.t + 2 ? fs * 1.1 : -4)}" text-anchor="end" style="fill:var(--faint,#B9B3A6)">${L.s} ${k}</text>`;
    }
    s += `<line class="b2" x1="${m.l}" x2="${W - m.r}" y1="${Y(2)}" y2="${Y(2)}"/><text x="${m.l + 6}" y="${Y(2) - 5}" style="fill:var(--ink-2,#55524B)">${L.blind}</text>`;
    s += `<line class="bb" x1="${m.l}" x2="${W - m.r}" y1="${Y(o.bar)}" y2="${Y(o.bar)}"/><text x="${m.l + 6}" y="${Y(o.bar) - 5}" style="fill:var(--accent,#B8361F)">${L.best(Number(o.barN).toLocaleString('en-US'))}${o.bar.toFixed(2)}</text>`;
    // points: shortest records first, so the animation reads left to right
    const order = rows.map((r, i) => i).sort((a, b) => rows[a].years - rows[b].years);
    for (const i of order) {
      const r = rows[i], big = hl.has(r.id);
      s += `<circle data-i="${i}" data-g="${r.group}" cx="${X(r.years)}" cy="${Y(r.z)}" r="${big ? fs * 0.55 : fs * 0.4}" fill="${GC[r.group] || '#888'}"${o.animate ? ' class="pre"' : ''}/>`;
    }
    for (const id in (o.labels || {})) {
      const r = rows.find(x => x.id === id); if (!r) continue;
      const [txt, dx = 9, dy = 4, an = 'start'] = [].concat(o.labels[id]);
      s += `<text class="lab" data-g="${r.group}" x="${X(r.years) + dx}" y="${Y(r.z) + dy}" text-anchor="${an}"${o.animate ? ' style="opacity:0;transition:opacity .4s"' : ''}>${esc(txt)}</text>`;
    }
    const groups = [...new Set(rows.map(r => r.group))];
    el.style.position = 'relative';
    el.innerHTML = `<div style="overflow-x:auto"><svg class="rp" viewBox="0 0 ${W} ${H}" width="100%" style="min-width:${o.minWidth || 0}px;display:block" role="img" aria-label="${esc(L.y)} / ${esc(L.x)}">${s}</svg></div>` +
      `<div class="rp-leg">${groups.map(k => `<span><i style="background:${GC[k]}"></i>${esc(L.groups[k] || k)}</span>`).join('')}</div><div class="rp-tip" hidden></div>`;
    const svg = el.querySelector('svg'), tip = el.querySelector('.rp-tip');
    svg.addEventListener('pointerover', e => {
      const c = e.target.closest('circle'); if (!c) return;
      const r = rows[+c.dataset.i];
      tip.innerHTML = `<b>${esc(r.name)}</b>${r.who ? `<br><span style="color:var(--muted,#7A766D)">${esc(r.who)}</span>` : ''}<br>t ${r.z.toFixed(2)} · ${r.years.toFixed(1)}${L.yr}<br>${L.luck}${odds(r.z, o.lang)}`;
      tip.hidden = false;
      const b = el.getBoundingClientRect(), cb = c.getBoundingClientRect();
      const left = cb.left - b.left + 14, top = cb.top - b.top - 10;
      tip.style.left = Math.min(left, b.width - 310) + 'px'; tip.style.top = top + 'px';
    });
    svg.addEventListener('pointerout', e => { if (e.target.closest('circle')) tip.hidden = true; });
    if (o.animate) {
      const cs = [...svg.querySelectorAll('circle.pre')], reduce = matchMedia('(prefers-reduced-motion: reduce)').matches, step = reduce ? 0 : Math.min(30, 1800 / cs.length);
      cs.forEach((c, k) => setTimeout(() => c.classList.remove('pre'), 150 + k * step));
      setTimeout(() => svg.querySelectorAll('.lab').forEach(t => t.style.opacity = 1), 250 + cs.length * step);
    }
    return {
      setFilter(f) { svg.querySelectorAll('circle,.lab').forEach(n => n.classList.toggle('dim', f !== 'all' && n.dataset.g !== f)); },
      count: rows.length,
    };
  }
  g.RankPlot = { mount, odds, tail };
})(typeof window !== 'undefined' ? window : globalThis);
