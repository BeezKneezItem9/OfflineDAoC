// Hand-off of the archive worker's pages (IndexedDB "zamarchive") to the local receiver, run in a SECOND
// camelot.allakhazam.com tab (the form post navigates that tab away; the worker tab must keep running).
// 1) zamHandoff(15e6) posts the next unsent records (up to ~15 MB) to http://127.0.0.1:8766/ (walk_receiver.py), which
//    appends them to allakhazam-live/<kind>.jsonl.gz and logs {"n", "first", "last"} in handoff.log.
// 2) After handoff.log shows the batch, navigate this tab back to the site and run zamConfirm(last) to delete the
//    saved records from IndexedDB and remember the position.
async function openZam() {
  return new Promise((res, rej) => { const q = indexedDB.open('zamarchive', 1); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); });
}
async function zamHandoff(maxBytes) {
  const db = await openZam();
  const sent = +localStorage.getItem('__zamSent') || 0;
  const recs = []; let bytes = 0;
  await new Promise((res, rej) => {
    const cur = db.transaction('pages', 'readonly').objectStore('pages').openCursor(IDBKeyRange.lowerBound(sent, true));
    cur.onsuccess = () => {
      const c = cur.result; if (!c) return res();
      const s = JSON.stringify(c.value);
      if (bytes + s.length > maxBytes && recs.length) return res();
      recs.push(c.value); bytes += s.length; c.continue();
    };
    cur.onerror = () => rej(cur.error);
  });
  if (!recs.length) return 'nothing new';
  const last = recs[recs.length - 1].seq;
  localStorage.setItem('__zamPending', String(last));
  const f = document.createElement('form');
  f.method = 'POST'; f.action = 'http://127.0.0.1:8766/'; f.enctype = 'text/plain';
  const i = document.createElement('input'); i.type = 'hidden'; i.name = 'd'; i.value = JSON.stringify(recs);
  f.appendChild(i); document.body.appendChild(f);
  setTimeout(() => f.submit(), 50);
  return 'posting ' + recs.length + ' records seq ' + recs[0].seq + '-' + last + ' bytes ' + bytes;
}
async function zamConfirm(lastSaved) {
  if ((+localStorage.getItem('__zamPending') || 0) !== lastSaved) return 'mismatch';
  const db = await openZam();
  await new Promise((res, rej) => {
    const t = db.transaction('pages', 'readwrite');
    t.objectStore('pages').delete(IDBKeyRange.upperBound(lastSaved));
    t.oncomplete = res; t.onerror = () => rej(t.error);
  });
  localStorage.setItem('__zamSent', String(lastSaved)); localStorage.removeItem('__zamPending');
  return 'confirmed through ' + lastSaved;
}
