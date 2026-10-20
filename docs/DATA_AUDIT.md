# 119th Congress outlier audit

This audit was performed on **October 20, 2026** in response to unexpectedly isolated Republican points. It describes the original maintained **methodology 1.0.0** snapshot, generated at `2026-10-20T16:25:27Z`, with **915 roll calls dated January 9, 2025–September 30, 2026**. Its 103 nodes represent people who served during the Congress, including departures and replacements; they are not a roster of the 100 senators serving on the final date.

The most conspicuous vertical outliers were **Darline Graham and Alan Armstrong**. Both are legitimate senators with short records in this Congress. **Rand Paul, Susan Collins, and Lisa Murkowski** also stand apart from the Republican cluster, with much fuller records and appreciably more votes against their party's majority. The original plot's geometry mixes these different phenomena because missing entries, including time outside Senate service, are encoded as zero.

## Which names are in the original plot?

Coordinates below are the original snapshot's normalized-Laplacian eigenvectors, rounded to four decimal places. They are descriptive coordinates, not ideological scores. Coverage is usable yea/nay entries divided by all 915 roll calls, not attendance during a senator's tenure.

| Republican member | State | Voteview ID | Original x | Original y | Usable votes | Coverage | First–last usable vote in source |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Darline Graham | SC | 42508 | 0.0106 | 0.3941 | 55 | 6.01% | 2026-07-14–2026-09-30 |
| Alan Armstrong | OK | 42507 | 0.0404 | 0.3766 | 191 | 20.87% | 2026-03-24–2026-09-30 |
| Markwayne Mullin | OK | 21355 | 0.0772 | −0.1906 | 683 | 74.64% | 2025-01-09–2026-03-23 |
| Rand Paul | KY | 41104 | 0.0689 | 0.1857 | 871 | 95.19% | 2025-01-09–2026-09-30 |
| Susan Collins | ME | 49703 | 0.0481 | −0.1301 | 915 | 100.00% | 2025-01-09–2026-09-30 |
| Lindsey Graham | SC | 29566 | 0.0864 | −0.0967 | 794 | 86.78% | 2025-01-09–2026-06-24 |
| Lisa Murkowski | AK | 40300 | 0.0536 | −0.0960 | 877 | 95.85% | 2025-01-13–2026-09-30 |
| Marco Rubio | FL | 41102 | −0.0063 | −0.0225 | 8 | 0.87% | 2025-01-09–2025-01-20 |

