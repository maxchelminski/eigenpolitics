# Local development

## View the explorer

The frontend is plain HTML, CSS, JavaScript, and checked-in JSON. It does not require npm, a frontend build, an account, or a data-service credential.

With Python 3.11 or newer installed, run this from the repository root:

```bash
python scripts/serve.py
```

Open [localhost:4173](http://127.0.0.1:4173). Stop the server with `Ctrl+C`. The server serves only `site/` and binds to the loopback address by default.

On Windows:

```powershell
.\scripts\start.ps1 -OpenBrowser
```

Both launchers resolve paths from their own location, so they also work when invoked with an absolute path from another directory. If PowerShell's script policy prevents the convenience launcher from running, use the Python command.

An alternate port is available:

```bash
python scripts/serve.py --port 4174 --open
```

Use an HTTP server instead of opening `site/index.html` as a file: the application fetches its JSON over HTTP.

## Optional local automatic refresh

Install the dependencies described below, then enable the refresh loop:

```bash
python scripts/serve.py --refresh-hours 6
```

The equivalent Windows launcher command is:

```powershell
.\scripts\start.ps1 -Live -OpenBrowser
```

The server immediately starts a background `refresh_data.py --congress current --refresh` subprocess. After each attempt completes, it waits the configured number of hours before trying again. Only one refresh runs at a time; each attempt has a 20-minute timeout. Output and failures are logged in the server terminal. The HTTP server keeps serving the available snapshot during this work.

`--refresh-hours` accepts a finite positive number, including fractions. Omit it to serve the existing files without automatic refresh. `Ctrl+C` stops the server and terminates an active refresh subprocess.

This is an in-process convenience, not an installed operating-system schedule. It runs only while the server is running and the computer is awake; closing it or restarting the computer ends the loop. Voteview may publish data later than the Senate's latest activity, so a successful fetch does not imply that every recent vote is available.

The browser periodically checks the published data manifest; reload the page to check immediately. No HTTP endpoint can start a refresh. The server's timer and explicit command-line actions control updates.

## Refresh the underlying data

Viewing the included snapshot uses only the Python standard library. Recomputing it requires the scientific Python dependencies:

```bash
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS or Linux
source .venv/bin/activate
```

Then install dependencies and refresh the current Congress:

```bash
python -m pip install -r requirements.txt
python scripts/refresh_data.py --congress current --refresh
```

The refresh downloads current Voteview inputs, computes the Senate graph and spectral results, writes the selected Congress JSON, and updates the index while retaining other available Congresses. Reload the browser to use the new snapshot. The browser does not poll Voteview; the data timestamp records when the pipeline last retrieved its inputs.

See the command's current options:

```bash
python scripts/refresh_data.py --help
```

Source downloads are cached locally under `.cache/`, which is excluded from Git. The `--refresh` flag asks for new source data rather than reusing that cache. Keep generated `site/data/` snapshots under version control when you want a reproducible repository state.

## Project layout

| Path | Purpose |
| --- | --- |
| `site/index.html` | Explorer page structure |
| `site/styles.css` | Responsive visual design |
| `site/app.js` | Data loading, controls, and charts |
| `site/data/index.json` | Available Congresses and aggregate history |
| `site/data/congresses/` | Detailed generated snapshot for each Congress |
| `site/research/thesis.pdf` | Unmodified copy of the original thesis for the site's PDF link |
| `scripts/refresh_data.py` | Source download and spectral analysis |
| `eigenpolitics/` | Reusable analysis, source-validation, and command-line implementation |
| `scripts/serve.py` | Local static server |
| `scripts/start.ps1` | Windows convenience launcher |
| `tests/` | Data and mathematical regression tests |
| `docs/images/` | Real screenshots and generated figures |
| `.github/workflows/` | Validation and optional hosted refresh/deployment |

The four original files remain at the repository root so their original names and contents are preserved.

## Checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q scripts eigenpolitics
node --check site/app.js
```

Tests should run without downloading live data. Network retrieval is a separate operation so upstream downtime does not turn mathematical regression checks into flaky tests.

After changing the interface, inspect it at desktop and narrow mobile widths. Check loading and error states, change Congress, search for a member, and verify that the selected member's numbers match the generated JSON.

### Browser checks and screenshots

The optional Node development dependency is locked in `package-lock.json`. With Node 22+:

```bash
npm ci
npx playwright install chromium
```

Keep the local server running in another terminal, then run:

```bash
npm run test:browser
npm run screenshots
```

These checks exercise live timeline input, clickable Congress points, keyboard navigation, fixed axes across all four views, NOMINATE source coordinates and missing scores, rapid-selection races, failure rollback, minimum-vote exclusions, search, comparison, downloads, and narrow layouts. The screenshots command replaces the desktop, mobile, ideology, and network screenshots under `docs/images/` with real captures of the current snapshot.

The slider indexes the available manifest entries, so gaps in historical data do not create invalid selections. Requests carry a selection counter: only the latest selection can replace the chart, and a failed latest request restores the last displayed Congress. In-flight loads are shared and scoped to the manifest generation. `axis_bounds` is calculated during publication from all retained snapshots, so the browser does not download every Congress merely to establish a fixed plotting frame.

Ideology has fixed `[-1, 1]` limits and uses the source `nominate_dim1` and `nominate_dim2` fields. A `view=ideology` URL preserves that mode when reloading. Missing score pairs are omitted only from that plot; the graph analysis and member search retain those senators. See [Methodology](METHODOLOGY.md#nominate-common-scale-view) for source-vintage considerations when refreshing longitudinal data.

To use an installed Edge browser on Windows instead of downloading Chromium:

```powershell
$env:BROWSER_CHANNEL = "msedge"
npm run screenshots
```

Set `SITE_URL` to test another local server address. For data figures, install `python -m pip install -e ".[figures]"` and run `python scripts/render_figures.py --svg`. Figure generation reads the existing JSON without downloading data.

## Common issues

| Symptom | Fix |
| --- | --- |
| Python is not recognized | Install Python 3.11+, or use the Windows `py -3` launcher. |
| Port 4173 is already in use | Add `--port 4174`. |
| Browser reports a data-loading error | Use the local HTTP server and check that `site/data/index.json` exists. |
| Results still show an older retrieval date | Run the refresh command or start the server with `--refresh-hours 6`, then inspect the logs and reload the page. The default server command does not refresh data. |
| Download or refresh fails | Check the command's error, network access, and Voteview availability. The checked-in snapshot remains available for local browsing. |
| A chart differs from the thesis | Read [the method and interpretation notes](METHODOLOGY.md); the companion uses refreshed inputs and an explicit implementation. |
