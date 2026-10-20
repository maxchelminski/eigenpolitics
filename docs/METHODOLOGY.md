# Methodology

Eigen-Politics models each Senate as a network of similarities between roll-call voting records. The maintained pipeline continues the original thesis while correcting several implementation issues. Its output is descriptive network analysis, not a causal estimate of polarization or a forecast of legislation.

The [thesis guide](THESIS.md) preserves the original study's metadata, reported results, and interpretive context. This document describes the maintained calculation, **methodology 1.1.0**, and explains where it differs.

## Data and unit of analysis

The source is [Voteview's Congressional Roll-Call Votes Database](https://voteview.com/data). Voteview provides current and historical CSV exports and states that its data is updated as new votes arrive. A refresh is a new snapshot of that source, not a guarantee of instantaneous coverage.

For Congress `NNN`, the pipeline uses the Voteview votes and members exports. Roll-call metadata supplies source vote dates where available. Each observation in the analysis is a member's record within one Congress; each graph node is a retained member identifier.

The nominal Congress start year is `1789 + 2 × (Congress - 1)` and the end year is two years later. These labels describe congressional terms. Source date coverage and retrieval time must be reported separately. A later download can also revise earlier records.

Membership changes mean a graph can include more than 100 senators over a two-year term. The analysis is not a snapshot of the 100 seats on a particular day. Party colors come from member metadata, not estimated ideology; affiliations that change within a Congress need additional care.

## From roll calls to a matrix

The maintained pipeline retains records identified as Senate members in metadata and excludes the executive/non-state records identified by `state_icpsr = 99` or `state_abbrev = USA`. It keeps members with at least two usable yea/nay-coded entries and nonconstant encoded records. That minimum is a computational safeguard, not evidence that a short record is statistically reliable.

**Congress-specific analytical exclusion:** Starting with methodology **1.1.0**, Marco Rubio (Voteview ID `41102`) is excluded **only from Congress 119**, at the author's request. His brief Senate service before becoming secretary of state supplies only eight usable votes in the audited snapshot, making a full-Congress position unreliable under the retained zero-coding convention. This is an explicit modeling choice, not a finding that he was an invalid Senate member. The rule does not remove his earlier Congress records or apply automatically to future Congresses.

The exclusion runs before construction of the analyzed matrix, similarity graph, eigenvectors, and centrality statistics. Consequently the entire 119th Congress analysis is recomputed without Rubio; the browser does not merely hide his point. The exclusion and its reason are recorded in provenance and applied again on future refreshes. Other short-service members remain subject to the existing rules, so this exception does not resolve the general missingness and tenure limitation.

Each matrix row represents a retained member and each column a roll call. The inherited encoding is:

| Voteview cast code | Meaning | Encoded value |
| --- | --- | ---: |
| 1, 2, 3 | Yea, paired yea, announced yea | +1 |
| 4, 5, 6 | Announced nay, paired nay, nay | −1 |
| 7, 8, 9 | Present or not voting | 0 |
| 0 or missing entry | Not in the chamber for the vote, or no recorded entry | 0 |

The meanings of the source fields and cast codes are documented by [Voteview](https://voteview.com/articles/data_help_votes). All-zero roll-call columns are removed. Members whose encoded vectors have no variance cannot support a Pearson correlation and are removed. Unknown cast codes and duplicate member/roll-call records are treated as validation errors rather than silently averaged or assigned a political value.

**Zero is a modeling convention, not a neutral political preference.** It combines different situations, including abstention, absence, and non-overlapping service. Shared zeros can affect correlations; zeros outside a senator's service can move their coordinates. Paired and announced positions are also pooled with actual votes. The retained convention makes this extension recognizable as the thesis's analysis, but alternative missing-data treatments remain an important robustness exercise.

### A concrete short-record artifact in the initial snapshot

The superseded **methodology 1.0.0** snapshot of the 119th Congress, generated on **October 20, 2026**, with roll calls through **September 30, 2026**, included 103 members and 915 analyzed roll calls. Marco Rubio's source record contained only eight votes, dated January 9-20, 2025. That matrix filled his other 907 entries with zero. His eight encoded votes represented approximately **0.87% of the full-term matrix columns**, and his computed normalized betweenness was **0.501844**, the largest in that snapshot. These are preserved diagnostic values, not the current 1.1.0 output, which excludes Rubio from this Congress.

This is a concrete warning about the zero-coding model: a short service record can acquire an apparently central position when mostly missing observations are treated numerically as zero. The statistic is not evidence that Rubio was a uniquely influential intermediary across the observed Congress. It should not be used as a substantive ranking without a missingness and tenure sensitivity analysis.

The preserved thesis scripts explicitly remove Rubio by identifier. The first maintained baseline, methodology 1.0.0, applied only the general metadata and minimum-record rules, making this limitation inspectable. Methodology 1.1.0 adds the explicit Congress-119-only exclusion described above. A broader robustness specification should predefine a minimum record or jointly observed voting requirement and report how results change. Neither those alternatives nor an adjustment for service dates are implemented here.

The JSON field `participation_rate` is named for convenience but divides encoded nonzero entries by **all analyzed roll calls in the Congress**. It is record coverage, not attendance during the member's actual tenure. For replacement members and brief service, a low value must not be interpreted as habitual abstention. The [outlier audit](DATA_AUDIT.md) preserves the dated 1.0.0 diagnostics and source checksums. The [current 119th Congress output](../site/data/congresses/119.json) records the active methodology and can change with later refreshes.

## Similarity graph

For members `i` and `j`, compute the Pearson correlation `rᵢⱼ` between their encoded vote vectors. Transform it into a nonnegative edge weight:

```text
Aᵢⱼ = (rᵢⱼ + 1) / 2,  i ≠ j
Aᵢᵢ = 0
```

These weights are **rescaled correlations**, not agreement rates. A weight of 0.5 means zero correlation; 1 means perfect positive correlation; 0 means perfect negative correlation. For variable records, perfect correlation need not mean identical original votes. Even a zero-correlation pair receives a positive baseline weight.

The diagonal is zeroed before every graph calculation, so a senator's similarity with themself does not contribute to degree, conductance, or shortest paths. Floating-point bounds are handled numerically by the implementation.

An ordinary nonnegative weighted graph is a choice here. Signed networks can model positive and negative relationships differently and are a possible extension.

## Normalized Laplacian and geometry

Let `dᵢ = Σⱼ Aᵢⱼ` and `D = diag(d)`. On positive-degree vertices the symmetric normalized Laplacian is:

```text
L = I − D^(−1/2) A D^(−1/2)
```

Its eigenvalues are ordered `0 = λ₁ ≤ λ₂ ≤ … ≤ λₙ ≤ 2`. The second-smallest eigenvalue, λ₂, is called the Fiedler value here. Lower values indicate that a low-conductance partition is possible in this particular weighted graph. Exact disconnection produces additional zero eigenvalues; numerical calculations require a tolerance.

The first and second displayed spectral coordinates are the eigenvectors corresponding to λ₂ and λ₃. They describe low-frequency graph structure. Their signs are arbitrary, so the maintained pipeline chooses a deterministic sign for display and orients the first coordinate toward a higher Republican than Democratic mean when both groups are present. This is a visual convention and does not change λ₂.

Coordinates are not DW-NOMINATE scores, ideological probabilities, or comparable absolute units across Congresses. Close eigenvalues can make individual eigenvectors unstable under small data changes, and an entire eigenspace may rotate. A plot's axes therefore need to be interpreted within the selected Congress. Normalization controls one source of graph-size dependence; it does not make different agendas, memberships, and voting opportunities equivalent.

The timeline keeps the display limits fixed across the published Congresses. The manifest's `axis_bounds` covers all published node coordinates, adds 5% padding, and rounds limits outward to steps of 0.05. Horizontal and spectral vertical limits are symmetric; brokerage starts at zero. Partial refreshes include retained historical snapshots when calculating these bounds. A newly published snapshot can expand the limits, but moving the slider within a snapshot does not rescale them. Comparison charts use those same limits. This is a visual comparison aid, not cross-Congress alignment of the underlying eigenvectors.

The [119th Congress outlier audit](DATA_AUDIT.md) verifies prominent names against their source records and official Senate biographies. It also compares correlations computed on jointly observed votes with the superseded 1.0.0 zero-filled baseline. Trump is correctly excluded by his member metadata even though the votes export includes Senate-labelled presidential positions; his exclusion is recorded explicitly in provenance. The fixed-axis display itself does not alter numerical analysis. The subsequent 1.1.0 Rubio exclusion does change the analyzed population and recalculates the 119th Congress graph.

The implementation uses SciPy's symmetric normalized Laplacian. Its treatment of input self-loops is documented in [the SciPy reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csgraph.laplacian.html).

## Conductance and the spectral sweep

For a nonempty proper set of vertices `S`, define:

```text
cut(S, S̄) = Σ(i∈S, j∈S̄) Aᵢⱼ
vol(S)    = Σ(i∈S) dᵢ
φ(S)      = cut(S, S̄) / min(vol(S), vol(S̄))
h(G)      = min over all nonempty proper S of φ(S)
```

The maintained pipeline orders members by `u₂(i) / √dᵢ`, where `u₂` is the symmetric normalized-Laplacian eigenvector. It evaluates the nontrivial prefixes of that ordering and reports the lowest conductance encountered.

This is a **sweep conductance estimate**, `φ_sweep`. Searching these ordered cuts is tractable, but it is not an exhaustive search over all partitions. Consequently `h(G) ≤ φ_sweep`. The familiar Cheeger bounds for this graph are:

```text
λ₂ / 2 ≤ h(G) ≤ √(2λ₂)
```

The theoretical bounds concern the global minimum. Published output caps the upper bound at 1, the trivial maximum for this conductance definition. These are not confidence intervals, and the sweep result must not be labeled an exactly computed Cheeger constant. Standard normalized-Laplacian sweep arguments use the degree-adjusted coordinate above; see [Spielman's spectral graph theory text](https://cs-www.cs.yale.edu/homes/spielman/sagt/sagt.pdf).

The optimizing cut is selected from voting similarity, not defined by party labels. A conductance of 0.15 therefore describes a proportion of weighted degree crossing that cut, not “15% of bills are bipartisan” or necessarily “15% of the minority party's ties cross the aisle.”

## Thresholded graph and betweenness

The spectral calculations above use the full weighted similarity graph. Brokerage uses a second graph that retains off-diagonal similarities at or above a threshold, by default `Aᵢⱼ ≥ 0.5`. This is equivalent to `rᵢⱼ ≥ 0`, not a raw-correlation cutoff of 0.5.

The retained edge is assigned a positive shortest-path length:

```text
distanceᵢⱼ = max(1 − Aᵢⱼ, 10⁻⁶)
```

This makes stronger similarities shorter while avoiding zero-length edges for identical encoded records. Distances are attached directly to the graph passed to the centrality algorithm. [NetworkX documents](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.centrality.betweenness_centrality.html) that the selected weight attribute is interpreted as a distance and must be positive.

Betweenness counts the fraction of shortest paths between other member pairs that pass through a member. The calculation is undirected, normalized, and excludes path endpoints. The pipeline summarizes its mean, maximum, and inequality where emitted.

Threshold and distance choices materially affect centrality. Disconnected components have no paths between them; zero betweenness alone does not demonstrate that the original weighted graph is disconnected. It can also occur in a connected complete graph with direct shortest paths. A weighted clique can have nonzero betweenness if an indirect route is shorter than a direct edge. Results are structural statistics under these modeling choices, not direct measurements of bargaining power.

NetworkX additionally notes numerical limitations with floating-point weighted shortest paths. Results near distance ties should be checked for robustness before using tiny centrality differences substantively.

## Inverse-Fiedler proxy

The pipeline may report `1 / λ₂` as an **inverse-Fiedler proxy**. It preserves a quantity discussed in the thesis but avoids treating it as an observed negotiation time or a bill-passage forecast.

For a discrete-time walk `P = D⁻¹A`, the algebraic gap from its second-largest eigenvalue is λ₂. General mixing behavior also involves the absolute spectral gap, error tolerance, and stationary distribution. Making the walk lazy, `(I + P) / 2`, changes the gap to `λ₂ / 2`; its corresponding relaxation time is `2 / λ₂`. These distinctions are explained in [Levin and Peres, *Markov Chains and Mixing Times*, Chapter 12](https://pages.uoregon.edu/dlevin/MARKOV/markovmixing.pdf).

The gap `λ₃ − λ₂` is an eigengap relevant to spectral separation, not the same quantity as the random-walk gap above. Neither `1 / λ₂` nor a change in it calculates a particular pair's hitting time. The dashboard does not estimate hitting times or empirical persuasion probabilities.

## Corrections relative to the preserved scripts

| Original behavior | Maintained behavior | Consequence |
| --- | --- | --- |
| Selected member IDs were manually excluded; the two scripts use different exclusions. | Eligibility uses chamber/member metadata and a minimum usable record, with an explicit Congress-119-only exclusion for Rubio in methodology 1.1.0. | The analyzed population can differ; the scoped exception and its reason are recorded in provenance. |
| Zero/constant records could produce undefined correlations; one script fills undefined correlations with zero before rescaling. | Unsupported constant records are filtered. | Avoids manufacturing 0.5-weight ties from undefined correlations. |
| Self-similarity remained in the matrix. SciPy omitted it in normalization, while the custom conductance calculation included it in volumes. | The diagonal is zero everywhere. | Spectral and conductance calculations use consistent degree definitions. |
| The sweep sorts the raw symmetric eigenvector. | It sorts the degree-adjusted coordinate. | Uses the ordering appropriate to the normalized formulation. |
| A sweep minimum is called the empirical Cheeger constant. | It is labeled a sweep estimate. | Avoids claiming a globally optimal cut was computed. |
| `G_sparse = G.copy()` occurs before `distance` is added to `G`. | Distances are assigned on the graph actually analyzed. | Restores intended weighted shortest paths; centrality will change. |
| Intended `1 − weight` distances can be zero. | Distances have a small positive floor. | Avoids zero-length shortest-path ambiguity. |
| Plot captions mix raw correlation and transformed similarity thresholds. | The weight scale and threshold conversion are explicit. | Full and thresholded graph results can be interpreted correctly. |
| `1/λ₂` is discussed as mixing or legislative time. | It is labeled a spectral proxy. | Avoids an unsupported behavioral interpretation. |
| Data is downloaded at execution without a saved analysis manifest. | Published outputs include data/provenance metadata. | Readers can distinguish calculation time from source coverage. |

The original files are retained as historical research artifacts. The maintained pipeline is a **revised implementation**, and agreement with the thesis's rounded Table 6.1 values is not a correctness criterion.

## Interpretation and robustness checklist

For a research claim or publication, report:

- The source snapshot, retrieval time, observed date range, Congresses, pipeline version, and settings.
- The analyzed membership, minimum activity rule, and handling of non-voting and non-overlapping service.
- Whether a result describes the full similarity graph or a thresholded graph, with its threshold and distance convention.
- Sensitivity to missing-data treatment, minimum overlapping votes, edge thresholds, and short member records.
- Whether an in-progress Congress is compared with a complete term or a matched partial-term window.
- The uncertainty and statistical design behind any historical or causal claim.

Historical parties and issue agendas change. Normalized metrics and colored clusters do not establish that a contemporary party is equivalent to a historical party with a similar name or color. Likewise, drawing a line at a historical event is context, not an identified causal effect.

The current dashboard computes one documented specification. It does not yet implement the robustness studies listed above, uncertainty intervals, causal inference, signed-graph alternatives, or a model of legislative outcomes.
