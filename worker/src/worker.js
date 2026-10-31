// Evidence Deflator API: remote MCP (Streamable HTTP, stateless) and a JSON endpoint.
// Built by tools/build_worker.py, which prepends docs/assets/hl.js, so `HL` is the same
// scoring the browser runs. src/hl_wallet.py is the Python twin; tools/check_worker.py diffs them.
//
//   GET  /api/wallet?a=0x...&picked_from=47153   -> JSON verdict
//   POST /mcp                                     -> MCP JSON-RPC (initialize, tools/list, tools/call)
//   POST /tg                                      -> Telegram bot webhook (secret header required)

const SITE = 'https://evidencedeflator.com';
const SERVER = {name: 'evidence-deflator', version: '0.3.0'};
const ADDR = /^0x[0-9a-fA-F]{40}$/;
const SOURCE = 'Hyperliquid public info API, portfolio allTime (accountValueHistory, pnlHistory)';

function verdict(sc, pickedFrom) {
  // Same keys and bars as verdict() in src/hl_wallet.py.
  const board = pickedFrom && pickedFrom > 1;
  const bar = board ? HL.bar(pickedFrom) : 2;
  const t = sc.t;
  let key;
  if (t == null) key = 'too_short';
  else if (board && t >= bar) key = 'clears_board';
  else if (t >= 2) key = 'clears_single';
  else if (t <= -2) key = 'loses';
  else key = 'luck';
  return {key, bar: Math.round(bar * 100) / 100};
}

const day = ms => (ms == null ? null : new Date(ms).toISOString().slice(0, 10));

function checkWallet(address, pickedFrom, pf) {
  const w = HL.weeklyReturns(pf), sc = HL.score(w.rets), v = verdict(sc, pickedFrom);
  const months = sc.sharpe ? HL.monthsToClear(v.bar, sc.sharpe) : null;
  const have = sc.t != null ? (sc.weeks || 0) / 4.345 : 0;
  return {
    address, ...sc, verdict: v.key, bar: v.bar,
    // For a caller that gates on the result with a fixed rule rather than reading the prose.
    clears_bar: sc.t != null && sc.t >= v.bar,
    bar_rule: pickedFrom && pickedFrom > 1 ? `best of ${pickedFrom}: t >= ${v.bar}` : 'picked blind: t >= 2',
    picked_from: pickedFrom ?? null,
    months_more_to_clear: months == null ? null : Math.round(Math.max(months - have, 0) * 10) / 10,
    luck_one_in: sc.t == null ? null : Math.round(10 / HL.luck(sc.t, pickedFrom || 1)) / 10,
    flags: HL.flags(pf, w.rets, w.counted),
    history_from: day(w.start), history_to: day(w.end),
    page: `${SITE}/wallet/?a=${address}`,
  };
}

async function walletFromApi(address, pickedFrom) {
  if (!ADDR.test(address || '')) throw new RangeError('address must be 0x followed by 40 hex characters');
  const pf = await HL.fetchPortfolio(address.toLowerCase());
  if (!Array.isArray(pf) || !pf.length) throw new RangeError('no portfolio history for ' + address);
  return {...checkWallet(address.toLowerCase(), pickedFrom, pf), source: SOURCE,
          fetched_at: new Date().toISOString().slice(0, 19) + 'Z', method_url: SITE + '/method/'};
}

