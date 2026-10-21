// Browser API test doubles, not real GPS. No Node packages or browser install needed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../gps_device/index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function setup({secure = true} = {}) {
  const elements = {};
  for (const match of html.matchAll(/id="([^"]+)"/g)) elements[match[1]] = {textContent:'', value:'', disabled:false};
  elements.bus.value = 'PHONE_TEST'; elements.route.value = 'SAMPLE_R1'; elements.trip.value = 'SAMPLE_T1';
  const watches = [], uploads = [], cleared = [], intervals = new Set();
  let transport = async () => ({ok:true, status:200, json:async () => ({route_verified:true, route_data_source:'SAMPLE'})});
  const sandbox = {
    document: {getElementById: id => elements[id]},
    window: {isSecureContext:secure, addEventListener() {}}, location:{protocol:'https:'},
    navigator:{geolocation:{watchPosition(success, error) {watches.push({success, error}); return watches.length;}, clearWatch(id) {cleared.push(id);}}},
    Date, Number, String, Object, Math, AbortController,
    setTimeout:() => 1, clearTimeout() {},
    setInterval(callback) {intervals.add(callback); return callback;}, clearInterval(callback) {intervals.delete(callback);},
    fetch:async (_, options) => {uploads.push(JSON.parse(options.body)); return transport(options);}
  };
  vm.createContext(sandbox); vm.runInContext(script, sandbox);
  return {elements, watches, uploads, cleared, intervals,
    start:() => elements.start.onclick(), stop:() => elements.stop.onclick(),
    send:() => vm.runInContext('send()', sandbox),
    retryNow:() => vm.runInContext('retryAt = 0', sandbox),
    transport: fn => {transport = fn;},
    fix(changes = {}, index = watches.length - 1) {
      watches[index].success({timestamp:Date.now(), coords:{latitude:13, longitude:80, accuracy:5, speed:null, heading:null, ...changes}});
    }
  };
}

async function main() {
  let tests = 0;
  {
    const h = setup({secure:false}); h.start();
    assert.equal(h.watches.length, 0); assert.match(h.elements.status.textContent, /HTTPS/); tests++;
  }
  {
    const h = setup(); h.start(); h.start();
    assert.equal(h.watches.length, 1); assert.equal(h.intervals.size, 1);
    h.fix(); await h.send();
    assert.equal(h.uploads[0].source, 'REAL_PHONE_GPS');
    assert.equal(h.uploads[0].accuracy, 5); assert.equal(h.uploads[0].speed, null);
    assert.equal(h.uploads[0].heading, null); assert.equal(h.elements.count.textContent, '1');
    await h.send(); assert.equal(h.uploads.length, 1);
    h.stop(); assert.equal(h.cleared.length, 1); assert.equal(h.intervals.size, 0);
    h.fix({latitude:14}); await h.send(); assert.equal(h.uploads.length, 1); tests++;
  }
  {
    const h = setup(); h.start(); h.watches[0].error({code:1, message:'denied'});
    assert.equal(h.elements.permission.textContent, 'Denied'); assert.equal(h.intervals.size, 0); tests++;
  }
  {
    const h = setup(); h.start(); h.fix({accuracy:250, speed:2, heading:90});
    assert.match(h.elements.quality.textContent, /Weak accuracy/); await h.send();
    assert.equal(h.uploads[0].accuracy, 250); assert.equal(h.elements.heading.textContent, '90.0');
    h.watches[0].error({code:2, message:'unavailable'}); await h.send();
    assert.equal(h.uploads.length, 1); assert.match(h.elements.status.textContent, /unavailable/); tests++;
  }
  {
    const h = setup(); h.start(); h.fix();
    h.transport(async () => {throw Error('offline');}); await h.send();
    assert.match(h.elements.status.textContent, /retry in 3s/); assert.equal(h.elements.count.textContent, '0');
    await h.send(); assert.equal(h.uploads.length, 1);
    h.retryNow(); h.transport(async () => ({ok:true, status:200, json:async () => ({route_verified:false})}));
    await h.send(); assert.equal(h.uploads.length, 2); assert.equal(h.elements.count.textContent, '1'); tests++;
  }
  {
    const h = setup(); h.start(); h.fix({latitude:91}); await h.send();
    assert.equal(h.uploads.length, 0); assert.match(h.elements.quality.textContent, /Invalid/);
    h.stop(); h.start(); h.fix({latitude:14}, 0); await h.send();
    assert.equal(h.uploads.length, 0); // Obsolete watcher cannot feed the new session.
    h.fix(); h.transport(async () => ({status:409, ok:false, text:async () => 'bus ID conflict'}));
    await h.send(); assert.equal(h.intervals.size, 0); assert.match(h.elements.status.textContent, /rejected/); tests++;
  }
  {
    const h = setup(); h.start(); h.fix();
    let resolve;
    h.transport(() => new Promise(r => {resolve = r;}));
    const pending = h.send(); h.stop(); h.start();
    resolve({ok:true, status:200, json:async () => ({route_verified:true})}); await pending;
    assert.equal(h.elements.count.textContent, '0'); // Late response must not affect new session.
    tests++;
  }
  console.log(`PASS: ${tests} phone-page scenarios (mocked browser/GPS, not physical-phone validation)`);
}

main().catch(error => {console.error(error); process.exitCode = 1;});
