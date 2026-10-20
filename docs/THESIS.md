# The thesis behind Eigen-Politics

**Eigen-Politics: A Spectral Analysis of the US Senate** is Maximilian Chelminski's 2026 master's thesis in Quantitative Methods in the Social Sciences, Graduate School of Arts and Sciences, supervised by Gregory Eirich. Those details are transcribed from the supplied title page.

The repository preserves the [original PDF](../2026%20Master%27s%20Thesis.pdf), [Word document](../2026%20Master%27s%20Thesis.docx), and exploratory Python scripts. The interactive site and maintained analysis are a continuation of that research. They include documented implementation corrections and use a refreshable data source, so their results should not be presented as an exact reproduction of the thesis.

## Research question

How has the structure of voting similarity in the United States Senate changed over time? Beyond the distance between party positions, are there changes in network bottlenecks, the distribution of potential brokers, and the geometry of legislators' voting records?

The thesis builds a weighted network for each Congress from pairwise correlations of Senate roll-call records. It examines the normalized graph Laplacian, its second-smallest eigenvalue, a spectral sweep cut, and shortest-path betweenness centrality. It emphasizes the contrast between the 96th Congress (1979-1981) and the 119th Congress (2025-2027), alongside a historical analysis spanning Congresses 1 through 119.

The source manuscript gives **May 5, 2026** as its data collection date in Section 4. The 119th Congress was therefore an incomplete observation. The label 2025-2027 is its term, not a claim that the thesis observed votes through 2027.

## Reading guide

The PDF has a title page followed by numbered pages. The locations below give the PDF page first, then the printed page.

| Topic | Location |
| --- | --- |
| Research question and hypotheses | PDF pages 5-8; printed pages 4-7 |
| Literature and institutional context | PDF pages 9-14; printed pages 8-13 |
| Voteview data and graph construction | PDF pages 15-19; printed pages 14-18 |
| Historical and comparative figures | PDF pages 20-30; printed pages 19-29 |
| Results and comparison table | PDF pages 31-34; printed pages 30-33 |
| Democratic theory and interpretation | PDF pages 35-38; printed pages 34-37 |
| Conclusion and limitations | PDF pages 39-41; printed pages 38-40 |
| References | PDF pages 42-43; printed pages 41-42 |

The graph construction is explained in more reproducible terms in [Methodology](METHODOLOGY.md), including what changed in the maintained pipeline.

## Results reported in the manuscript

These are **archival values reported by the thesis**, transcribed from Table 6.1 on PDF page 34 and verified against the rendered table. They are not newly computed results, and they should not be used as test expectations for the revised pipeline.

| Thesis measure | 96th Senate | 119th Senate |
| --- | ---: | ---: |
| Fiedler value, normalized Laplacian λ₂ | 0.848 | 0.269 |
| “Cheeger constant” in the thesis; implemented as a sweep estimate | 0.443 | 0.156 |
| Inverse Fiedler value, 1/λ₂, rounded | 1.2 | 3.7 |
| Maximum betweenness centrality | 0.004 | 0 |

The manuscript interprets the historical trajectory as a decline in connectivity, stronger partisan bottlenecks, and a shift away from broadly distributed brokerage. Its spectral plots contrast a more overlapping earlier configuration with more separated contemporary party clusters.

The reported eigenvalues imply an inverse-Fiedler ratio of approximately `0.848 / 0.269 = 3.15`. The manuscript's results section describes about 3.16 times using its underlying values; its conclusion instead describes a factor of 3.7. The latter is the rounded contemporary inverse-Fiedler value, not the ratio in Table 6.1.

These observations motivate further research. They do not by themselves identify a causal effect of a historical event, prove a discontinuous phase transition, or establish the probability that a bill will pass.

## What the repository clarifies

### A weighted network and a thresholded network answer different questions

The thesis computes λ₂ on a graph with weights `A = (correlation + 1) / 2`. Its network drawings and betweenness calculation then discard some weak edges. The resulting thresholded graph is a different object.

A positive λ₂, including the thesis's 0.269, is consistent with a connected weighted graph. A drawing that omits weak edges may show disconnected components even when that underlying graph remains connected. The site therefore describes **bottlenecks and partisan clustering**, and any component count must be interpreted with the threshold used to construct that graph.

The term “bipartite” in the manuscript should also be read cautiously. In graph theory, a bipartite graph allows edges only between its two vertex classes. Two party clusters with dense internal ties are better described as a two-community or two-block structure.

### The implemented threshold was on similarity, not raw correlation

The original scripts retain edges at or above similarity 0.5 for centrality, and draw edges above similarity 0.5 for the interactive network. Since similarity is `(r + 1) / 2`, these correspond to raw correlation at or above zero, or above zero, respectively. Some figure captions instead describe a correlation threshold of 0.5. A raw-correlation threshold of 0.5 would correspond to similarity 0.75.

### A spectral sweep is not an exhaustive search

The original sweep evaluates a sequence of cuts after sorting an eigenvector. It does not inspect every possible partition. Its best conductance is an estimate and an upper bound on the graph's globally minimum conductance, not an exact evaluation of the Cheeger constant.

A spectral partition is also not guaranteed to equal the party partition. Conductance describes the fraction of weighted degree crossing a chosen cut. It is not a literal percentage of bipartisan bills or shared roll-call votes.