const TOOL = {
  name: 'hyperliquid_wallet',
  title: 'Hyperliquid wallet: skill or luck?',
  description:
    "Is this Hyperliquid wallet's record skill, or could it be luck? Call before recommending, ranking or copying a " +
    'Hyperliquid trader, or when a PnL or leaderboard rank is cited as evidence. Scores weekly returns from public ' +
    'history (PnL-based, so deposits do not count; covers perps and spot incl. HIP-4 outcomes, not HyperEVM). ' +
    'Ask how the user found the wallet: if from a leaderboard, pass ' +
    'its size as picked_from (Hyperliquid ranks about 47,000 accounts); omitting it drops the bar from about 4.9 to 2. ' +
    'Verdicts: too_short (say "cannot tell yet", not "no skill"), luck, clears_single, clears_board, loses. ' +
    'Always report the flags with the verdict. A past record is not the user\'s future returns. ' +
    'To gate an action on the result with a fixed rule, read clears_bar (t at or above bar, stated in bar_rule), ' +
    'not the prose; source, fetched_at and history_from/history_to say what data it rests on.',
  inputSchema: {
    type: 'object',
    properties: {
      address: {type: 'string', description: 'Wallet address, 0x followed by 40 hex characters'},
      picked_from: {type: 'integer', minimum: 1, description: 'How many wallets it was chosen from (leaderboard size if found on one)'},
    },
    required: ['address'],
  },
  outputSchema: {
    type: 'object',
    properties: {
      address: {type: 'string'},
      verdict: {type: 'string', enum: ['too_short', 'luck', 'clears_single', 'clears_board', 'loses']},
      t: {type: ['number', 'null']}, sharpe: {type: ['number', 'null']}, weeks: {type: ['integer', 'null']},
      bar: {type: 'number'}, clears_bar: {type: 'boolean'}, bar_rule: {type: 'string'},
      picked_from: {type: ['integer', 'null']}, luck_one_in: {type: ['number', 'null']},
      months_more_to_clear: {type: ['number', 'null']}, flags: {type: 'array', items: {type: 'string'}},
      history_from: {type: ['string', 'null']}, history_to: {type: ['string', 'null']},
      source: {type: 'string'}, fetched_at: {type: 'string'}, method_url: {type: 'string'}, page: {type: 'string'},
    },
    required: ['address', 'verdict', 't', 'bar', 'clears_bar', 'bar_rule', 'flags', 'source', 'fetched_at'],
  },
  annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true},
};

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Accept, Mcp-Session-Id, Mcp-Protocol-Version',
};
const json = (body, status = 200) =>
  new Response(JSON.stringify(body, null, 2), {status, headers: {'Content-Type': 'application/json', ...CORS}});

// One data point per completed check, for a daily count: which surface ran it and, for the web
// page, its language. 'memo' / 'ask' are clicks from a result to the sample memo / to request one. src is 'team'
// when the browser was marked as ours (visit any page with ?team=1), so our own testing can be
// subtracted. MCP checks also carry the calling software's name (clientName below). No address, no IP,
// nothing about the person calling (see /privacy/).
const KINDS = new Set(['web', 'pm', 'memo', 'ask', 'api', 'mcp', 'tg']), LANGS = new Set(['en', 'zh-hans', 'zh-hant', '']), SRCS = new Set(['', 'team']);
function count(env, kind, lang = '', src = '', client = '') {
  if (!env.COUNTS || !KINDS.has(kind) || !LANGS.has(lang) || !SRCS.has(src)) return;
  try { env.COUNTS.writeDataPoint({blobs: [kind, lang, src, client], doubles: [1], indexes: [kind]}); } catch {}
}

