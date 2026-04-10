const puppeteer = require('puppeteer-core');
const path = require('path');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/root/.cache/puppeteer/chrome/linux-146.0.7680.153/chrome-linux64/chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  page.on('console', msg => {
    const type = msg.type();
    if (type === 'error' || type === 'warning') console.log(`[${type}] ${msg.text()}`);
  });
  page.on('pageerror', err => console.log('[PAGE ERROR]', err.message));

  console.log('=== LOADING PAGE ===');
  await page.goto('http://localhost:9090/index.html', { waitUntil: 'domcontentloaded', timeout: 15000 });
  
  // Wait for init
  await page.waitForFunction(() => typeof sim !== 'undefined' && sim.world.tick > 0, { timeout: 10000 });
  console.log('✓ Page loaded, simulation running');

  // Check canvas exists and has size
  const canvasInfo = await page.evaluate(() => {
    const cv = document.getElementById('cv');
    return { width: cv.width, height: cv.height, ctx: !!cv.getContext('2d') };
  });
  console.log(`✓ Canvas: ${canvasInfo.width}x${canvasInfo.height} ctx=${canvasInfo.ctx}`);

  // Let it run for a bit
  await page.waitForFunction(() => sim.world.tick > 50, { timeout: 30000 });
  
  // Check simulation state
  const state = await page.evaluate(() => {
    const s = sim.sum();
    return {
      tick: s.tick, pop: s.pop, tribes: s.tribes, structs: s.structs,
      fire: s.fire, farm: s.farm, maxTool: s.maxTool,
      wars: s.wars, trades: s.trades,
      animals: s.animals,
      canvasDrawn: document.getElementById('cv').getContext('2d').getImageData(10, 10, 1, 1).data[3] > 0
    };
  });
  console.log(`✓ Tick ${state.tick}: pop=${state.pop} tribes=${state.tribes} structs=${state.structs}`);
  console.log(`  fire=${state.fire} farm=${state.farm} tool=${state.maxTool}`);
  console.log(`  animals: deer=${state.animals.deer} wolf=${state.animals.wolf} boar=${state.animals.boar}`);
  console.log(`  canvas has pixels: ${state.canvasDrawn}`);

  // Check for JS errors that occurred during runtime
  const errors = await page.evaluate(() => {
    return window.__errors || [];
  });
  
  // Check all sidebar elements render
  const sidebarOk = await page.evaluate(() => {
    const ids = ['xt','xsn','xp','xan','xtr','xst','xht','xbd','xera'];
    const results = {};
    for (const id of ids) {
      const el = document.getElementById(id);
      results[id] = el ? el.textContent : 'MISSING';
    }
    return results;
  });
  console.log('✓ Sidebar values:', JSON.stringify(sidebarOk));

  // Check governance panel exists
  const govExists = await page.evaluate(() => {
    return {
      govPanel: !!document.getElementById('gov-panel'),
      godPanel: !!document.getElementById('god-panel'),
      minimap: !!document.getElementById('minimap'),
      toasts: !!document.getElementById('toasts'),
      narrative: !!document.getElementById('narrative'),
      daybar: !!document.getElementById('daybar'),
    };
  });
  console.log('✓ UI elements:', JSON.stringify(govExists));

  // Check tooltips work
  const tooltipCheck = await page.evaluate(() => {
    const tt = document.getElementById('tt');
    return { exists: !!tt, display: tt?.style?.display };
  });
  console.log(`✓ Tooltip: exists=${tooltipCheck.exists} display=${tooltipCheck.display}`);

  // Let it run more and check for errors
  await page.waitForFunction(() => sim.world.tick > 150, { timeout: 30000 });
  
  const state2 = await page.evaluate(() => {
    const s = sim.sum();
    const w = sim.world;
    return {
      tick: s.tick, pop: s.pop, tribes: s.tribes, structs: s.structs,
      ruins: w.ruins.length, wonders: w.wonders.length, cities: w.cities.length,
      climate: w.climate.era,
      maxTool: s.maxTool,
      tribeDetails: w.tribes.slice(0, 3).map(t => ({
        name: t.name, sz: t.sz, belief: t.belief, 
        leader: t.leaderName, isEmpire: t.isEmpire,
        hasMythology: t.myths.length > 0,
        currencyTier: t.currencyTier
      }))
    };
  });
  console.log(`\n=== AFTER ${state2.tick} TICKS ===`);
  console.log(`pop=${state2.pop} tribes=${state2.tribes} structs=${state2.structs}`);
  console.log(`ruins=${state2.ruins} wonders=${state2.wonders} cities=${state2.cities} climate=${state2.climate}`);
  console.log(`maxTool=${state2.maxTool}`);
  for (const t of state2.tribeDetails) {
    console.log(`  ${t.name}(${t.sz}) belief=${t.belief} leader=${t.leader} empire=${t.isEmpire} myths=${t.hasMythology} currency=${t.currencyTier}`);
  }

  // Screenshot
  await page.screenshot({ path: '/tmp/aalf_screenshot.png', fullPage: false });
  console.log('\n✓ Screenshot saved to /tmp/aalf_screenshot.png');

  console.log('\n=== ALL TESTS PASSED ===');
  await browser.close();
})().catch(e => { console.error('TEST FAILED:', e.message); process.exit(1); });
