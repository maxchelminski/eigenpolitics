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
  const snapshots = new Map();
  const snapshotFor = async congress => {
    if (!snapshots.has(congress)) snapshots.set(congress,
      await (await page.request.get(new URL(`data/congresses/${congress}.json`, base).href)).json());
    return snapshots.get(congress);
  };
  const chartBounds = target => target.locator("#main-chart svg").evaluate(svg =>
    ["xMin", "xMax", "yMin", "yMax"].map(key => Number(svg.dataset[key])));
  // Read the actual plot rectangle from its grid rather than repeating chart
  // layout constants. This checks source coordinates after responsive scaling.
  const plotRectangle = target => target.locator("#main-chart svg").evaluate(svg => {
    const grid = [...svg.querySelectorAll(".chart-grid")];
    const xs = grid.filter(line => line.getAttribute("x1") === line.getAttribute("x2"))
      .map(line => Number(line.getAttribute("x1")));
    const ys = grid.filter(line => line.getAttribute("y1") === line.getAttribute("y2"))
      .map(line => Number(line.getAttribute("y1")));
    return [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  });
  const pixelFor = async (target, x, y) => {
    const [xMin, xMax, yMin, yMax] = await chartBounds(target);
    const [left, right, top, bottom] = await plotRectangle(target);
    return [left + (x - xMin) / (xMax - xMin) * (right - left),
      bottom - (y - yMin) / (yMax - yMin) * (bottom - top)];
  };
  const assertCoordinates = async (target, id, x, y, label) => {
    const expected = await pixelFor(target, x, y);
    const actual = await target.locator(`#main-chart .point[data-id="${id}"]`).evaluate(point =>
      [Number(point.getAttribute("cx")), Number(point.getAttribute("cy"))]);
    actual.forEach((value, axis) => assert.ok(Math.abs(value - expected[axis]) < 1e-8, `${label}: axis ${axis + 1} matches the generated source coordinate`));
  };
  const screenPoint = async (target, fractionX, fractionY) => {
    const [left, right, top, bottom] = await plotRectangle(target);
    return target.locator("#main-chart svg").evaluate((svg, point) => {
      const client = new DOMPoint(...point).matrixTransform(svg.getScreenCTM());
      return { x: client.x, y: client.y };
    }, [left + fractionX * (right - left), top + fractionY * (bottom - top)]);
  };
  const whitespacePoint = async target => {
    await target.locator("#main-chart svg").scrollIntoViewIfNeeded();
    const rect = await plotRectangle(target);
    return target.locator("#main-chart svg").evaluate((svg, [left, right, top, bottom]) => {
      const points = [...svg.querySelectorAll(".point")].map(point =>
        [Number(point.getAttribute("cx")), Number(point.getAttribute("cy"))]);
      for (const fy of [.08, .92, .25, .75, .5]) {
        for (const fx of [.08, .92, .25, .75, .5]) {
          const x = left + fx * (right - left), y = top + fy * (bottom - top);
          if (points.every(([px, py]) => Math.hypot(x - px, y - py) > 16)) {
            const client = new DOMPoint(x, y).matrixTransform(svg.getScreenCTM());
            return { x: client.x, y: client.y };
          }
        }
      }
      throw new Error("No empty plot area found for the whitespace interaction");
    }, rect);
  };
  const clickWhitespace = async target => {
    const point = await whitespacePoint(target);
    await target.mouse.click(point.x, point.y);
  };
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
    assert.equal(await page.locator("#align-spectra").count(), 0);
    assert.equal(await page.locator("[data-view]").count(), 4);
    assert.equal(await page.locator('[data-view="spectral"]').getAttribute("aria-pressed"), "true");
    assert.equal(await page.locator('[data-view="ideology"]').count(), 0);
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

    const paul = snapshot119.nodes.find(node => node.id === 41104);
    const alignedBounds = [...manifest.aligned_axis_bounds.x, ...manifest.aligned_axis_bounds.y];
    const rawBounds = [...manifest.axis_bounds.x, ...manifest.axis_bounds.y];
    assert.deepEqual(await chartBounds(page), rawBounds);
    await assertCoordinates(page, paul.id, paul.x, paul.y, "Original Geometry");
    const spectralTicks = await chartTicks();
    const statsBefore = await page.locator("#stats").innerText();
    await page.locator('[data-view="network"]').click();
    assert.equal(await page.locator("#network-controls").isVisible(), true);
    assert.deepEqual(await chartTicks(), spectralTicks, "Network and Geometry use the same raw axes");
    await assertCoordinates(page, paul.id, paul.x, paul.y, "Original Network");
    const edgesBefore = await page.locator("#edge-count").innerText();
    await inputRange(page, "#edge-threshold", 0.99);
    assert.notEqual(await page.locator("#edge-count").innerText(), edgesBefore);
    await page.locator('[data-view="brokerage"]').click();
    assert.match(await page.locator("#plot-title").innerText(), /paths/);
    await assertCoordinates(page, paul.id, paul.x, paul.betweenness, "Brokerage retains the raw Fiedler coordinate and graph centrality");
    await page.locator('[data-view="aligned"]').click();
    assert.deepEqual(await chartBounds(page), alignedBounds);
    await assertCoordinates(page, paul.id, paul.aligned_x, paul.aligned_y, "Aligned geometry");
    assert.equal(new URL(page.url()).searchParams.get("view"), "aligned");
    assert.equal(await page.locator("#stats").innerText(), statsBefore, "Alignment does not alter graph statistics");
    await page.reload({ waitUntil: "networkidle" });
    await waitForCongress(119);
    assert.equal(await page.locator('[data-view="aligned"]').getAttribute("aria-pressed"), "true");
    assert.deepEqual(await chartBounds(page), alignedBounds);
    assert.equal(await page.locator(".interpretation").isVisible(), false);
    assert.equal(await page.locator("#alignment-info").getAttribute("open"), null);
    results.push("Original Geometry/Network/Brokerage and separate Aligned source coordinates, URL persistence, and unchanged graph metrics");

    const compareCongresses = [...new Set([first.congress, 96, current.congress])].filter(congress => congresses.some(item => item.congress === congress));
    for (const view of ["spectral", "aligned", "network", "brokerage"]) {
      await page.locator(`[data-view="${view}"]`).click();
      const aligned = view === "aligned";
      const ticks = await chartTicks();
      for (const congress of compareCongresses) {
        await selectCongress(congress);
        await assertTimeline(congress);
        assert.equal(new URL(page.url()).searchParams.get("congress"), String(congress));
        const snapshot = await snapshotFor(congress);
        assert.equal(await page.locator("#main-chart .point").count(), snapshot.members);
        assert.deepEqual(await chartTicks(), ticks, `${view} axes stay fixed for Congress ${congress}`);
        const senator = snapshot.nodes[0];
        await assertCoordinates(page, senator.id, aligned ? senator.aligned_x : senator.x,
          view === "brokerage" ? senator.betweenness : aligned ? senator.aligned_y : senator.y,
          `${view}, Congress ${congress}`);
      }
    }
    await page.locator('[data-view="aligned"]').click();
    results.push("Input-only scrubbing synchronizes chart, URL, timeline, and fixed axes in all four views");

    await selectCongress(118);
    await page.locator("#senator-search").fill("Rand Paul");
    await page.locator("#search-results button").click();
    await selectCongress(119);
    assert.equal(await page.locator('#main-chart .point[data-id="41104"].selected').count(), 1);
    assert.match(await page.locator("#senator-detail").innerText(), /Rand Paul/);
    const snapshot118 = await snapshotFor(118);
    const priorPaul = snapshot118.nodes.find(node => node.id === paul.id);
    assert.ok(snapshot119.alignment.anchor_ids.includes(paul.id), "Selected senator is an actual alignment anchor");
    const trail = page.locator("#member-trail");
    await trail.waitFor();
    assert.match(await page.locator("#senator-detail").innerText(), /CHANGE SINCE/);
    assert.equal(await trail.count(), 1);
    assert.equal(await trail.getAttribute("data-member-id"), String(paul.id));
    assert.equal(await trail.getAttribute("data-from-congress"), "118");
    assert.equal(await trail.getAttribute("data-to-congress"), "119");
    const priorPixel = await pixelFor(page, priorPaul.aligned_x, priorPaul.aligned_y);
    const currentPixel = await pixelFor(page, paul.aligned_x, paul.aligned_y);
    const trailPixels = await trail.locator(".trail-line").evaluate(line => ["x1", "y1", "x2", "y2"].map(key => Number(line.getAttribute(key))));
    [...priorPixel, ...currentPixel].forEach((value, index) => assert.ok(Math.abs(trailPixels[index] - value) < 1e-8, "Trail connects source coordinates in the same frame"));
    await page.locator('[data-view="network"]').click();
    assert.equal(await trail.count(), 0, "The original Network view has no aligned movement trail");
    await page.locator('[data-view="brokerage"]').click();
    assert.equal(await trail.count(), 0, "A geometric trajectory is not projected onto brokerage");
    await page.locator('[data-view="spectral"]').click();
    assert.equal(await trail.count(), 0, "Original Geometry has no aligned movement trail");
    await page.locator('[data-view="aligned"]').click();
    await selectCongress(first.congress);
    assert.match(await page.locator("#senator-detail").innerText(), /Rand Paul/);
    assert.match(await page.locator("#senator-detail").innerText(), /Not included in the .*Congress analysis/);
    assert.equal(await page.locator("#main-chart .point.selected").count(), 0);
    assert.equal(await trail.count(), 0);
    await selectCongress(119);
    assert.equal(await page.locator('#main-chart .point[data-id="41104"].selected').count(), 1, "Selection returns when the senator is present again");
    assert.equal(await page.locator('#outlier-list .outlier-button[data-id="41104"]').getAttribute("aria-pressed"), "true",
      "Returning to the 119th preserves the selected senator in the outlier shortcuts");
    await selectCongress(118);
    await page.locator("#senator-search").fill("Rubio");
    await page.locator("#search-results button").click();
    await selectCongress(119);
    assert.match(await page.locator("#senator-detail").innerText(), /Rubio/);
    assert.match(await page.locator("#senator-detail").innerText(), /insufficient voting record/);
    assert.equal(await page.locator("#main-chart .point.selected").count(), 0);
    assert.equal(await trail.count(), 0);
    results.push("Selected senators persist across Congresses; source-based movement trails require shared membership and aligned geometry");

    await page.locator("#senator-search").fill("");
    await page.locator('#main-chart .point[data-id="41104"]').click();
    await trail.waitFor();
    assert.equal(await page.locator('#main-chart .point[data-id="41104"].selected').count(), 1,
      "Clicking a senator does not bubble into background deselection");
    await clickWhitespace(page);
    assert.equal(await page.locator("#main-chart .point.selected").count(), 0);
    assert.equal(await trail.count(), 0);
    assert.equal(await page.locator('#outlier-list .outlier-button[aria-pressed="true"]').count(), 0);
    assert.match(await page.locator("#senator-detail").innerText(), /EXPLORE A POINT/);
    await selectCongress(118);
    await selectCongress(119);
    assert.equal(await page.locator("#main-chart .point.selected").count(), 0, "Cleared selections remain cleared when changing Congress");
    await page.locator('[data-view="spectral"]').click();
    await page.locator('#main-chart .point[data-id="41104"]').click();
    assert.equal(await page.locator('#main-chart .point[data-id="41104"].selected').count(), 1);
    await clickWhitespace(page);
    assert.match(await page.locator("#senator-detail").innerText(), /EXPLORE A POINT/);
    results.push("Point clicks select senators; whitespace clears the point, detail, trail, shortcut, and remembered selection");

    assert.equal(await page.locator("#zoom-level").innerText(), "100%");
    await page.locator("#zoom-in").click();
    assert.equal(await page.locator("#zoom-level").innerText(), "125%");
    const zoomedBounds = await chartBounds(page);
    assert.ok(Math.abs((zoomedBounds[1] - zoomedBounds[0]) * 1.25 - (rawBounds[1] - rawBounds[0])) < 1e-10,
      "Zoom changes the visible range while preserving the plotted source coordinates");
    await assertCoordinates(page, paul.id, paul.x, paul.y, "Zoomed original Geometry");
    await page.locator("#zoom-out").click();
    assert.equal(await page.locator("#zoom-level").innerText(), "100%");
    assert.deepEqual(await chartBounds(page), rawBounds);
    await page.locator("#zoom-in").click();
    await page.locator("#main-chart svg").scrollIntoViewIfNeeded();
    const wheelFraction = [.65, .35];
    const wheelPoint = await screenPoint(page, ...wheelFraction);
    const beforeWheel = await chartBounds(page);
    const wheelRect = await plotRectangle(page);
    // Browser mouse input may round fractional client pixels. Observe the real
    // event so the anchor expectation uses the position the app actually got.
    const observedWheel = page.locator("#main-chart svg").evaluate((svg, [left, right, top, bottom]) =>
      new Promise(resolve => svg.addEventListener("wheel", event => {
        const local = new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM().inverse());
        resolve([(local.x - left) / (right - left), (local.y - top) / (bottom - top)]);
      }, { once: true, capture: true })), wheelRect);
    await page.mouse.move(wheelPoint.x, wheelPoint.y);
    await page.mouse.wheel(0, -120);
    const actualWheelFraction = await observedWheel;
    await page.waitForFunction(() => document.querySelector("#zoom-level").textContent !== "125%");
    const afterWheel = await chartBounds(page);
    assert.ok(afterWheel[1] - afterWheel[0] < beforeWheel[1] - beforeWheel[0], "Wheel up zooms in");
    const pinnedData = [beforeWheel[0] + actualWheelFraction[0] * (beforeWheel[1] - beforeWheel[0]),
      beforeWheel[3] - actualWheelFraction[1] * (beforeWheel[3] - beforeWheel[2])];
    const afterPinnedData = [afterWheel[0] + actualWheelFraction[0] * (afterWheel[1] - afterWheel[0]),
      afterWheel[3] - actualWheelFraction[1] * (afterWheel[3] - afterWheel[2])];
    pinnedData.forEach((value, index) => assert.ok(Math.abs(value - afterPinnedData[index]) < 1e-8,
      "Wheel zoom holds the data beneath the cursor fixed"));
    const dragStart = await whitespacePoint(page);
    await page.mouse.move(dragStart.x, dragStart.y);
    await page.mouse.down();
    await page.mouse.move(dragStart.x + 35, dragStart.y + 25, { steps: 5 });
    await page.mouse.up();
    const pannedBounds = await chartBounds(page);
    assert.notDeepEqual(pannedBounds, afterWheel, "Dragging a zoomed plot pans its visible range");
    assert.ok(Math.abs((pannedBounds[1] - pannedBounds[0]) - (afterWheel[1] - afterWheel[0])) < 1e-10,
      "Panning does not change the zoom factor");
    const geometryZoom = await page.locator("#zoom-level").innerText();
    await page.locator('[data-view="aligned"]').click();
    assert.equal(await page.locator("#zoom-level").innerText(), "100%");
    assert.deepEqual(await chartBounds(page), alignedBounds);
    await page.locator("#zoom-in").click();
    const alignedZoomBounds = await chartBounds(page);
    await page.locator('[data-view="network"]').click();
    assert.equal(await page.locator("#zoom-level").innerText(), "100%");
    assert.deepEqual(await chartBounds(page), rawBounds);
    await page.locator('[data-view="spectral"]').click();
    assert.equal(await page.locator("#zoom-level").innerText(), geometryZoom);
    assert.deepEqual(await chartBounds(page), pannedBounds, "Each tab retains its own viewport");
    await selectCongress(118);
    assert.deepEqual(await chartBounds(page), pannedBounds, "Moving Congress retains the view's zoom and pan");
    await selectCongress(119);
    assert.deepEqual(await chartBounds(page), pannedBounds);
    await page.locator("#zoom-reset").click();
    assert.equal(await page.locator("#zoom-level").innerText(), "100%");
    assert.deepEqual(await chartBounds(page), rawBounds, "Reset restores the global fixed bounds");
    await page.locator('[data-view="aligned"]').click();
    assert.deepEqual(await chartBounds(page), alignedZoomBounds);
    await page.locator("#zoom-reset").click();
    assert.deepEqual(await chartBounds(page), alignedBounds);
    await page.locator('[data-view="spectral"]').click();
    for (let step = 0; step < 12 && !(await page.locator("#zoom-in").isDisabled()); step++)
      await page.locator("#zoom-in").click();
    assert.equal(await page.locator("#zoom-level").innerText(), "800%");
    assert.equal(await page.locator("#zoom-in").isDisabled(), true);
    const plotRect = await plotRectangle(page);
    const clipping = await page.locator("#main-chart svg").evaluate((svg, [left, right, top, bottom]) => {
      const points = [...svg.querySelectorAll(".point")];
      const outside = point => {
        const x = Number(point.getAttribute("cx")), y = Number(point.getAttribute("cy"));
        return x < left || x > right || y < top || y > bottom;
      };
      return {
        outside: points.some(outside),
        outsideNotFocusable: points.filter(outside).every(point =>
          point.getAttribute("tabindex") === "-1" && point.getAttribute("aria-hidden") === "true"),
        clipped: points.every(point => {
          const layer = point.closest("[clip-path]");
          const id = layer?.getAttribute("clip-path")?.match(/url\(#([^)]*)\)/)?.[1];
          const rect = id ? svg.querySelector(`#${CSS.escape(id)} rect`) : null;
          if (!rect) return false;
          const actual = ["x", "y", "width", "height"].map(name => Number(rect.getAttribute(name)));
          return actual.every((value, index) => Math.abs(value - [left, top, right - left, bottom - top][index]) < 1e-8);
        }),
      };
    }, plotRect);
    assert.equal(clipping.outside, true, "Extreme zoom exercises points beyond the visible plot frame");
    assert.equal(clipping.clipped, true, "Every plotted point is clipped to the plot rectangle");
    assert.equal(clipping.outsideNotFocusable, true, "Clipped points outside the viewport do not become invisible keyboard targets");
    await page.locator("#zoom-reset").click();
    assert.deepEqual(await chartBounds(page), rawBounds);
    await page.locator('[data-view="aligned"]').click();
    results.push("Zoom buttons, cursor-centered wheel zoom, drag pan, independent persistent viewports, 800% cap, clipping, and reset");

    const baselinePosition = congresses.findIndex(item => item.congress === 96);
    await page.locator("#congress-dots .timeline-dot").nth(baselinePosition).click();
    await waitForCongress(96);
    await assertTimeline(96);
    await selectCongress(current.congress);
    await page.locator("#compare-button").click();
    await page.locator("#comparison-panel svg").first().waitFor();
    assert.equal(await page.locator("#comparison-panel svg").count(), 2);
    for (const view of ["aligned", "spectral", "aligned"]) {
      await page.locator(`[data-view="${view}"]`).click();
      const aligned = view === "aligned";
      const mode = aligned ? "aligned" : "raw";
      await page.waitForFunction(expected => [...document.querySelectorAll("#comparison-panel svg > title")]
        .every(title => title.textContent.toLowerCase().includes(expected)), mode);
      const comparisonBounds = await page.locator("#comparison-panel svg").evaluateAll(charts =>
        charts.map(svg => ["xMin", "xMax", "yMin", "yMax"].map(key => Number(svg.dataset[key]))));
      const expectedBounds = aligned ? alignedBounds : rawBounds;
      assert.deepEqual(comparisonBounds, [expectedBounds, expectedBounds], `${mode} comparison uses the main chart's fixed axes`);
      assert.ok((await page.locator("#comparison-panel svg > title").allTextContents()).every(title => /spectral/i.test(title)));
    }
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
      await page.locator('[data-view="spectral"]').click();
      assert.equal(await page.locator("#zoom-level").innerText(), "100%");
      await page.locator("#senator-search").fill("");
      await clickWhitespace(page);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: path.join(imageDir, "explorer-desktop.png"), fullPage: true });
      await page.locator("#explorer").screenshot({ path: path.join(imageDir, "explorer-geometry.png") });
      await page.locator('[data-view="aligned"]').click();
      await page.locator("#senator-search").fill("Rand Paul");
      await page.locator("#search-results button").click();
      await page.locator("#senator-search").fill("");
      await page.locator("#member-trail").waitFor();
      await page.locator("#explorer").screenshot({ path: path.join(imageDir, "explorer-alignment.png") });
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

    const guarded = await browser.newPage();
    const guardedErrors = [];
    guarded.on("pageerror", error => guardedErrors.push(error.message));
    try {
      let fixture = structuredClone(snapshot119);
      let predecessorAvailable = true;
      await guarded.route("**/data/congresses/119.json", route => route.fulfill({ json: fixture }));
      await guarded.route("**/data/congresses/118.json", route => predecessorAvailable
        ? route.fulfill({ json: snapshot118 }) : route.fulfill({ status: 503, body: "Unavailable" }));
      const guardedURL = new URL(base);
      guardedURL.searchParams.set("congress", "119");
      guardedURL.searchParams.set("view", "ideology");
      guardedURL.searchParams.set("align", "raw");
      await guarded.goto(guardedURL.href, { waitUntil: "networkidle" });
      await waitForCongress(119, guarded);
      assert.equal(await guarded.locator('[data-view="spectral"]').getAttribute("aria-pressed"), "true");
      assert.notEqual(new URL(guarded.url()).searchParams.get("view"), "ideology", "Old ideology URLs fall back to spectral geometry");
      assert.equal(new URL(guarded.url()).searchParams.has("align"), false, "The retired alignment checkbox parameter is removed");
      await assertCoordinates(guarded, paul.id, paul.x, paul.y, "Legacy URL falls back to original Geometry");
      await guarded.locator('[data-view="aligned"]').click();
      for (const scenario of ["different-segment", "not-an-anchor", "reset", "missing-predecessor"]) {
        fixture = structuredClone(snapshot119);
        predecessorAvailable = scenario !== "missing-predecessor";
        if (scenario === "different-segment") fixture.alignment.segment_id = -1;
        if (scenario === "not-an-anchor") fixture.alignment.anchor_ids = fixture.alignment.anchor_ids.filter(id => id !== paul.id);
        if (scenario === "reset") fixture.alignment.status = "reset";
        await guarded.reload({ waitUntil: "networkidle" });
        await waitForCongress(119, guarded);
        await guarded.locator("#senator-search").fill("Rand Paul");
        await guarded.locator("#search-results button").click();
        await guarded.waitForLoadState("networkidle");
        assert.equal(await guarded.locator("#main-chart .point").count(), snapshot119.members, `${scenario}: current Congress remains usable`);
        assert.equal(await guarded.locator('#main-chart .point[data-id="41104"].selected').count(), 1);
        assert.equal(await guarded.locator("#member-trail").count(), 0, `${scenario}: no unsupported movement trail`);
        assert.doesNotMatch(await guarded.locator("#senator-detail").innerText(), /CHANGE SINCE/, `${scenario}: no unsupported numerical movement`);
        await assertCoordinates(guarded, paul.id, paul.aligned_x, paul.aligned_y, `${scenario} preserves current geometry`);
      }
      assert.deepEqual(guardedErrors, [], "Missing or incomparable predecessors never crash the chart");
    } finally { await guarded.close(); }
    results.push("Legacy ideology links resolve to geometry; movement is suppressed across alignment resets, segment boundaries, missing anchors, and unavailable predecessors");

    const invalid = await browser.newPage();
    const invalidErrors = [];
    invalid.on("pageerror", error => invalidErrors.push(error.message));
    try {
      let fixture;
      await invalid.route("**/data/congresses/119.json", route => route.fulfill({ json: fixture }));
      const invalidURL = new URL(base);
      invalidURL.searchParams.set("congress", "119");
      for (const scenario of ["missing-alignment", "missing-coordinate", "nonfinite-coordinate"]) {
        fixture = structuredClone(snapshot119);
        if (scenario === "missing-alignment") delete fixture.alignment;
        if (scenario === "missing-coordinate") delete fixture.nodes[0].aligned_x;
        // JSON cannot encode NaN; a null coordinate is likewise not a finite number.
        if (scenario === "nonfinite-coordinate") fixture.nodes[0].aligned_y = null;
        await invalid.goto(invalidURL.href, { waitUntil: "networkidle" });
        await invalid.locator("#load-error:not([hidden])").waitFor();
        assert.match(await invalid.locator("#load-error").innerText(), /alignment data[\s\S]*refresh/i,
          `${scenario}: the error identifies incomplete alignment and tells the user how to refresh`);
        assert.equal(await invalid.locator("#main-chart .point").count(), 0);
        assert.doesNotMatch(await invalid.locator("#main-chart").innerHTML(), /NaN|Infinity/,
          `${scenario}: invalid source coordinates never become an SVG point`);
        await selectCongress(first.congress, invalid);
        const validChart = await invalid.locator("#main-chart").innerHTML();
        await setSlider(119, invalid);
        await invalid.locator("#load-error:not([hidden])").waitFor();
        await waitForCongress(first.congress, invalid);
        await assertTimeline(first.congress, invalid);
        assert.match(await invalid.locator("#load-error").innerText(), /alignment data[\s\S]*refresh/i);
        assert.equal(await invalid.locator("#main-chart").innerHTML(), validChart,
          `${scenario}: rejected navigation preserves the previous valid chart`);
      }
      assert.deepEqual(invalidErrors, [], "Invalid alignment snapshots produce a handled load error");
    } finally { await invalid.close(); }
    results.push("Incomplete alignment metadata or coordinates produce actionable refresh errors, never NaN charts, and preserve a valid chart on failed navigation");

    const race = await browser.newPage();
    const raceErrors = [];
    race.on("pageerror", error => raceErrors.push(error.message));
    try {
      const initialURL = new URL(base);
      initialURL.searchParams.set("congress", first.congress);
      initialURL.searchParams.set("view", "aligned");
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
      await race.locator("#senator-search").fill("Rand Paul");
      await race.locator("#search-results button").click();
      assert.equal(await race.locator("#member-trail").count(), 0, "The predecessor is still loading");
      const lastChart = await race.locator("#main-chart").innerHTML();
      await race.route(`**/data/congresses/${failedCongress}.json`, route => route.fulfill({ status: 503, body: "Unavailable" }));
      await setSlider(failedCongress, race);
      await race.locator("#load-error:not([hidden])").waitFor();
      await waitForCongress(current.congress, race);
      await assertTimeline(current.congress, race);
      assert.equal(await race.locator("#main-chart").innerHTML(), lastChart, "Failed selection preserves the last rendered chart");
      assert.match(await race.locator("#load-error").innerText(), /503/);
      assert.equal(new URL(race.url()).searchParams.get("congress"), String(current.congress));
      const delayedResponse = race.waitForResponse(response => response.url().endsWith(`/data/congresses/${delayedCongress}.json`));
      releaseDelayed();
      await (await delayedResponse).finished();
      await race.locator("#member-trail").waitFor();
      assert.match(await race.locator("#senator-detail").innerText(), /CHANGE SINCE/,
        "A failed intervening selection does not strand the current senator's predecessor request");
      await waitForCongress(current.congress, race);
      await assertTimeline(current.congress, race);
      assert.equal(new URL(race.url()).searchParams.get("congress"), String(current.congress));
      assert.equal(await race.locator("#member-trail").getAttribute("data-member-id"), String(paul.id));
      assert.equal(await race.locator("#member-trail").getAttribute("data-from-congress"), String(delayedCongress));
      assert.equal(await race.locator("#member-trail").getAttribute("data-to-congress"), String(current.congress));
      assert.deepEqual(raceErrors, [], "Script errors during rapid or failed selection");
    } finally { await race.close(); }
    results.push("Delayed stale responses cannot replace the newest Congress; failed selection preserves the chart and still allows its pending predecessor trail to finish");

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