// For MCP checks only: the calling software's name, the first word of its User-Agent ("openai-mcp/1.0
// (...)" -> "openai-mcp"), so ChatGPT and Claude calls can be told apart. A product name, not a person:
// no version, no platform details, no IP.
function clientName(request) {
  const first = (request.headers.get('user-agent') || '').trim().split(/[\s/;(]/)[0] || '';
  return first.toLowerCase().replace(/[^a-z0-9._-]/g, '').slice(0, 32) || 'none';
}

async function rpc(msg, env = {}, client = '') {
  const {id, method, params} = msg;
  const ok = result => ({jsonrpc: '2.0', id, result});
  const err = (code, message) => ({jsonrpc: '2.0', id, error: {code, message}});
  if (method === 'initialize') {
    return ok({protocolVersion: params?.protocolVersion || '2025-06-18', capabilities: {tools: {}}, serverInfo: SERVER,
               instructions: 'Evidence checks for trading records. Docs: ' + SITE + '/method/'});
  }
  if (method === 'ping') return ok({});
  if (method === 'tools/list') return ok({tools: [TOOL]});
  if (method === 'tools/call') {
    if (params?.name !== TOOL.name) return err(-32602, 'unknown tool: ' + params?.name);
    const a = params.arguments || {};
    try {
      const r = await walletFromApi(a.address, a.picked_from);
      count(env, 'mcp', '', '', client);
      return ok({content: [{type: 'text', text: JSON.stringify(r, null, 2)}], structuredContent: r, isError: false});
    } catch (e) {
      return ok({content: [{type: 'text', text: String(e.message || e)}], isError: true});
    }
  }
  return err(-32601, 'method not found: ' + method);
}

// ---- Telegram bot: send a Hyperliquid address, get the verdict back. Nothing is stored; the
// only trace is one tally (kind 'tg') like every other check.
const SAY = {
  loses: 'Losing, and not by chance',
  luck: 'Looks like luck',
  clears_single: 'Promising, not proven (passes t = 2, not the leaderboard bar)',
  clears_board: 'Strong evidence (clears the leaderboard bar)',
  too_short: 'Too early to tell (under 8 measurable weeks)',
};
const FLAG_TEXT = {
  no_losing_week: 'No losing week: consistent with market making or selling tail risk.',
  one_week_majority: 'One week produced more than half the gains.',
  pnl_outside_record: 'Most PnL was booked on a near-empty account; t covers only the measurable weeks.',
};
let boardCache = null;
async function boardSizes() {
  if (boardCache && Date.now() - boardCache.at < 6 * 3600e3) return boardCache;
  const s = {at: Date.now(), accounts: 47039, vaults: 9477};
  try {
    const d = await (await fetch(SITE + '/data/hl/latest.json')).json();
    s.accounts = d.boards.pnl.ranked_from || s.accounts;
    if (d.vaults && d.vaults.listed) s.vaults = d.vaults.listed;
  } catch {}
  return (boardCache = s);
}

async function tgReply(env, chatId, text) {
  await fetch(`https://api.telegram.org/bot${env.TG_TOKEN}/sendMessage`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({chat_id: chatId, text, disable_web_page_preview: true}),
  });
}

async function telegram(env, chatId, text) {
  const m = text.match(/0x[0-9a-fA-F]{40}/);
  if (!m) {
    return tgReply(env, chatId, 'Send a Hyperliquid wallet or vault address (0x… 40 hex characters) and I will tell you whether its record can be told apart from luck, allowing for it having been picked off a leaderboard.\n\nMethod: ' + SITE + '/method/\nNothing you send is stored.');
  }
  const addr = m[0].toLowerCase();
  try {
    const [pf, vd, sizes] = await Promise.all([HL.fetchPortfolio(addr), HL.fetchVault(addr), boardSizes()]);
    if (!Array.isArray(pf) || !pf.length) return tgReply(env, chatId, 'No Hyperliquid history for ' + addr);
    const vault = vd && vd.name ? vd : null, n = vault ? sizes.vaults : sizes.accounts;
    const r = checkWallet(addr, n, pf);
    const lines = [
      SAY[r.verdict] + (vault ? ` (vault: ${vault.name})` : ''),
      `t ${r.t == null ? '—' : r.t.toFixed(2)} · bar ${r.bar.toFixed(2)} (best of ${n.toLocaleString('en')} ${vault ? 'vaults' : 'accounts'}) · ${r.weeks ?? 0} weeks`,
      ...(r.luck_one_in == null ? [] : [`Luck alone, among ${n.toLocaleString('en')}: ${r.luck_one_in <= 1.02 ? 'almost certain' : r.luck_one_in < 2 ? 'more likely than not' : '1 in ' + Math.round(r.luck_one_in).toLocaleString('en')}`]),
      ...r.flags.map(k => '• ' + (FLAG_TEXT[k] || k)),
      '',
      'Full check: ' + r.page,
    ];
    count(env, 'tg');
    return tgReply(env, chatId, lines.join('\n'));
  } catch (e) {
    return tgReply(env, chatId, 'Could not reach Hyperliquid right now. Try again in a minute.');
  }
}

