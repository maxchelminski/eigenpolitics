/* Start `python scripts/serve.py` first. Optional: npm install && npx playwright install chromium.
 * Set BROWSER_CHANNEL=msedge to use a locally installed Edge browser.
 * Screenshots are actual browser captures of the bundled data, never mockups.
 */
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs/promises");

async function run() {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) });
  const errors = [];
  const base = process.env.SITE_URL || "http://127.0.0.1:4173/";
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 1 });
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  const results = [];
  const waitForCongress = (congress) => page.waitForFunction(c => {
    const text = document.querySelector("#data-notes").textContent;
    return Number.parseInt(text, 10) === c && document.querySelector("#workspace").getAttribute("aria-busy") === "false";
  }, congress);
  try {
    await page.goto(base, { waitUntil: "networkidle" });
    await page.locator("#main-chart .point").first().waitFor();
    assert.equal(await page.locator("#load-error").isVisible(), false);
    const manifest = await (await page.request.get(new URL("data/index.json", base).href)).json();
    assert.equal(await page.locator("#congress-select option").count(), manifest.congresses.length);
    const current = manifest.congresses.at(-1);
    assert.equal(await page.locator("#main-chart .point").count(), current.members);
    results.push(`Manifest and ${manifest.congresses.length} Congress options render; ${current.members} current points`);

    await page.locator("#congress-select").selectOption("119");
    await waitForCongress(119);
    await page.locator("#senator-search").fill("Rubio");
    await page.locator("#search-results button").first().click();
    assert.match(await page.locator("#senator-detail").innerText(), /Rubio/i);
    assert.match(await page.locator("#senator-detail").innerText(), /Low record coverage/);
    await page.locator("#senator-search").fill("no-senator-has-this-name");
    assert.match(await page.locator("#search-results").innerText(), /No matching/);
    await page.locator("#senator-search").fill("");
    results.push("Member search, empty results, selection, low-coverage caution");

    await page.locator('[data-view="network"]').click();
    assert.equal(await page.locator("#network-controls").isVisible(), true);
    const edgesBefore = await page.locator("#edge-count").innerText();
    await page.locator("#edge-threshold").fill("0.99");
    await page.locator("#edge-threshold").dispatchEvent("input");
    assert.notEqual(await page.locator("#edge-count").innerText(), edgesBefore);
    await page.locator('[data-view="brokerage"]').click();
    assert.match(await page.locator("#plot-title").innerText(), /paths/);
    await page.locator('[data-view="spectral"]').click();
    results.push("Network threshold and all chart modes");

    await page.locator("#congress-select").selectOption("96");
    await waitForCongress(96);
    assert.equal(await page.locator("#main-chart .point").count(), manifest.congresses.find(d => d.congress === 96).members);
    await page.locator("#congress-select").selectOption(String(current.congress));
    await waitForCongress(current.congress);
    await page.locator("#compare-button").click();
    await page.locator("#comparison-panel svg").first().waitFor();
    assert.equal(await page.locator("#comparison-panel svg").count(), 2);
    await page.locator("#compare-button").click();
    await page.locator("#history-metric").selectOption("gini_betweenness");
    assert.match(await page.locator("#history-chart-title").innerText(), /concentrated/);
    await page.locator("#history-metric").selectOption("fiedler_value");
    await page.locator("#history-chart .history-dot").first().click();
    await waitForCongress(1);
    await page.locator("#congress-select").selectOption(String(current.congress));
    await waitForCongress(current.congress);
    results.push("Congress changes, historical selection, measure switching, comparison");

    await page.locator("summary").filter({ hasText: "Data provenance" }).click();
    const download = page.waitForEvent("download");
    await page.locator("#download-csv").click();
    const csv = await download;
    assert.equal(csv.suggestedFilename(), "eigenpolitics-historical-metrics.csv");
    const stream = await csv.createReadStream();
    let csvText = "";
    for await (const chunk of stream) csvText += chunk;
    assert.equal(csvText.split("\r\n").length, manifest.congresses.length + 1);
    await page.locator("summary").filter({ hasText: "Data provenance" }).click();
    const pdf = await page.request.get(new URL("research/thesis.pdf", base).href);
    assert.equal(pdf.status(), 200);
    assert.match(pdf.headers()["content-type"], /pdf/);
    results.push("CSV download and thesis PDF");

    const imageDir = path.join(__dirname, "..", "docs", "images");
    if (process.argv.includes("--screenshots")) {
      await fs.mkdir(imageDir, { recursive: true });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: path.join(imageDir, "explorer-desktop.png"), fullPage: true });
      await page.locator('[data-view="network"]').click();
      await page.locator("#edge-threshold").fill("0.8");
      await page.locator("#edge-threshold").dispatchEvent("input");
      await page.locator("#explorer").screenshot({ path: path.join(imageDir, "explorer-network.png") });
      await page.locator('[data-view="spectral"]').click();
    }

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(250);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), "Mobile page overflows horizontally");
    assert.equal(await page.locator("#main-chart .point").count(), current.members);
    if (process.argv.includes("--screenshots")) {
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: path.join(imageDir, "explorer-mobile.png"), fullPage: true });
    }
    await page.setViewportSize({ width: 320, height: 700 });
    await page.waitForTimeout(250);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), "320px viewport overflows");
    results.push("390px and 320px layouts without horizontal overflow");

    const failed = await browser.newPage();
    await failed.route("**/data/index.json", route => route.fulfill({ status: 503, body: "Unavailable" }));
    await failed.goto(base);
    await failed.locator("#load-error:not([hidden])").waitFor();
    assert.match(await failed.locator("#load-error").innerText(), /503/);
    await failed.close();
    results.push("Unavailable data produces an actionable error");
    assert.deepEqual(errors, [], "Browser errors");
    console.log(JSON.stringify({ status: "passed", checks: results }, null, 2));
  } finally { await browser.close(); }
}
run().catch(error => { console.error(error); process.exitCode = 1; });
