/* ===== STORE: the page's memory, in this browser's database (25 Oct 2026) =====
   The user's 10/25 backup held 298 card rows and 2,171 props: 11.5 MB as the
   browser counts it, and localStorage stops at 10 MB in Chrome (5 MB in Safari).
   The props save had been failing quietly for a day, and the morning the page
   "showed nothing from 10/24 and would not change the date" was that wall. The
   card, the props and the slate now live in IndexedDB, which holds hundreds of
   megabytes; the draft and the table view stay in localStorage. The page reads
   through a cache filled before its own code runs, so every read stays
   synchronous; a write updates the cache and goes to the database behind it.
   Whatever the old keys still hold in localStorage moves over on the first load
   and is cleared from there. No IndexedDB (an old private window): localStorage
   carries on as before. */
var smStore = (function () {
  var DB = "callsheet3", OS = "kv", BIG = ["callsheet3.card.v1", "callsheet3.props.v1", "callsheet3.slate.v1"];
  var cache = {}, db = null, why = "";
  function tx(mode, fn) {
    return new Promise(function (res, rej) {
      if (!db) return res();
      var t;
      try { t = db.transaction(OS, mode); } catch (e) { return rej(e); }
      t.oncomplete = function () { res(); };
      t.onerror = t.onabort = function () { rej(t.error || new Error("the write did not finish")); };
      fn(t.objectStore(OS));
    });
  }
  function fail(e) {
    why = String((e && e.message) || e || "storage failed");
    var el = document.getElementById("saveState");
    if (el) el.textContent = "this browser is not storing anything: " + why;
  }
  var ready = new Promise(function (res) {
    var rq;
    try { rq = indexedDB.open(DB, 1); } catch (e) { why = String(e); return res(); }
    rq.onupgradeneeded = function () { rq.result.createObjectStore(OS); };
    rq.onerror = rq.onblocked = function () { why = String(rq.error || "blocked"); res(); };
    rq.onsuccess = function () {
      db = rq.result;
      db.onversionchange = function () { db.close(); db = null; };
      var c;
      try { c = db.transaction(OS, "readonly").objectStore(OS).openCursor(); } catch (e) { why = String(e); db = null; return res(); }
      c.onsuccess = function () { var cur = c.result; if (cur) { cache[cur.key] = cur.value; cur.continue(); } else res(); };
      c.onerror = function () { why = String(c.error); db = null; res(); };
    };
  }).then(function () {
    if (!db) return;
    /* the move from localStorage, once: what the database already holds is newer, so it wins */
    var moved = [];
    BIG.forEach(function (k) {
      var v = null;
      try { v = localStorage.getItem(k); } catch (e) {}
      if (v === null) return;
      if (cache[k] === undefined) { cache[k] = v; moved.push(k); }
      try { localStorage.removeItem(k); } catch (e) {}
    });
    if (moved.length) return tx("readwrite", function (s) { moved.forEach(function (k) { s.put(cache[k], k); }); }).catch(fail);
  }).then(function () {
    try { if (navigator.storage && navigator.storage.persist) navigator.storage.persist(); } catch (e) {}
  });
  function big(k) { return !!db && BIG.indexOf(k) >= 0; }
  return {
    ready: ready,
    backend: function () { return db ? "indexeddb" : "localstorage"; },
    why: function () { return why; },
    getItem: function (k) { if (big(k)) return cache[k] === undefined ? null : cache[k]; return localStorage.getItem(k); },
    setItem: function (k, v) {
      v = String(v);
      if (big(k)) { cache[k] = v; return tx("readwrite", function (s) { s.put(v, k); }).catch(fail); }
      localStorage.setItem(k, v);
      return Promise.resolve();
    },
    removeItem: function (k) {
      if (big(k)) { delete cache[k]; return tx("readwrite", function (s) { s.delete(k); }).catch(fail); }
      localStorage.removeItem(k);
      return Promise.resolve();
    },
    clear: function () {
      cache = {};
      try { localStorage.clear(); } catch (e) {}
      return tx("readwrite", function (s) { s.clear(); }).catch(fail);
    }
  };
})();
