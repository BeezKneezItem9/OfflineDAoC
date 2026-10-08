// Allakhazam (camelot.allakhazam.com) full period archive - runs as a Web Worker inside a camelot.allakhazam.com tab
// (the site refuses scripts outside a browser). Owner 2026-10-07: keep everything for Classic, Shrouded Isles and Trials
// of Atlantis - every quest page with all dialogue and comments, every monster of the period zones, every item they or
// the quests link. Pages are stored in IndexedDB "zamarchive" (store "pages"); a second tab hands them to the local
// receiver (walk_receiver.py -> allakhazam-live/<kind>.jsonl.gz). Polite: one request at a time, ~3.5 s apart, 15-minute
// pause when the CDN starts refusing. Resumes from its saved queue.
// No backticks in this file: it is injected as a string.
var DELAY = 3500, PAUSE = 15 * 60 * 1000;
var PERIOD_EXP = { '': 1, 'Shrouded Isle expansion': 1, 'Trials of Atlantis expansion': 1 };
var db, state = { queues: [[], [], [], [], []], seen: {}, done: 0, fail: 0, paused: 0, phase: 'start' };
function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
function openDb() {
  return new Promise(function (res, rej) {
    var q = indexedDB.open('zamarchive', 1);
    q.onupgradeneeded = function () {
      var d = q.result;
      d.createObjectStore('pages', { keyPath: 'seq', autoIncrement: true });
      d.createObjectStore('state');
    };
    q.onsuccess = function () { res(q.result); };
    q.onerror = function () { rej(q.error); };
  });
}
function tx(store, mode, fn) {
  return new Promise(function (res, rej) {
    var t = db.transaction(store, mode), out = fn(t.objectStore(store));
    t.oncomplete = function () { res(out && out.result); };
    t.onerror = function () { rej(t.error); };
  });
}
function save() { return tx('state', 'readwrite', function (s) { return s.put(state, 'crawl'); }); }
function load() { return tx('state', 'readonly', function (s) { return s.get('crawl'); }); }
function add(prio, url, kind, meta) {
  if (state.seen[url]) return;
  state.seen[url] = 1;
  state.queues[prio].push([url, kind, meta || null]);
}
function unesc(s) { return s.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>'); }
function strip(html) {
  var i = html.indexOf('id="col-main-inner-3"'), j = html.indexOf('id="buffer-bottom"');
  var body = i > 0 ? html.slice(html.lastIndexOf('<', i), j > i ? html.lastIndexOf('<', j) : undefined) : html;
  return body.replace(/<script[\s\S]*?<\/script>/gi, '').replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '').replace(/<noscript[\s\S]*?<\/noscript>/gi, '')
    .replace(/<ins[\s\S]*?<\/ins>/gi, '').replace(/<div id="AKZ_[^"]*"[^>]*><\/div>/g, '');
}
function links(html, base) {
  var out = [], re = /href\s*=\s*"([^"]+)"/gi, m;
  while ((m = re.exec(html))) {
    try { out.push(new URL(unesc(m[1]), base)); } catch (e) {}
  }
  return out;
}
function discover(kind, url, html) {
  links(html, url).forEach(function (u) {
    if (u.host !== 'camelot.allakhazam.com') return;
    var p = u.pathname, s = u.searchParams;
    if (/search\.html$/.test(p) && s.get('cmob') && kind !== 'mob') add(3, '/db/search.html?cmob=' + s.get('cmob'), 'mob');
    else if (/item\.html$/.test(p) && s.get('citem') && kind !== 'item') add(/^quest/.test(kind) ? 1 : 4, '/item.html?citem=' + s.get('citem'), 'item');  // quest items before monsters
    else if (/zones\.html$/.test(p) && s.get('czone') && +s.get('czone') <= 161) add(2, '/zones.html?czone=' + s.get('czone'), 'zoneinfo');
    // further pages of a page's player comments
    if (s.get('p') && +s.get('p') > 1 && !s.get('post') && !s.get('replyto')) add(1, p + u.search, kind + '_comments');
  });
}
function questList(html, realm) {
  var rows = html.split(/<tr class="(?:lr|dr)">/).slice(1), n = 0;
  rows.forEach(function (row) {
    var exp = (row.match(/<img[^>]*title="([^"]*)"/) || [, ''])[1];
    var id = (row.match(/cquest=(\d+)/) || [])[1];
    var tds = row.split(/<td[^>]*>/).map(function (t) { return t.replace(/<[^>]+>/g, '').trim(); });
    var type = tds[5] || '';
    if (!id || !PERIOD_EXP[exp] || type === 'Champion') return;
    add(1, '/quests.html?realm=' + realm + '&cquest=' + id, 'quest', { exp: exp || 'Classic', type: type });
    n++;
  });
  return n;
}
async function fetchPage(url) {
  for (;;) {
    var r;
    try { r = await fetch('https://camelot.allakhazam.com' + url, { credentials: 'include' }); } catch (e) { r = null; }
    if (r && (r.status === 200 || r.status === 404)) return { status: r.status, html: await r.text() };
    state.paused++; state.phase = 'paused ' + (r ? r.status : 'network') + ' ' + new Date().toISOString();
    postMessage(state.phase); await save(); await sleep(PAUSE);
  }
}
async function run() {
  db = await openDb();
  var old = await load();
  if (old) state = old;
  if (!old) {
    var realms = ['Albion', 'Midgard', 'Hibernia'];
    for (var k = 0; k < realms.length; k++) {
      var page = await fetchPage('/quests.html?realm=' + realms[k]);
      await tx('pages', 'readwrite', function (s) { return s.add({ kind: 'zam_questlist', url: '/quests.html?realm=' + realms[k], status: page.status, fetched: new Date().toISOString(), html: strip(page.html) }); });
      questList(page.html, realms[k]);
      await sleep(DELAY);
    }
    var zones = await fetchPage('/db/mobsbyzone.html');
    await tx('pages', 'readwrite', function (s) { return s.add({ kind: 'zam_zonelist', url: '/db/mobsbyzone.html', status: zones.status, fetched: new Date().toISOString(), html: strip(zones.html) }); });
    links(zones.html, 'https://camelot.allakhazam.com/db/mobsbyzone.html').forEach(function (u) {
      var z = u.searchParams.get('cmzone');
      if (z && +z <= 161) add(2, '/db/search.html?cmzone=' + z, 'zone');
    });
    await save();
  }
  state.phase = 'crawling';
  for (;;) {
    var item = null;
    for (var q = 0; q < state.queues.length && !item; q++) if (state.queues[q].length) item = state.queues[q].shift();
    if (!item) break;
    var res = await fetchPage(item[0]);
    var rec = { kind: 'zam_' + item[1], url: item[0], status: res.status, fetched: new Date().toISOString(), meta: item[2],
                title: (res.html.match(/<title>([\s\S]*?)<\/title>/) || [, ''])[1].trim(), html: strip(res.html) };
    await tx('pages', 'readwrite', function (s) { return s.add(rec); });
    if (res.status === 200) discover(item[1], 'https://camelot.allakhazam.com' + item[0], rec.html);
    state.done++;
    if (state.done % 25 === 0) { await save(); postMessage('done ' + state.done + ' queued ' + state.queues.map(function (x) { return x.length; }).join('/')); }
    await sleep(DELAY + Math.random() * 1000);
  }
  state.phase = 'finished'; await save(); postMessage('finished ' + state.done);
}
run().catch(function (e) { state.phase = 'error ' + e; postMessage('error ' + e); });
