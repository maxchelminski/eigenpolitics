# Optional hosting and automatic updates

Local use is ready with `python scripts/serve.py`. No hosting, domain, GitHub repository, or scheduled job is required for that workflow.

For local updates while the computer is awake, install the analysis dependencies and run `python scripts/serve.py --refresh-hours 6` (or `.\scripts\start.ps1 -Live`). This starts an immediate background refresh and waits six hours between subsequent attempts. It stops with the server process and does not install a system schedule. See [local automatic refresh](DEVELOPMENT.md#optional-local-automatic-refresh).

The included Pages workflow is an opt-in path to a hosted research companion. It remains skipped until the repository variable `ENABLE_PAGES` is set to `true`.

## A public address without buying a domain

GitHub Pages serves static HTML, CSS, JavaScript, and JSON. A project site normally receives `https://<owner>.github.io/<repository>/`; a custom domain is optional. Public repositories can use Pages with GitHub Free. See [GitHub's description of Pages and default addresses](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages).

The site uses relative asset and data paths so it can work under a repository path as well as at the root of a local server.

## Publish when ready

1. Review the thesis files and choose the repository's visibility and licensing before uploading. The current project does not grant an open-source license.
2. Create an empty GitHub repository and push this repository to its `main` branch. If using another default branch, update the `push.branches` entry in `.github/workflows/pages.yml`.
3. In the repository, open **Settings → Pages → Build and deployment → Source**, and select **GitHub Actions**. GitHub documents this in [Configuring a publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
4. Under **Settings → Secrets and variables → Actions → Variables**, create the repository variable `ENABLE_PAGES` with the value `true`.
5. Open **Actions → Refresh data and deploy Pages → Run workflow** on the default branch.
6. Open the URL shown by the successful deployment. Keep the `github-pages` environment restricted to your intended deployment branch.

The workflow uses GitHub's built-in token and Pages actions. No personal access token, external API key, or domain configuration is needed. The required deployment permissions are limited to the publishing job. The action sequence follows [GitHub's custom Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## How the hosted data stays current

Once enabled, the workflow runs on pushes to `main`, manual dispatch, and a daily schedule at **10:23 UTC**. GitHub's scheduler is best effort; a scheduled run is not a guarantee of a particular publication time.

Each run checks out the repository, tests the pipeline, and restores `.cache/voteview` from the latest matching GitHub Actions source cache. It then downloads fresh inputs for the current and preceding Congresses and rebuilds the full history. Older source files are reused from the validated cache; missing or evicted files are downloaded again. The resulting `site/` directory is deployed, and a successful job saves the source cache under a new key for that run.

The current Congress is determined by the refresh script rather than hard-coded in the workflow. Refreshing the preceding Congress captures its final votes after a term change. Rebuilding from the saved source history carries those inputs forward on later runs, even though every workflow begins with a fresh repository checkout.

This is a periodically refreshed static site. Freshness depends on Voteview publishing new data and a successful workflow run. It is not a direct feed from the Senate floor.

The workflow **does not commit generated data back into the repository**. The deployed site can therefore be newer than the JSON files in Git. To preserve a new snapshot in Git, run the refresh locally and review and commit `site/data/`.

Historical source caches are reused, so an older Congress is not automatically downloaded again on every deployment. To request a fresh historical analysis locally, use `python scripts/refresh_data.py --congress NUMBER --refresh`, replacing `NUMBER` with the Congress. A local JSON commit does not change the runner's source cache. To force the hosted workflow to retrieve older inputs, add the desired Congress to its refresh command, or change the `voteview-source-v1-` prefix consistently in both the cache `key` and `restore-keys` to start a new full source cache.

If download, analysis, tests, or deployment fails, the workflow fails and the previous successful deployment remains available. Check the Actions run rather than assuming the date on the live site has advanced.

## Pause or change updates

- Set `ENABLE_PAGES` to `false` or remove it to skip future publishing jobs. This leaves the last published site available.
- Edit the `schedule` entry in `.github/workflows/pages.yml` to change the frequency.
- Disable the workflow in GitHub Actions to stop it entirely.
- Use GitHub Pages settings to unpublish the site when desired.

GitHub may delay scheduled runs and disables scheduled workflows in public repositories after prolonged inactivity. Review [GitHub's schedule event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) when deciding whether this cadence meets your needs.

## Other static hosts

The complete deployable artifact is the `site/` directory. A static host can serve it without running Python in production. To keep another host updated, run the same refresh pipeline in that host's build system or a separate scheduled job, then publish `site/`. Hosting the files alone does not update the dataset.
