#!/usr/bin/env node
// Extract structured ordering data (psidss/pprcss/ctidss/pltdss/exTopping)
// from a Pizza Hut step_2 "menu page" by executing its data <script> blocks.
//
// Why node: the menu page embeds product/choice data as inline JS variables.
// Some pages assign directly (ctidss.v["g1_.."][0]="3021"), others use an
// indirect variable (spArrName = 'g' + orderSpecName) — regex can't reliably
// follow the indirect form, but executing the script in a vm fills both.
//
// Usage: node extract_js.cjs <html-file>
//   stdout: JSON {psidss, pprcss, ctidss, pltdss, exTopping}
//   stderr: diagnostics (total/data script counts, per-block failures)
const fs = require('fs');
const vm = require('vm');

const file = process.argv[2];
if (!file) { console.error('usage: node extract_js.cjs <html>'); process.exit(1); }
const html = fs.readFileSync(file, 'utf8');

// pull all inline <script> blocks
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);

// keep only blocks referencing the data vars
const KEY = /psidss|pprcss|ctidss|pltdss|exTopping/;
const dataBlocks = scripts.filter(sc => KEY.test(sc));
console.error(`total scripts=${scripts.length} dataBlocks=${dataBlocks.length}`);

const sandbox = {};
sandbox.window = sandbox;          // window.* === bare globals
sandbox.self = sandbox;
sandbox.console = console;
sandbox.Date = Date; sandbox.JSON = JSON; sandbox.Math = Math;
// minimal DOM stubs in case any read-path code runs at top level
sandbox.document = {
  getElementById: () => null,
  querySelector: () => null,
  querySelectorAll: () => [],
  createElement: () => ({ style: {}, setAttribute(){}, appendChild(){} }),
  cookie: '',
};
sandbox.location = { search: '', href: file, pathname: '' };
vm.createContext(sandbox);

let executed = 0, failed = 0;
for (const sc of dataBlocks) {
  try {
    vm.runInContext(sc, sandbox, { timeout: 2000 });
    executed++;
  } catch (e) {
    failed++;
    // ignore failures — data-only blocks are assignment-heavy and should pass;
    // only surface failures that are NOT in data-only blocks
    if (!/psidss|pprcss|ctidss|pltdss|exTopping/.test(sc) || sc.length > 2000) {
      console.error(`block fail (len=${sc.length}): ${e.message.slice(0,150)}`);
    }
  }
}
console.error(`executed=${executed} failed=${failed}`);

const out = {};
for (const v of ['psidss','pprcss','ctidss','pltdss','exTopping']) {
  out[v] = sandbox[v] !== undefined ? sandbox[v] : null;
}
process.stdout.write(JSON.stringify(out));