Darline Graham's [official Senate biography](https://www.dgraham.senate.gov/) records her oath on July 14, 2026, following appointment to Lindsey Graham's vacant seat. Alan Armstrong's [official biography](https://www.armstrong.senate.gov/about/) records his oath on March 24, 2026, following Markwayne Mullin's departure to become secretary of Homeland Security. Their first usable dates in this source match those oath dates. The [Senate's current roster](https://www.senate.gov/senators/index.htm), checked on the audit date, also lists Graham, Armstrong, Paul, Collins, and Murkowski.

The [Senate's Florida service history](https://www.senate.gov/states/FL/senators.htm) records Rubio's resignation on January 20, 2025. His eight observations are a valid historical record, but too short to support a reliable position in this full-Congress network. With 907 matrix entries filled with zero, his original normalized betweenness was **0.501844**, the largest in this snapshot. This should not be interpreted as demonstrated political brokerage.

No invalid office or invented identity was found among the named plotted points checked above. Partial service still matters statistically, even when membership is legitimate.

## Donald Trump and J. D. Vance

- **Donald Trump (ID 99912) is absent from the plotted graph.** The raw votes file has 145 Senate-labelled records for this identifier, but the members file identifies him as `chamber = President`, `state_icpsr = 99`, and `state_abbrev = USA`. The maintained pipeline's member-metadata eligibility check excludes him. Filtering only the votes file's chamber would incorrectly admit these records.
- **J. D. Vance (ID 42304) is also absent from the plotted graph.** His Ohio Senate record has one usable vote, on January 9, 2025, and the original maintained pipeline excludes records with fewer than two usable votes. The [Senate's Ohio service history](https://www.senate.gov/states/OH/senators.htm) records his resignation on January 10, 2025. His brief Senate service in the 119th Congress is legitimate; it does not supply a meaningful full-Congress voting profile.

The preserved thesis scripts exclude IDs `42304`, `41102`, and `99912` explicitly. The maintained implementation instead uses chamber/state metadata and a general minimum-record rule. The two-vote minimum in methodology 1.0.0 protects the calculation from some invalid inputs, but it is not a statistical adequacy threshold.

## Diagnostic: observed votes versus zero-filled tenure

Two checks help distinguish voting differences from missing-record effects. These are diagnostics of the source snapshot, not a replacement fitted model or a causal interpretation.

For each senator, the first check counts votes against the majority position of **other Republican senators on the same roll call**. It uses Voteview cast codes 1–3 as yea and 4–6 as nay, omits all other codes, excludes tied party votes, and requires at least ten other Republicans with usable votes. Paul's denominator is 870 rather than 871 because one applicable party vote is tied.

The second check compares the senator with each other Republican having at least 20 jointly observed usable votes and variable records on those jointly observed votes. It reports the median Pearson correlation across those pairs, first using only their jointly observed votes and then using the original zero-filled 915-column records for **the same pairs**.

| Member | Against other Republicans' majority | Rate | Median correlation on jointly observed votes | Median correlation with zero filling |
| --- | ---: | ---: | ---: | ---: |
| Darline Graham | 1 / 55 | 1.82% | 0.9265 | 0.1878 |
| Alan Armstrong | 3 / 191 | 1.57% | 0.9563 | 0.4402 |
| Markwayne Mullin | 5 / 683 | 0.73% | 0.9670 | 0.7875 |
| Rand Paul | 138 / 870 | 15.86% | 0.6341 | 0.6055 |
| Susan Collins | 144 / 915 | 15.74% | 0.5532 | 0.5422 |
| Lisa Murkowski | 123 / 877 | 14.03% | 0.6231 | 0.5875 |
| Lindsey Graham | 7 / 794 | 0.88% | 0.9651 | 0.8715 |
| Marco Rubio | 0 / 8 | 0.00% | Insufficient overlap | Insufficient overlap |

The large change in Graham's and Armstrong's pair correlations demonstrates that their short records substantially affect the similarity calculation. Their dramatic separation is not evidence that they voted unusually often against other Republicans. Mullin and Lindsey Graham show a similar, smaller effect associated with their partial-Congress records.

Paul, Collins, and Murkowski disagree more often with their Republican colleagues in the observed votes themselves. Calling them voting outliers is therefore better supported by this check, although direction in the spectral plot does not identify a specific ideology, issue, or motive.

Rubio's 0/8 dissent count is too small a record to infer a stable pattern. Neither this majority comparison nor pairwise correlation distinguishes substantive legislation from nominations, procedural votes, or repeated votes on the same issue.

## Reproducibility and boundaries

The numerical checks use these cached Voteview exports, fetched on October 20, 2026. The SHA-256 values match the provenance recorded in the original output:

| Source | SHA-256 |
| --- | --- |
| [S119 members](https://voteview.com/static/data/out/members/S119_members.csv) | `a497d542cce3b46760cdad978f92a3df59b2370fe86385606b262bd33948611f` |
| [S119 votes](https://voteview.com/static/data/out/votes/S119_votes.csv) | `d44e6b3f5a9849dc02edbf3e372b4158841f70589e74e9c03335ebeb05c981f1` |
| [S119 roll calls](https://voteview.com/static/data/out/rollcalls/S119_rollcalls.csv) | `7372967d13913c954f51dd815871566e5f57ed0b1d7c3fe2e7b55016c1a055e8` |

Vote counts and first/last dates above are computed from the cached rows, joined to roll-call metadata by `rollnumber`. The date range of usable votes is not itself a legal service-date record; service details were checked separately against the official sources linked above. [Voteview's vote-code documentation](https://voteview.com/articles/data_help_votes) defines the cast codes.

This is a focused audit of the named outliers and executive contamination concern, not an independent verification of all 915 roll calls or every member's biography. Live exports and website biographies can change; this document deliberately preserves the dated baseline values even if the dashboard is regenerated. See [Methodology](METHODOLOGY.md) for the currently implemented population and missing-data rules.
