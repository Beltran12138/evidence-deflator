/* Rules from choices, for owners who cannot say their limits as numbers. Instead of asking "how much risk
   can you take?", show concrete orders and ask "let it through, or stop it?"; a few answers per rule
   narrow the limit by bisection over a fixed ladder. Choices carry preferences better than descriptions
   (arXiv 2603.29317: "as few as two sufficing to match prompts' predictive value").
   Every limit cites the answers it came from. Deterministic, no model; tests/test_mandate_choices.py
   replays answers through the Python rule check and requires every answered order to get the owner's
   decision under the rules produced. */
(function (root) {
  var LADDERS = {
    max_order_usd: [100, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000],
    max_daily_loss_usd: [50, 100, 150, 200, 300, 500, 750, 1000, 1500, 2000],
    max_position_usd: [500, 1000, 1500, 2000, 3000, 5000, 7500, 10000, 15000, 20000]
  };
  var ORDER = ['max_order_usd', 'max_daily_loss_usd', 'max_position_usd'];
  function money(x) { return '$' + Math.round(x).toLocaleString('en-US'); }

  // lo: highest ladder index answered "allow"; hi: lowest answered "block". Answers between them are all
  // the search ever asks, so they cannot contradict each other.
  function bounds(field, answers) {
    var L = LADDERS[field], lo = -1, hi = L.length;
    (answers || []).forEach(function (a) {
      var i = L.indexOf(a.amount);
      if (i < 0) return;
      if (a.allow) lo = Math.max(lo, i); else hi = Math.min(hi, i);
    });
    return { lo: lo, hi: hi };
  }
  function nextAmount(field, answers) {
    var b = bounds(field, answers);
    if (b.hi - b.lo <= 1) return null;
    return LADDERS[field][(b.lo + b.hi) >> 1];
  }
  // The order a question shows. The small order in the loss and position questions stays under the
  // single-order limit already chosen, so only the rule being asked about can stop it.
  function question(field, amount, symbol, orderCap) {
    var sym = symbol || 'AAPL';
    var small = Math.min(orderCap || 100, 100);
    if (field === 'max_order_usd')
      return { text_zh: 'AI 想一次买 ' + money(amount) + ' 的 ' + sym + '。',
               order: { symbol: sym, side: 'buy', usd: amount }, situation: { position_usd: 0, loss_today: 0, orders_today: 0 } };
    if (field === 'max_daily_loss_usd')
      return { text_zh: '今天已经亏了 ' + money(amount) + '，AI 还想再买 ' + money(small) + ' 的 ' + sym + '。',
               order: { symbol: sym, side: 'buy', usd: small }, situation: { position_usd: 0, loss_today: amount, orders_today: 0 } };
    return { text_zh: '你已经持有 ' + money(amount) + ' 的 ' + sym + '，AI 想再买 ' + money(small) + '。',
             order: { symbol: sym, side: 'buy', usd: small }, situation: { position_usd: amount, loss_today: 0, orders_today: 0 } };
  }
  // The next question to ask, or null when every rule is settled.
  function next(state) {
    for (var k = 0; k < ORDER.length; k++) {
      var f = ORDER[k];
      if (f !== 'max_order_usd' && result(state).scope.max_order_usd == null) return null;
      var a = nextAmount(f, state.answers[f]);
      if (a != null) return { field: f, amount: a, q: question(f, a, state.symbol, result(state).scope.max_order_usd) };
    }
    return null;
  }
  function said(field, answers) {
    return (answers || []).slice().sort(function (x, y) { return x.amount - y.amount; }).map(function (a) {
      return money(a.amount) + (a.allow ? ' 放行' : ' 拦下');
    }).join('、');
  }
  // Rules from the answers so far. Single order: the largest amount let through. Daily loss and
  // position: the smallest level stopped (the gate stops at or past the daily-loss limit, and when the
  // position would go above the position limit). Both agree with every answer; the owner's true limit
  // lies within one ladder step, and the cited answers show which step.
  function result(state) {
    var scope = {}, cites = [], notes = [];
    ORDER.forEach(function (f) {
      var ans = state.answers[f] || [], L = LADDERS[f], b = bounds(f, ans);
      if (b.hi - b.lo > 1) return;
      var v = null;
      if (f === 'max_order_usd') {
        if (b.lo >= 0) v = L[b.lo]; else notes.push('order_all_blocked');
        if (b.hi === L.length) notes.push('order_all_allowed');
      } else {
        if (b.hi < L.length) v = L[b.hi]; else notes.push(f + '_all_allowed');
      }
      if (v != null) { scope[f] = v; cites.push({ field: f, value: v, words: said(f, ans) }); }
    });
    if (state.allow && state.allow.length) {
      scope.allow = state.allow.map(function (s) { return String(s).toUpperCase(); });
      cites.unshift({ field: 'allow', value: scope.allow, words: '你勾选的' });
    }
    return { scope: scope, cites: cites, notes: notes };
  }
  function start(symbol, allow) { return { symbol: symbol || (allow && allow[0]) || 'AAPL', allow: allow || [], answers: {} }; }
  function answer(state, field, amount, allow) {
    (state.answers[field] = state.answers[field] || []).push({ amount: amount, allow: !!allow });
    return state;
  }

  var api = { LADDERS: LADDERS, start: start, next: next, answer: answer, result: result, question: question };
  root.mandateChoices = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
