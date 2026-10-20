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
  const waitForCongress = (congress, target = page) => target.waitForFunction(c => {
    const text = document.querySelector("#data-notes").textContent;
    return Number.parseInt(text, 10) === c && document.querySelector("#workspace").getAttribute("aria-busy") === "false";
  }, congress);
  let congresses;
  const inputRange = (target, selector, value) => target.locator(selector).evaluate((slider, next) => {
    slider.value = String(next);
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  }, value);
  const setSlider = async (congress, target = page) => {
    const position = congresses.findIndex(item => item.congress === congress);
    assert.notEqual(position, -1, `Congress ${congress} is in the manifest`);
    // Dispatch only input: scrubbing must update without waiting for change/release.
    await inputRange(target, "#congress-slider", position);
  };
  const selectCongress = async (congress, target = page) => {
    await setSlider(congress, target);
    await waitForCongress(congress, target);
  };
  const assertTimeline = async (congress, target = page) => {
    const position = congresses.findIndex(item => item.congress === congress);
    const ordinal = new RegExp(`\\b${congress}(st|nd|rd|th)\\b`, "i");
    assert.equal(await target.locator("#congress-slider").inputValue(), String(position));
    assert.match(await target.locator("#congress-readout").innerText(), ordinal);
    assert.match(await target.locator("#congress-current").innerText(), ordinal);
    assert.match(await target.locator("#congress-slider").getAttribute("aria-valuetext"), ordinal);
    assert.equal(await target.locator("#congress-dots .timeline-dot[aria-current='true']").count(), 1);
    assert.equal(await target.locator("#congress-dots .timeline-dot").nth(position).getAttribute("aria-current"), "true");
    assert.equal(await target.locator("#congress-prev").isDisabled(), position === 0);
    assert.equal(await target.locator("#congress-next").isDisabled(), position === congresses.length - 1);
  };
  const chartTicks = () => page.locator("#main-chart .chart-tick").allTextContents();
  const hasIdeologyPair = node => Number.isFinite(node.nominate_dim1) && Number.isFinite(node.nominate_dim2);
  const snapshots = new Map();
  const snapshotFor = async congress => {
    if (!snapshots.has(congress)) snapshots.set(congress,
      await (await page.request.get(new URL(`data/congresses/${congress}.json`, base).href)).json());
    return snapshots.get(congress);
  };
  const chartBounds = target => target.locator("#main-chart svg").evaluate(svg =>
    ["xMin", "xMax", "yMin", "yMax"].map(key => Number(svg.dataset[key])));
  try {
    await page.goto(base, { waitUntil: "networkidle" });
    await page.locator("#main-chart .point").first().waitFor();
    assert.equal(await page.locator("#load-error").isVisible(), false);
    const manifest = await (await page.request.get(new URL("data/index.json", base).href)).json();
    congresses = [...manifest.congresses].sort((a, b) => a.congress - b.congress);
    const current = congresses.at(-1), first = congresses[0];
    assert.equal(await page.locator("#congress-select").count(), 0);
    assert.equal(await page.locator("#congress-slider").getAttribute("min"), "0");
    assert.equal(await page.locator("#congress-slider").getAttribute("max"), String(congresses.length - 1));
    assert.equal(await page.locator("#congress-dots .timeline-dot").count(), congresses.length);
    assert.equal(await page.locator("#main-chart .point").count(), current.members);
    await assertTimeline(current.congress);
    results.push(`Manifest and ${congresses.length} timeline points render; ${current.members} current senators`);

    const slider = page.locator("#congress-slider");
    await slider.focus();
    await slider.press("Home");
    await waitForCongress(first.congress);
    await assertTimeline(first.congress);
    await slider.press("ArrowRight");
    await waitForCongress(congresses[1].congress);
    await assertTimeline(congresses[1].congress);
    await page.locator("#congress-prev").click();
    await waitForCongress(first.congress);
    await assertTimeline(first.congress);
    await slider.focus();
    await slider.press("End");
    await waitForCongress(current.congress);
    await slider.press("ArrowLeft");
    await waitForCongress(congresses.at(-2).congress);
    await page.locator("#congress-next").click();
    await waitForCongress(current.congress);
    await assertTimeline(current.congress);
    results.push("Keyboard Home/End/arrows, previous/next controls, and boundary states");

    await selectCongress(119);
    const snapshot119 = await snapshotFor(119);
    const policy = snapshot119.provenance.parameters;
    const requiredVotes = Math.max(20, Math.ceil(.1 * snapshot119.provenance.source_rollcall_denominator));
    assert.equal(policy.minimum_usable_votes, 20);
    assert.equal(policy.minimum_participation_rate, .1);
    assert.equal(snapshot119.provenance.effective_minimum_votes, requiredVotes);
    assert.ok(snapshot119.nodes.every(node => node.votes_cast >= requiredVotes), "Every retained senator meets the shared voting-record threshold");
    for (const [id, name] of [[41102, "Rubio"], [42508, "Darline"], [42304, "Vance"]]) {
      const exclusion = snapshot119.provenance.excluded_members.find(node => node.id === id);
      assert.ok(exclusion, `${name} exclusion is recorded`);
      assert.match(exclusion.reason, /insufficient voting record/);
      assert.equal(exclusion.effective_minimum_votes, requiredVotes);
      await page.locator("#senator-search").fill(name);
      assert.equal(await page.locator("#search-results button").count(), 0);
      assert.match(await page.locator("#search-results").innerText(), /is excluded from this Congress/i);
      assert.ok((await page.locator("#search-results").innerText()).includes(exclusion.reason));
      assert.equal(await page.locator(`#main-chart .point[data-id="${id}"]`).count(), 0);
    }
    await selectCongress(118);
    await page.locator("#senator-search").fill("Rubio");
    await page.locator("#search-results button").first().click();
    assert.match(await page.locator("#senator-detail").innerText(), /Rubio/i);
    await selectCongress(119);
    await page.locator("#senator-search").fill("Armstrong");
    await page.locator("#search-results button").first().click();
    assert.match(await page.locator("#senator-detail").innerText(), /Armstrong/i);
    assert.match(await page.locator("#senator-detail").innerText(), /RECORD COVERAGE/);
    await page.locator("#senator-search").fill("no-senator-has-this-name");
    assert.match(await page.locator("#search-results").innerText(), /No matching/);
    await page.locator("#senator-search").fill("");
    results.push("One 20-vote/10% rule excludes brief records in 119; Rubio remains searchable in 118");

    assert.equal(await page.locator("#outlier-inspector").isVisible(), true);
    const inspectorButtons = page.locator("#outlier-list .outlier-button");
    assert.ok(await inspectorButtons.count() > 0, "Outlier inspector has selectable members");
    const inspectorIDs = await inspectorButtons.evaluateAll(buttons => buttons.map(button => Number(button.dataset.id)));
    assert.ok(inspectorIDs.every(id => snapshot119.nodes.some(node => node.id === id)), "Inspector names refer to included senators");
    for (const [id, name] of [[42507, /Armstrong/i], [41104, /Paul/i]]) {
      const button = page.locator(`#outlier-list .outlier-button[data-id="${id}"]`);
      assert.match(await button.innerText(), name);
      await button.click();
      assert.match(await page.locator("#senator-detail").innerText(), name);
      assert.equal(await page.locator(`#main-chart .point[data-id="${id}"]`).getAttribute("class").then(value => value.includes("selected")), true);
    }
    assert.ok(snapshot119.nodes.every(node => !/TRUMP|VANCE|RUBIO|GRAHAM, Darline/i.test(node.name)), "119th analyzed nodes exclude executive and insufficient-record entries");
    assert.equal(await page.locator('#outlier-list .outlier-button[data-id="42508"]').count(), 0);
    assert.match(await page.locator("#outlier-office-note").innerText(), /Rubio: insufficient voting record/);
    results.push("Outlier names are traceable to included senators and select their plotted records");

    const spectralTicks = await chartTicks();
    await page.locator('[data-view="network"]').click();
    assert.equal(await page.locator("#network-controls").isVisible(), true);
    assert.deepEqual(await chartTicks(), spectralTicks, "Network and geometry use the same fixed axes");
    const edgesBefore = await page.locator("#edge-count").innerText();
    await inputRange(page, "#edge-threshold", 0.99);
    assert.notEqual(await page.locator("#edge-count").innerText(), edgesBefore);
    await page.locator('[data-view="brokerage"]').click();
    assert.match(await page.locator("#plot-title").innerText(), /paths/);
    await page.locator('[data-view="ideology"]').click();
    assert.deepEqual(await chartBounds(page), [-1, 1, -1, 1]);
    assert.match(await page.locator("#plot-title").innerText(), /Ideology across Congresses/);
    assert.equal(await page.locator(".interpretation").isVisible(), false);
    const paul = snapshot119.nodes.find(node => node.id === 41104);
    assert.ok(hasIdeologyPair(paul));
    // Infer the actual plot rectangle from its grid, so this checks the source
    // coordinates without repeating chart layout constants from application code.
    const plotted = await page.locator('#main-chart .point[data-id="41104"]').evaluate(point => {
      const grid = [...point.ownerSVGElement.querySelectorAll(".chart-grid")];
      const xs = grid.filter(line => line.getAttribute("x1") === line.getAttribute("x2"))
        .map(line => Number(line.getAttribute("x1")));
      const ys = grid.filter(line => line.getAttribute("y1") === line.getAttribute("y2"))
        .map(line => Number(line.getAttribute("y1")));
      return [
        (Number(point.getAttribute("cx")) - Math.min(...xs)) / (Math.max(...xs) - Math.min(...xs)),
        (Math.max(...ys) - Number(point.getAttribute("cy"))) / (Math.max(...ys) - Math.min(...ys)),
      ];
    });
    assert.ok(Math.abs(plotted[0] - (paul.nominate_dim1 + 1) / 2) < 1e-10, "Ideology x uses the source NOMINATE score");
    assert.ok(Math.abs(plotted[1] - (paul.nominate_dim2 + 1) / 2) < 1e-10, "Ideology y uses the source NOMINATE score");
    assert.equal(new URL(page.url()).searchParams.get("view"), "ideology");
    await page.reload({ waitUntil: "networkidle" });
    await waitForCongress(119);
    assert.equal(await page.locator('[data-view="ideology"]').getAttribute("aria-pressed"), "true");
    assert.deepEqual(await chartBounds(page), [-1, 1, -1, 1]);
    await page.locator('[data-view="spectral"]').click();
    assert.equal(await page.locator(".interpretation").isVisible(), false);
    results.push("Network threshold; source NOMINATE coordinates, fixed common-scale bounds, and view URL persistence");

    const compareCongresses = [...new Set([first.congress, 96, current.congress])].filter(congress => congresses.some(item => item.congress === congress));
    for (const view of ["spectral", "ideology", "network", "brokerage"]) {
      await page.locator(`[data-view="${view}"]`).click();
      const ticks = await chartTicks();
      for (const congress of compareCongresses) {
        await selectCongress(congress);
        await assertTimeline(congress);
        assert.equal(new URL(page.url()).searchParams.get("congress"), String(congress));
        const snapshot = await snapshotFor(congress);
        const expectedPoints = view === "ideology" ? snapshot.nodes.filter(hasIdeologyPair).length : snapshot.members;
        assert.equal(await page.locator("#main-chart .point").count(), expectedPoints);
        assert.deepEqual(await chartTicks(), ticks, `${view} axes stay fixed for Congress ${congress}`);
        if (view === "ideology") assert.deepEqual(await chartBounds(page), [-1, 1, -1, 1]);
      }
    }
    await page.locator('[data-view="spectral"]').click();
    results.push("Input-only scrubbing synchronizes chart, URL, timeline, and fixed axes in all four views");

    const baselinePosition = congresses.findIndex(item => item.congress === 96);
    await page.locator("#congress-dots .timeline-dot").nth(baselinePosition).click();
    await waitForCongress(96);
    await assertTimeline(96);
    await selectCongress(current.congress);
    await page.locator("#compare-button").click();
    await page.locator("#comparison-panel svg").first().waitFor();
    assert.equal(await page.locator("#comparison-panel svg").count(), 2);
    await page.locator('[data-view="ideology"]').click();
    await page.waitForFunction(() => document.querySelector("#comparison-panel h3")?.textContent.includes("common ideological scale"));
    const comparisonBounds = await page.locator("#comparison-panel svg").evaluateAll(charts =>
      charts.map(svg => ["xMin", "xMax", "yMin", "yMax"].map(key => Number(svg.dataset[key]))));
    assert.deepEqual(comparisonBounds, [[-1, 1, -1, 1], [-1, 1, -1, 1]]);
    assert.ok((await page.locator("#comparison-panel svg > title").allTextContents()).every(title => title.includes("NOMINATE")));
    await page.locator('[data-view="spectral"]').click();
    await page.waitForFunction(() => document.querySelector("#comparison-panel h3")?.textContent.includes("visual frame"));
    assert.ok((await page.locator("#comparison-panel svg > title").allTextContents()).every(title => title.includes("spectral")));
    await page.locator("#compare-button").click();
    await page.locator("#history-metric").selectOption("gini_betweenness");
    assert.match(await page.locator("#history-chart-title").innerText(), /concentrated/);
    await page.locator("#history-metric").selectOption("fiedler_value");
    await page.locator("#history-chart .history-dot").first().click();
    await waitForCongress(first.congress);
    await assertTimeline(first.congress);
    await selectCongress(current.congress);
    results.push("Timeline point and historical selection, measure switching, comparison");

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
      await page.locator('[data-view="ideology"]').click();
      await page.locator("#explorer").screenshot({ path: path.join(imageDir, "explorer-ideology.png") });
      await page.locator('[data-view="network"]').click();
      await inputRange(page, "#edge-threshold", 0.8);
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
    await slider.focus();
    await slider.press("Home");
    await waitForCongress(first.congress);
    await assertTimeline(first.congress);
    await slider.press("End");
    await waitForCongress(current.congress);
    results.push("390px and 320px layouts without horizontal overflow");

    const missingScores = await browser.newPage();
    const missingErrors = [];
    missingScores.on("pageerror", error => missingErrors.push(error.message));
    try {
      const fixture = structuredClone(snapshot119);
      const missing = fixture.nodes[0];
      missing.name = "FIXTURE, Missing Score";
      missing.nominate_dim1 = null;
      missing.nominate_dim2 = .5;
      await missingScores.route("**/data/congresses/119.json", route => route.fulfill({ json: fixture }));
      const missingURL = new URL(base);
      missingURL.searchParams.set("congress", "119");
      missingURL.searchParams.set("view", "ideology");
      await missingScores.goto(missingURL.href, { waitUntil: "networkidle" });
      await waitForCongress(119, missingScores);
      assert.equal(await missingScores.locator("#main-chart .point").count(), fixture.nodes.filter(hasIdeologyPair).length);
      assert.equal(await missingScores.locator(`#main-chart .point[data-id="${missing.id}"]`).count(), 0);
      assert.equal(await missingScores.locator("#score-coverage").isVisible(), true);
      assert.match(await missingScores.locator("#score-coverage").innerText(), /no complete NOMINATE score/);
      await missingScores.locator("#senator-search").fill("missing score");
      await missingScores.locator("#search-results button").click();
      assert.match(await missingScores.locator("#senator-detail").innerText(), /remains in the graph analysis/);
      assert.equal(await missingScores.locator("#senator-detail .detail-values strong").nth(0).innerText(), "—");
      assert.equal(await missingScores.locator("#senator-detail .detail-values strong").nth(1).innerText(), "0.500");
      await missingScores.locator('[data-view="spectral"]').click();
      assert.equal(await missingScores.locator("#main-chart .point").count(), fixture.nodes.length);
      assert.equal(await missingScores.locator(`#main-chart .point[data-id="${missing.id}"]`).count(), 1);
      assert.equal(await missingScores.locator("#score-coverage").isVisible(), false);
      await missingScores.locator('[data-view="ideology"]').click();
      fixture.nodes.forEach(node => { node.nominate_dim1 = null; node.nominate_dim2 = null; });
      await missingScores.reload({ waitUntil: "networkidle" });
      await waitForCongress(119, missingScores);
      assert.equal(await missingScores.locator("#main-chart .point").count(), 0);
      assert.match(await missingScores.locator("#main-chart").innerText(), /No NOMINATE scores available/);
      assert.equal(await missingScores.locator("#score-coverage").isVisible(), true);
      assert.deepEqual(missingErrors, [], "Missing scores should never cause chart errors");
    } finally { await missingScores.close(); }
    results.push("Missing NOMINATE pairs are omitted and reported, remain searchable, and never become false zero-score points");

    const race = await browser.newPage();
    const raceErrors = [];
    race.on("pageerror", error => raceErrors.push(error.message));
    try {
      const initialURL = new URL(base);
      initialURL.searchParams.set("congress", first.congress);
      await race.goto(initialURL.href, { waitUntil: "networkidle" });
      await waitForCongress(first.congress, race);
      const delayedCongress = congresses.at(-2).congress;
      const failedCongress = congresses.at(-3).congress;
      let releaseDelayed;
      const delayedGate = new Promise(resolve => { releaseDelayed = resolve; });
      await race.route(`**/data/congresses/${delayedCongress}.json`, async route => {
        await delayedGate;
        await route.continue();
      });
      const requestStarted = race.waitForRequest(request => request.url().endsWith(`/data/congresses/${delayedCongress}.json`));
      await setSlider(delayedCongress, race);
      await requestStarted;
      await selectCongress(current.congress, race);
      await assertTimeline(current.congress, race);
      const delayedResponse = race.waitForResponse(response => response.url().endsWith(`/data/congresses/${delayedCongress}.json`));
      releaseDelayed();
      await (await delayedResponse).finished();
      // Give the delayed response's continuation an opportunity to commit if the
      // request guard is broken, then check the selected and rendered Congress.
      await race.waitForTimeout(150);
      await waitForCongress(current.congress, race);
      await assertTimeline(current.congress, race);
      assert.equal(new URL(race.url()).searchParams.get("congress"), String(current.congress));

      const lastChart = await race.locator("#main-chart").innerHTML();
      await race.route(`**/data/congresses/${failedCongress}.json`, route => route.fulfill({ status: 503, body: "Unavailable" }));
      await setSlider(failedCongress, race);
      await race.locator("#load-error:not([hidden])").waitFor();
      await waitForCongress(current.congress, race);
      await assertTimeline(current.congress, race);
      assert.equal(await race.locator("#main-chart").innerHTML(), lastChart, "Failed selection preserves the last rendered chart");
      assert.match(await race.locator("#load-error").innerText(), /503/);
      assert.equal(new URL(race.url()).searchParams.get("congress"), String(current.congress));
      assert.deepEqual(raceErrors, [], "Script errors during rapid or failed selection");
    } finally { await race.close(); }
    results.push("Delayed stale responses cannot replace the newest Congress; failed selection rolls controls back and preserves the chart");

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
