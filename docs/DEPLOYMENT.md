# GitHub Pages hosting and automatic updates

Repository: [maxchelminski/eigenpolitics](https://github.com/maxchelminski/eigenpolitics). The configured project address is [maxchelminski.github.io/eigenpolitics](https://maxchelminski.github.io/eigenpolitics/); a successful Pages deployment makes the site available there.

Local use is ready with `python scripts/serve.py`. No hosting, domain, GitHub repository, or scheduled job is required for that workflow.

For local updates while the computer is awake, install the analysis dependencies and run `python scripts/serve.py --refresh-hours 6` (or `.\scripts\start.ps1 -Live`). This starts an immediate background refresh and waits six hours between subsequent attempts. It stops with the server process and does not install a system schedule. See [local automatic refresh](DEVELOPMENT.md#optional-local-automatic-refresh).

The included Pages workflow publishes the research companion and refreshes its data every six hours. It remains opt-in for forks: publishing jobs are skipped until the repository variable `ENABLE_PAGES` is set to `true`.

## Recommended first deployment

Use GitHub Pages for the public thesis site. The explorer is a static site: visitors' browsers draw the charts from published JSON, while a separate Python job refreshes that JSON. GitHub hosts the files and runs the refresh workflow, so neither an always-on home computer nor a purchased domain is necessary.

An NVIDIA Jetson Orin Nano Super can also serve the site or run the refresh pipeline. That is useful for learning self-hosting, but entails maintaining the device, web server, and public connection. The current analysis uses CPU-based NumPy, pandas, SciPy, and NetworkX; its GPU is not used.

## A public address without buying a domain

GitHub Pages serves static HTML, CSS, JavaScript, and JSON. A project site normally receives `https://<owner>.github.io/<repository>/`; a custom domain is optional. Public repositories can use Pages with GitHub Free. See [GitHub's description of Pages and default addresses](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).

The site uses relative asset and data paths so it can work under a repository path as well as at the root of a local server.

## Initial setup or publishing a fork

1. Review the thesis files, repository visibility, and the repository's licensing notes before uploading. Publishing a repository does not itself grant an open-source license.
2. Push the repository to its `main` branch. The project repository is already [maxchelminski/eigenpolitics](https://github.com/maxchelminski/eigenpolitics); use your own repository for a fork. If using another default branch, update every `main` reference in `.github/workflows/pages.yml`, including the trigger, branch guard, checkout, fetch, and push.
3. In the repository, open **Settings → Pages → Build and deployment → Source**, and select **GitHub Actions**. GitHub documents this in [Configuring a publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
4. Under **Settings → Secrets and variables → Actions → Variables**, create the repository variable `ENABLE_PAGES` with the value `true`.
5. A push to `main` publishes the checked-in snapshot. Open **Actions → Refresh data and deploy Pages → Run workflow** on `main` to download fresh data and publish it immediately.
6. Open the URL shown by the successful deployment. Keep the `github-pages` environment restricted to your intended deployment branch.

The workflow uses GitHub's built-in `GITHUB_TOKEN` and Pages actions. No personal access token, external API key, or domain configuration is needed. The publishing job requests `contents: write` to retain changed data snapshots, plus `pages: write` and `id-token: write` for deployment. Repository and organization policies must permit those permissions; branch protection that blocks the bot's normal push will stop a changed-data deployment. The action sequence follows [GitHub's custom Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## How the hosted data stays current

Once enabled, the workflow runs on pushes to `main`, manual dispatch, and every six hours at **00:23, 06:23, 12:23, and 18:23 UTC**. GitHub's scheduler is best effort; a scheduled run is not a guarantee of a particular publication time.

Every run checks out the latest `main`, runs the regression tests, and validates the checked-in data manifest and source checksums. The two publication paths are:

- **Push:** deploy the checked-in `site/` snapshot without fetching Voteview. A reviewed interface or documentation update can therefore publish during an upstream outage.
- **Scheduled or manual run:** `scripts/refresh_pages.py` downloads the current and preceding Congress's votes, members, and roll-call metadata: six CSV files. The pipeline recomputes those two analyses and realigns the complete published history from its raw coordinates. Other Congresses retain their graph calculations.

The current Congress is determined by the refresh script rather than hard-coded in the workflow. Refreshing the preceding Congress captures its final votes after a term change. Successfully changed snapshots are retained in Git, so those final inputs remain represented in later runs without relying on an Actions cache or downloading the full history again.

This is a periodically refreshed static site. Freshness depends on Voteview publishing new data and a successful workflow run. It is not a direct feed from the Senate floor.

The helper compares the source CSV SHA-256 hashes, methodology/schema versions, and set of Congresses before and after a refresh. When source content changes, `github-actions[bot]` commits the validated `site/data/` snapshot to `main` before deployment. When only retrieval/build timestamps change, it reports that the source content is unchanged and deploys the refreshed timestamps without adding a Git commit. The live retrieval timestamp can therefore be newer than the timestamp in Git even when their source data is identical.

Bot commits use the built-in token and do not recursively trigger another push workflow. Before changing files locally, synchronize the retained snapshots with `git pull --ff-only origin main`. A non-fast-forward pull needs normal Git reconciliation; do not force-push over the bot's history. The publishing workflow checks whether `main` changed while it was working and uses only a normal, non-forced push. A concurrent change fails the run instead of overwriting it; rerun from the latest `main`.

To update an older Congress, pull `main`, run `python scripts/refresh_data.py --congress NUMBER --refresh`, review the resulting `site/data/` changes, and commit and push them. A methodology or schema change requires rebuilding **all** published Congresses with `python scripts/refresh_data.py` before committing; use `--refresh` too if fresh historical source inputs are wanted. The snapshot validator rejects mismatched methodology/schema versions rather than mixing old and new calculations.

If download, analysis, snapshot validation, tests, snapshot push, or deployment fails, the workflow fails and the previous successful deployment remains available. Check the Actions run rather than assuming the date on the live site has advanced. A successful manual run is the simplest way to retry immediately; no artificial keepalive commits are created.

## Pause or change updates

- Set `ENABLE_PAGES` to `false` or remove it to skip future publishing jobs. This leaves the last published site available.
- Edit the `schedule` entry in `.github/workflows/pages.yml` to change the frequency.
- Disable the workflow in GitHub Actions to stop it entirely.
- Use GitHub Pages settings to unpublish the site when desired.

GitHub may delay scheduled runs and disables scheduled workflows in public repositories after 60 days without repository activity. Content-based bot commits do not guarantee activity during a long period with no source changes. Check that the workflow remains enabled; re-enable it and run it manually if GitHub pauses it. The last deployed site remains online while its data stops refreshing. Review [GitHub's schedule event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) when deciding whether this cadence meets your needs.

## Using an always-on Jetson

This is an optional setup outline, not an installed configuration. The device has not been accessed or tested.

1. Clone or copy the repository onto the Jetson. For data refreshes, create a Python virtual environment and install `requirements.txt`. The package requires Python 3.10 or newer; the documented development setup and GitHub workflow use 3.11 or newer. Check the device's Python version and ARM dependency installation before relying on unattended updates.
2. Configure a static web server such as [Caddy](https://caddyserver.com/docs/quick-starts/static-files) to serve only the repository's `site/` directory, listening on localhost. Use a system service to start it after reboot. The bundled `scripts/serve.py` remains the local development preview.
3. Configure a systemd timer to run `scripts/refresh_data.py --congress current --refresh` periodically from the repository with its virtual environment. The script also recalculates the alignment chain. Include the preceding Congress around a term change to capture its final published votes. Hosting alone does not refresh the data.
4. For a public address without buying a domain, configure [Tailscale Funnel](https://tailscale.com/docs/features/tailscale-funnel) to forward HTTPS requests to that local web server. It provides a device address such as `https://jetson.<tailnet>.ts.net`; visitors do not need Tailscale. It avoids router port forwarding and a public home IP. Enable the required Tailscale account, DNS, certificate, and Funnel settings, and configure persistent background operation as described in the [Funnel CLI documentation](https://tailscale.com/docs/reference/tailscale-cli/funnel).
5. Verify the site from outside the home network, test recovery after a reboot, and check the refresh logs and displayed snapshot date.

Funnel is available on all Tailscale plans, but is currently beta and has non-configurable bandwidth limits. A Jetson-hosted site depends on the device, home power, and home internet connection remaining available. For a public thesis link, GitHub Pages avoids those home-server dependencies.

The Jetson can alternatively run data refreshes while GitHub Pages hosts the resulting files. That hybrid setup needs a separate, authenticated deployment job; it is not required by the existing GitHub-hosted workflow.

## Other static hosts

The complete deployable artifact is the `site/` directory. A static host can serve it without running Python in production. To keep another host updated, run the same refresh pipeline in that host's build system or a separate scheduled job, then publish `site/`. Hosting the files alone does not update the dataset.
