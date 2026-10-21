/* One sentence in, a mandate scope out, with no language model. A port of src/mandate_text.py;
   tests/test_mandate_text.py runs both on the same sentences and compares. Every field cites the
   words it came from; what could not be read is reported, never guessed. */
(function (root) {
  var NAMES = { '苹果': 'AAPL', '特斯拉': 'TSLA', '英伟达': 'NVDA', '微软': 'MSFT', '谷歌': 'GOOGL', '亚马逊': 'AMZN',
    '脸书': 'META', '奈飞': 'NFLX', '台积电': 'TSM', '标普500': 'SPY', '标普': 'SPY', '纳指': 'QQQ',
    '纳斯达克': 'QQQ', '比特币': 'BTC', '以太坊': 'ETH', '以太币': 'ETH' };
  var NOT_TICKERS = ['AI', 'USD', 'OK', 'I', 'A', 'MAX', 'PER', 'ETF', 'AND', 'OR', 'NO', 'THE', 'FOR', 'DAY'];
  var CN_DIGITS = { '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9 };
  var CN_UNITS = { '十': 10, '百': 100, '千': 1000, '万': 10000 };
  var NUM = '(\\$?\\s*\\d(?:[\\d,]*\\d)?(?:\\.\\d+)?\\s*[万千kK]?|[零一二两三四五六七八九十百千万]+)';
  var GAP = '[^\\d$零一二两三四五六七八九十百千万，,；;。]';
  var EGAP = '[^\\d$，,；;。]';
  var CLAUSE = /(?:[^，,；;。\n]|,(?=\d))+/g;

  function cnNumber(s) {
    var total = 0, section = 0, digit = null;
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      if (ch in CN_DIGITS) digit = CN_DIGITS[ch];
      else if (ch in CN_UNITS) {
        var unit = CN_UNITS[ch];
        if (unit === 10000) { total += (section + (digit || 0)) * 10000; section = 0; digit = null; }
        else { section += (digit === null ? 1 : digit) * unit; digit = null; }
      } else return null;
    }
    var rest = digit || 0;
    if (digit !== null && s.length >= 2 && (s[s.length - 2] in CN_UNITS) && s[s.length - 2] !== '十')
      rest = Math.floor(digit * CN_UNITS[s[s.length - 2]] / 10);
    return total + section + rest;
  }
  function toNumber(tok) {
    var t = tok.replace(/[$, ]/g, '');
    if (!t) return null;
    if (/^[零一二两三四五六七八九十百千万]+$/.test(t)) return cnNumber(t);
    var mult = 1, last = t[t.length - 1];
    if (last === '万') { mult = 10000; t = t.slice(0, -1); }
    else if ('千kK'.indexOf(last) >= 0) { mult = 1000; t = t.slice(0, -1); }
    if (!/^\d+(\.\d+)?$/.test(t)) return null;
    return Number(t) * mult;
  }
  function int2(x) { return Number.isInteger(x) ? x : Math.round(x * 100) / 100; }

  var PATTERNS = [
    ['max_orders_per_day', '(?:一天|每天|每日|单日|当天)' + GAP + '{0,6}?' + NUM + '\\s*(?:笔|单|次)', ''],
    ['max_orders_per_day', NUM + '\\s*(?:orders?|trades?)\\s*(?:a|per|each)\\s*day', 'i'],
    ['max_daily_loss_usd', '(?:一天|每天|每日|单日|日内|当天)' + GAP + '{0,6}?亏(?:损|钱)?' + GAP + '{0,6}?' + NUM, ''],
    ['max_daily_loss_usd', '日亏(?:损)?' + GAP + '{0,6}?' + NUM, ''],
    ['max_daily_loss_usd', '(?:lose|loss(?:es)?)' + EGAP + '{0,20}?' + NUM + '\\s*(?:a|per|each|in a)\\s*day', 'i'],
    ['max_daily_loss_usd', 'daily loss' + EGAP + '{0,15}?' + NUM, 'i'],
    ['max_order_usd', '(?:单笔|每笔|一笔|每单|单次|每次下单)' + GAP + '{0,8}?' + NUM, ''],
    ['max_order_usd', NUM + '\\s*(?:usd|dollars?)?\\s*(?:per|each|a)\\s*(?:order|trade)', 'i'],
    ['max_order_usd', '(?:per|each|single|any one)\\s*(?:order|trade)' + EGAP + '{0,15}?' + NUM, 'i'],
    ['max_position_usd', '(?:每只|每个|单只|单个|每支|单支|每种|单一)(?:股票|标的|币|品种)?' + GAP + '{0,8}?' + NUM, ''],
    ['max_position_usd', '(?:仓位|持仓)' + GAP + '{0,6}?' + NUM, ''],
    ['max_position_usd', '(?:position|per (?:stock|symbol|ticker|coin))' + EGAP + '{0,20}?' + NUM, 'i']
  ];
  var VALIDITY = [
    ['有效期?' + GAP + '{0,3}?' + NUM + '\\s*(天|日|周|星期|个?月)', ''],
    [NUM + '\\s*(天|日|周|星期|个?月)\\s*(?:内)?有效', ''],
    ['(?:valid\\s*)?for\\s*' + NUM + '\\s*(days?|weeks?|months?)', 'i']
  ];
  var NO_SHORT = /(不做空|不许做空|不能做空|别做空|不要做空|禁止做空|只做多|不卖空|no short(?:ing|s)?|long only)/i;
  var NEGATE = /(不要|别|不许|不准|禁止|不碰|不做|除了|no |not |avoid )/;

  function parse(text, defaultDays) {
    if (defaultDays === undefined) defaultDays = 14;
    var found = {}, cites = [], used = [];
    function take(field, value, m) {
      if (field in found) return;
      found[field] = value;
      cites.push({ field: field, value: value, words: m[0].trim() });
      used.push([m.index, m.index + m[0].length]);
    }
    function inUsed(i) { return used.some(function (u) { return u[0] <= i && i < u[1]; }); }

    PATTERNS.forEach(function (p) {
      var re = new RegExp(p[1], p[2] + 'g'), m;
      while ((m = re.exec(text)) !== null) {
        if (m[0].length === 0) { re.lastIndex++; continue; }
        if (inUsed(m.index)) continue;
        var v = toNumber(m[1]);
        if (v === null || !(v > 0)) continue;
        take(p[0], int2(v), m);
        break;
      }
    });
    for (var k = 0; k < VALIDITY.length; k++) {
      var vm = new RegExp(VALIDITY[k][0], VALIDITY[k][1]).exec(text);
      if (vm) {
        var n = toNumber(vm[1]), unit = vm[2].toLowerCase();
        if (n) {
          var days = n * ('周星w'.indexOf(unit[0]) >= 0 ? 7 : (unit.indexOf('月') >= 0 || unit.indexOf('month') === 0) ? 30 : 1);
          take('days', int2(days), vm);
          break;
        }
      }
    }
    var ns = NO_SHORT.exec(text);
    if (ns) take('sides', ['buy'], ns);

    var symbols = [], denied = [], spots = [], m2;
    var names = Object.keys(NAMES).sort(function (a, b) { return b.length - a.length; });
    var nre = new RegExp(names.join('|'), 'g');
    while ((m2 = nre.exec(text)) !== null) spots.push([m2.index, m2.index + m2[0].length, NAMES[m2[0]]]);
    var tre = /(?<![A-Za-z])[A-Z]{1,5}(?![A-Za-z])/g;
    while ((m2 = tre.exec(text)) !== null) if (NOT_TICKERS.indexOf(m2[0]) < 0) spots.push([m2.index, m2.index + m2[0].length, m2[0]]);
    spots.sort(function (x, y) { return x[0] - y[0] || x[1] - y[1] || (x[2] < y[2] ? -1 : x[2] > y[2] ? 1 : 0); });
    spots.forEach(function (sp) {
      var before = text.slice(Math.max(0, sp[0] - 6), sp[0]);
      var cs = Math.max.apply(null, '，,；;。'.split('').map(function (c) { return before.lastIndexOf(c); })) + 1;
      if (NEGATE.test(before.slice(cs))) denied.push(sp[2]);
      else if (symbols.indexOf(sp[2]) < 0) symbols.push(sp[2]);
      used.push([sp[0], sp[1]]);
    });
    if (symbols.length) {
      found.allow = symbols;
      cites.push({ field: 'allow', value: symbols,
                   words: spots.filter(function (sp) { return symbols.indexOf(sp[2]) >= 0; })
                               .map(function (sp) { return text.slice(sp[0], sp[1]); }).join('、') });
    }

    var missing = [];
    if (!('allow' in found)) missing.push('allow');
    ['max_order_usd', 'max_daily_loss_usd', 'max_position_usd'].forEach(function (f) { if (!(f in found)) missing.push(f); });
    var notes = [];
    if (denied.length) notes.push('denied_symbols:' + denied.join(','));
    if (!('days' in found)) { found.days = int2(defaultDays); notes.push('default_days'); }

    var unread = [], cm;
    CLAUSE.lastIndex = 0;
    while ((cm = CLAUSE.exec(text)) !== null) {
      var a = cm.index, b = a + cm[0].length;
      if (!used.some(function (u) { return u[0] < b && u[1] > a; }) && /[\w一-鿿]/.test(cm[0])) unread.push(cm[0].trim());
    }
    var scope = {};
    Object.keys(found).forEach(function (f) { if (f !== 'days') scope[f] = found[f]; });
    return { scope: scope, days: found.days, cites: cites, missing: missing, notes: notes, unread: unread };
  }

  root.mandateText = { parse: parse };
  if (typeof module !== 'undefined') module.exports = { parse: parse, cnNumber: cnNumber, toNumber: toNumber };
})(typeof window !== 'undefined' ? window : globalThis);
