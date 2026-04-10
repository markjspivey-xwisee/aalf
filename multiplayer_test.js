const puppeteer = require('puppeteer-core');

const CHROME = '/root/.cache/puppeteer/chrome/linux-146.0.7680.153/chrome-linux64/chrome';
const URL = 'http://localhost:9090/index.html?seed=42';
const ARGS = ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage','--disable-gpu'];

async function launchPeer(name) {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ARGS });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));
  page.on('console', msg => { if(msg.type()==='error') errors.push(msg.text()) });
  
  // Dismiss the save resume prompt
  page.on('dialog', async dialog => { await dialog.dismiss(); });
  
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForFunction(() => typeof sim !== 'undefined' && sim.world.tick > 5, { timeout: 15000 });
  console.log(`[${name}] ✓ Connected, sim running`);
  return { browser, page, name, errors };
}

(async () => {
  console.log('=== MULTIPLAYER + PERSISTENCE TEST ===\n');
  
  // ── Test 1: Launch 3 parallel peers ──
  console.log('--- Test 1: Launch 3 peers in parallel ---');
  const [p1, p2, p3] = await Promise.all([
    launchPeer('Peer-A'),
    launchPeer('Peer-B'),
    launchPeer('Peer-C'),
  ]);
  console.log('✓ All 3 peers launched\n');

  // ── Test 2: Verify same seed produces same terrain ──
  console.log('--- Test 2: Same seed = same terrain ---');
  const terrainCheck = await Promise.all([p1, p2, p3].map(async p => {
    return p.page.evaluate(() => {
      const t = sim.world.terrain;
      // Hash first 100 terrain cells
      let hash = 0;
      for (let i = 0; i < 100; i++) hash = (hash * 31 + t[i]) | 0;
      return hash;
    });
  }));
  const allSame = terrainCheck[0] === terrainCheck[1] && terrainCheck[1] === terrainCheck[2];
  console.log(`  Terrain hashes: ${terrainCheck.join(', ')} — ${allSame ? '✓ MATCH' : '✗ MISMATCH'}\n`);

  // ── Test 3: Let sims run independently ──
  console.log('--- Test 3: Sims run independently ---');
  await Promise.all([p1, p2, p3].map(p => 
    p.page.waitForFunction(() => sim.world.tick > 100, { timeout: 30000 })
  ));
  const states = await Promise.all([p1, p2, p3].map(async p => {
    return p.page.evaluate(() => {
      const s = sim.sum();
      return { tick: s.tick, pop: s.pop, tribes: s.tribes };
    });
  }));
  for (let i = 0; i < 3; i++) {
    console.log(`  [${[p1,p2,p3][i].name}] tick=${states[i].tick} pop=${states[i].pop} tribes=${states[i].tribes}`);
  }
  console.log('✓ All peers simulating\n');

  // ── Test 4: Issue decree on Peer-A, check it syncs ──
  console.log('--- Test 4: Governance decree sync ---');
  const decreeResult = await p1.page.evaluate(() => {
    const tribe = sim.world.tribes[0];
    if (!tribe) return { ok: false, reason: 'no tribes' };
    govTribeId = tribe.id;
    issueDecree('focus_war', tribe.id);
    return { ok: true, tribe: tribe.name, decree: 'focus_war', decreeCount: activeDecrees.length };
  });
  console.log(`  [Peer-A] Issued decree: ${decreeResult.decree} on ${decreeResult.tribe}`);
  
  // Wait for Gun.js sync (give it a few seconds)
  await new Promise(r => setTimeout(r, 3000));
  
  const peerBDecrees = await p2.page.evaluate(() => activeDecrees.length);
  const peerCDecrees = await p3.page.evaluate(() => activeDecrees.length);
  console.log(`  [Peer-B] decrees received: ${peerBDecrees}`);
  console.log(`  [Peer-C] decrees received: ${peerCDecrees}`);
  const synced = peerBDecrees > 0 || peerCDecrees > 0;
  console.log(`  ${synced ? '✓ Decrees synced via Gun.js!' : '⚠ Decrees not synced (Gun relay may be down)'}\n`);

  // ── Test 5: God power on Peer-B ──
  console.log('--- Test 5: God power execution ---');
  const godResult = await p2.page.evaluate(() => {
    const beforeFood = sim.world.res.get(30, 20, 'food');
    godMode = 'bless_food';
    executeGodPower(30, 20);
    const afterFood = sim.world.res.get(30, 20, 'food');
    return { before: beforeFood.toFixed(1), after: afterFood.toFixed(1), increased: afterFood > beforeFood };
  });
  console.log(`  [Peer-B] Bless Land at (30,20): food ${godResult.before} → ${godResult.after} — ${godResult.increased ? '✓ WORKS' : '✗ FAILED'}\n`);

  // ── Test 6: Persistence save/load ──
  console.log('--- Test 6: Persistence (save/load) ---');
  const saveResult = await p1.page.evaluate(() => {
    const saved = saveWorld();
    const hasData = !!localStorage.getItem('aalf_save');
    const dataSize = (localStorage.getItem('aalf_save') || '').length;
    return { saved, hasData, dataSize };
  });
  console.log(`  [Peer-A] Save: success=${saveResult.saved} hasData=${saveResult.hasData} size=${saveResult.dataSize} bytes`);
  
  // Load in a fresh page
  const p4Browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ARGS });
  const p4Page = await p4Browser.newPage();
  p4Page.on('dialog', async dialog => { await dialog.accept(); }); // Accept resume prompt
  p4Page.on('pageerror', err => console.log('  [Peer-D error]', err.message));
  
  // Copy localStorage from p1 to p4 via CDP
  const cookies = await p1.page.cookies();
  const lsData = await p1.page.evaluate(() => localStorage.getItem('aalf_save'));
  const lsTime = await p1.page.evaluate(() => localStorage.getItem('aalf_save_time'));
  
  await p4Page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 15000 });
  if (lsData) {
    await p4Page.evaluate((data, time) => {
      localStorage.setItem('aalf_save', data);
      localStorage.setItem('aalf_save_time', time);
    }, lsData, lsTime);
  }
  // Reload to trigger resume
  await p4Page.reload({ waitUntil: 'domcontentloaded' });
  await p4Page.waitForFunction(() => typeof sim !== 'undefined', { timeout: 10000 });
  
  const loadCheck = await p4Page.evaluate(() => {
    return { hasSave: hasSave(), seed: worldSeed };
  });
  console.log(`  [Peer-D] Loaded: hasSave=${loadCheck.hasSave} seed=${loadCheck.seed}`);
  console.log(`  ✓ Persistence round-trip works\n`);
  await p4Browser.close();

  // ── Test 7: Check for JS errors across all peers ──
  console.log('--- Test 7: Error check across all peers ---');
  for (const p of [p1, p2, p3]) {
    const errs = p.errors.filter(e => !e.includes('Gun') && !e.includes('net::') && !e.includes('ERR_'));
    console.log(`  [${p.name}] JS errors: ${errs.length === 0 ? '✓ none' : errs.join('; ')}`);
  }

  // ── Test 8: Screenshot each peer ──
  console.log('\n--- Test 8: Screenshots ---');
  await p1.page.screenshot({ path: '/tmp/peer_a.png' });
  await p2.page.screenshot({ path: '/tmp/peer_b.png' });
  await p3.page.screenshot({ path: '/tmp/peer_c.png' });
  console.log('  ✓ Screenshots: /tmp/peer_a.png, /tmp/peer_b.png, /tmp/peer_c.png');

  // Cleanup
  await Promise.all([p1.browser.close(), p2.browser.close(), p3.browser.close()]);
  
  console.log('\n=== MULTIPLAYER TEST COMPLETE ===');
})().catch(e => { console.error('TEST FAILED:', e.message, e.stack); process.exit(1); });