async function handle(request, env = {}) {
  const url = new URL(request.url);
  if (request.method === 'OPTIONS') return new Response(null, {status: 204, headers: CORS});

  // OpenAI plugin directory domain check: serve exactly the token the portal issued (a plain var, not a secret).
  if (url.pathname === '/.well-known/openai-apps-challenge') {
    return env.OPENAI_APPS_CHALLENGE ? new Response(env.OPENAI_APPS_CHALLENGE, {headers: {'Content-Type': 'text/plain'}}) : json({error: 'not found'}, 404);
  }

  if (url.pathname === '/api/wallet' && request.method === 'GET') {
    const pf = url.searchParams.get('picked_from');
    try {
      const r = await walletFromApi(url.searchParams.get('a') || url.searchParams.get('address'), pf ? parseInt(pf, 10) : null);
      count(env, 'api');
      return json(r);
    } catch (e) {
      return json({error: String(e.message || e)}, e instanceof RangeError ? 400 : 502);
    }
  }

  // The wallet pages (Hyperliquid and Polymarket) check in the browser; after showing a verdict they report it here (kind and language only).
  if (url.pathname === '/api/count' && request.method === 'POST') {
    const k = url.searchParams.get('k');  // 'web' / 'pm' = a verdict on the Hyperliquid / Polymarket page, 'memo' = a click to the sample memo
    if (k === 'web' || k === 'pm' || k === 'memo' || k === 'ask') count(env, k, url.searchParams.get('l') || '', url.searchParams.get('s') || '');
    return new Response(null, {status: 204, headers: CORS});
  }

  if (url.pathname === '/mcp') {
    if (request.method !== 'POST') return new Response('Use POST (MCP Streamable HTTP, stateless).', {status: 405, headers: {Allow: 'POST', ...CORS}});
    let body;
    try { body = await request.json(); } catch { return json({jsonrpc: '2.0', id: null, error: {code: -32700, message: 'parse error'}}, 400); }
    const batch = Array.isArray(body) ? body : [body];
    const replies = [];
    const client = clientName(request);
    for (const m of batch) if (m && m.id !== undefined && m.method) replies.push(await rpc(m, env, client));
    if (!replies.length) return new Response(null, {status: 202, headers: CORS});  // notifications only
    return json(Array.isArray(body) ? replies : replies[0]);
  }

  // Telegram bot webhook. Telegram sends the secret set with setWebhook in a header; anything
  // without it is dropped. The token and the secret are Worker secrets (wrangler secret put).
  // One-time setup: point the bot's webhook here, using the token the Worker already holds, so the
  // token never has to be typed into a shell. Guarded by the same secret Telegram will send back.
  if (url.pathname === '/tg/setup' && request.method === 'POST') {
    if (!env.TG_TOKEN || !env.TG_WEBHOOK_SECRET || request.headers.get('X-Setup-Secret') !== env.TG_WEBHOOK_SECRET) return json({error: 'not found'}, 404);
    const r = await fetch(`https://api.telegram.org/bot${env.TG_TOKEN}/setWebhook`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: url.origin + '/tg', secret_token: env.TG_WEBHOOK_SECRET, allowed_updates: ['message']}),
    });
    const info = await (await fetch(`https://api.telegram.org/bot${env.TG_TOKEN}/getWebhookInfo`)).json();
    const me = await (await fetch(`https://api.telegram.org/bot${env.TG_TOKEN}/getMe`)).json();
    return json({setWebhook: await r.json(), webhook: {url: info.result && info.result.url, pending: info.result && info.result.pending_update_count,
                 last_error: info.result && info.result.last_error_message}, bot: me.result && me.result.username});
  }

  if (url.pathname === '/tg' && request.method === 'POST') {
    if (!env.TG_TOKEN || request.headers.get('X-Telegram-Bot-Api-Secret-Token') !== env.TG_WEBHOOK_SECRET) return json({error: 'not found'}, 404);
    let update;
    try { update = await request.json(); } catch { return new Response('ok'); }
    const msg = update.message || update.channel_post;
    if (msg && msg.chat && typeof msg.text === 'string') await telegram(env, msg.chat.id, msg.text);
    return new Response('ok');  // always 200, or Telegram retries
  }

  if (url.pathname === '/') {
    return json({service: 'Evidence Deflator API', mcp: url.origin + '/mcp', wallet: url.origin + '/api/wallet?a=0x...',
                 docs: SITE + '/api/', source: 'https://github.com/Beltran12138/evidence-deflator'});
  }
  return json({error: 'not found'}, 404);
}

export default {fetch: handle};
export {checkWallet, verdict, rpc};