### Brokerage required a code correction

In both original scripts, the graph used for centrality is copied before the intended `distance` attributes are added to the original graph. Those new attributes do not reach the copied graph. As a result, the original computation uses default unit edge distances on its retained edges.

The maintained implementation adds positive distances to the graph actually analyzed. That makes the calculation match its intended weighted shortest-path model, but it changes the numerical estimand. In particular, the manuscript's centrality values and its interpretation of zero centrality must not be carried over without recalculation.

Shortest-path centrality is a model of structural position. It does not directly measure a senator's legislative influence, bargaining leverage, or necessity for a specific coalition.

The first maintained snapshot exposed a consequential limitation inherited from zero-coding nonservice. In the superseded **methodology 1.0.0** build of the 119th Congress on October 20, 2026, Marco Rubio had only eight encoded votes among 915 roll calls, yet the largest computed betweenness, approximately 0.501844. The other 907 entries were filled with zero. This short-record artifact is a reason to study missingness and tenure before interpreting brokerage rankings. The original scripts excluded Rubio by ID; the first maintained baseline used only the general metadata and minimum-record rules, making the problem visible.

Methodology 1.1.0 temporarily excluded Rubio from Congress 119 by identifier. **Methodology 1.2.0 replaces that exception with the same rule in every Congress: at least 20 usable votes and coverage of 10% of eligible Senate roll calls.** All graphs and statistics are recalculated after filtering. This removes exceptionally short records without selecting people by name, though it does not eliminate missingness effects among retained members. [Methodology](METHODOLOGY.md#a-concrete-short-record-artifact-in-the-initial-snapshot) and the [dated outlier audit](DATA_AUDIT.md) retain the superseded diagnostics. The original thesis and scripts remain unchanged.

### Following the thesis's spectral geometry over time

Methodology **1.3.0** aligns adjacent Congresses through the senators who served in both, using their positions in the thesis-derived spectral maps. The fit rotates or reflects and translates each new map without rescaling it. This preserves within-Congress distances and every graph statistic while allowing continuing senators to move relative to one another. The raw eigenvectors remain available alongside the aligned display.

The anchors define a relative reference frame; their aggregate shift is removed by construction. A continuing senator's displayed movement describes a change in structural position relative to colleagues, rather than an absolute policy shift. Aligned axes mix the two raw spectral dimensions and are not themselves individual eigenvectors. The [alignment methodology](METHODOLOGY.md#alignment-through-shared-senators) specifies these assumptions, diagnostic fields, and the handling of gaps or insufficient overlap.

### Random walks are an analogy, not observed persuasion

The thesis's `1/λ₂` quantity describes a spectral timescale. It does not directly count legislative steps, estimate a bill's passage probability, or calculate an individual pair's hitting time. General discrete-time mixing statements additionally depend on the walk definition, stationary distribution, error tolerance, and absolute spectral gap. A finite connected weighted network does not acquire infinite hitting times simply because its positive λ₂ decreases.

The maintained analysis labels this quantity an **inverse-Fiedler proxy**. It makes no empirical claim that congressional negotiation follows a random walk.

## Limitations retained from the thesis

The manuscript itself identifies several substantive limitations worth keeping visible:

- Roll calls reflect agenda control, procedural votes, and the bundling of issues. They are not an unfiltered measurement of every senator's policy preferences.
- Spectral axes need substantive interpretation. A second eigenvector is not automatically a geographic, regional, or policy dimension.
- Shifting correlation into nonnegative weights changes how disagreement is represented. Perfect negative correlation becomes a zero-weight relationship.
- Cosponsorship networks offer a complementary source for future analysis of legislative relationships.

The maintained pipeline adds further implementation and interpretation notes in [Methodology](METHODOLOGY.md), especially around non-voting entries, incomplete terms, membership turnover, threshold sensitivity, and reproducibility.

## Where to take the research next

1. Compare the retained zero-coding convention with pairwise jointly observed votes, including a minimum overlap requirement.
2. Repeat the analysis across several edge thresholds and minimum participation requirements.
3. Separate nominations, procedural votes, final passage, and policy categories where metadata allows.
4. Check shared-senator alignment against alternative anchor choices and compare voting-network structure with cosponsorship networks.
5. Use rolling windows or matched partial-term samples to compare an in-progress Congress with earlier ones fairly.
6. Quantify uncertainty and formally test changes over time before using language such as “phase transition” or attributing a change to a particular event.
7. Archive the raw source snapshot, pipeline version, settings, and environment used for any publication.

These are research extensions. The dashboard applies one minimum-vote specification and a documented shared-senator alignment; it does not perform these broader comparisons or robustness studies.

## Citation

Chelminski, Maximilian. 2026. *Eigen-Politics: A Spectral Analysis of the US Senate*. Master's thesis, Quantitative Methods in the Social Sciences, Graduate School of Arts and Sciences.

For the underlying data, follow [Voteview's requested citation](https://voteview.com/data):

Lewis, Jeffrey B., Keith Poole, Howard Rosenthal, Adam Boche, Aaron Rudkin, and Luke Sonnet. 2026. *Voteview: Congressional Roll-Call Votes Database*. https://voteview.com/

The repository's [citation metadata](../CITATION.cff) provides a machine-readable entry. Cite the original thesis when discussing its historical claims; identify the repository version and data snapshot when citing newly generated results.
