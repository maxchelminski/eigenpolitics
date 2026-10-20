# -*- coding: utf-8 -*-
"""
Streamlined Senate Spectral Analysis (Congresses 1 - 119)
Including Betweenness Centrality and Dynamic Date Calculations
"""

import pandas as pd
import numpy as np
from scipy.sparse.csgraph import laplacian
from scipy.linalg import eigh
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D

# ---------------------------------------------------------
# 1. SETUP AND CONFIGURATION
# ---------------------------------------------------------

code_map = {1: 1, 2: 1, 3: 1, 
            4: -1, 5: -1, 6: -1,
            7: 0, 8: 0, 9: 0}

party_info = {
    100: {'name': 'Democrat', 'color': 'blue'},
    200: {'name': 'Republican', 'color': 'red'},
    328: {'name': 'Independent', 'color': 'grey'},
    1:   {'name': 'Federalist', 'color': 'saddlebrown'},
    9:   {'name': 'Jeffersonian Rep.', 'color': 'forestgreen'},
    13:  {'name': 'Democrat-Republican', 'color': 'limegreen'},
    22:  {'name': 'Adams', 'color': 'darkorange'},
    29:  {'name': 'Whig', 'color': 'gold'},
    37:  {'name': 'Constitutional Union', 'color': 'purple'},
    46:  {'name': 'States Rights', 'color': 'teal'},
    112: {'name': 'Conservative', 'color': 'navy'},
    370: {'name': 'Readjuster', 'color': 'darkkhaki'},
    380: {'name': 'Populist', 'color': 'magenta'}
}

longitudinal_data = []

# ---------------------------------------------------------
# 2. HELPER FUNCTIONS
# ---------------------------------------------------------

def calculate_centrality_data(adj_matrix):
    G = nx.from_numpy_array(adj_matrix.to_numpy())
    
    G_sparse = G.copy()
    remove_list = []
    for u, v, d in G.edges(data=True):
        if d['weight'] < 0.5: 
            remove_list.append((u, v))
        else:
            d['distance'] = (1.0 - d['weight']) 

    G_sparse.remove_edges_from(remove_list)
        
    centrality_dict = nx.betweenness_centrality(G_sparse, weight='distance', normalized=True)
    
    centrality_values = [centrality_dict[i] for i in range(len(G.nodes))]
    return centrality_values

def calculate_gini(values):
    """Calculates the Gini Coefficient for inequality of centrality scores."""
    x = np.array(values, dtype=np.float64)
    x = x + 1e-8 # Add a tiny epsilon to prevent division by zero if all scores are 0
    x = np.sort(x)
    n = len(x)
    index = np.arange(1, n + 1)
    return ((np.sum((2 * index - n - 1) * x)) / (n * np.sum(x)))

def calculate_cheeger_cut(adj_matrix, fiedler_vec):
    """
    Performs a sweep cut along the sorted Fiedler vector to find the 
    empirical Cheeger constant (minimum conductance) of the network.
    """
    A = adj_matrix.to_numpy()
    n = A.shape[0]
    
    # Sort indices by their position on the Fiedler vector
    sorted_indices = np.argsort(fiedler_vec)
    
    # Calculate node degrees (volumes)
    degrees = np.sum(A, axis=1)
    total_volume = np.sum(degrees)
    
    min_conductance = float('inf')
    vol_S = 0
    
    # Sweep across the sorted nodes to find the optimal bipartition
    for i in range(n - 1):
        node = sorted_indices[i]
        vol_S += degrees[node]
        vol_V_minus_S = total_volume - vol_S
        
        min_vol = min(vol_S, vol_V_minus_S)
        
        if min_vol == 0:
            continue
            
        # Define the two partitions
        S = sorted_indices[:i+1]
        V_minus_S = sorted_indices[i+1:]
        
        # Calculate the cut size (sum of edges spanning the two groups)
        cut_size = np.sum(A[np.ix_(S, V_minus_S)])
        
        # Conductance is the ratio of the cut size to the volume of the smaller partition
        conductance = cut_size / min_vol
        
        if conductance < min_conductance:
            min_conductance = conductance
            
    return min_conductance

# ---------------------------------------------------------
# 3. MAIN LOOP (Senate 1 to 119)
# ---------------------------------------------------------

for cong in range(1, 120):
    cong_str = str(cong).zfill(3)
    
    # Calculate the exact years for this Congress
    start_year = 1789 + (cong - 1) * 2
    end_year = start_year + 2
    year_label = f"({start_year}-{end_year})"
    
    print(f"\n--- Processing {cong}th Senate {year_label} ---")
    
    url_votes = f"https://voteview.com/static/data/out/votes/HS{cong_str}_votes.csv"
    url_members = f"https://voteview.com/static/data/out/members/HS{cong_str}_members.csv"
    
    try:
        df_votes = pd.read_csv(url_votes)
        df_members = pd.read_csv(url_members)
    except Exception as e:
        print(f"Data for Congress {cong} could not be loaded. Skipping. Error: {e}")
        continue
        
    df_votes = df_votes[df_votes['chamber'] == 'Senate'].copy()
    
    df_votes['vote_value'] = df_votes['cast_code'].map(code_map).fillna(0)
    
    # Exclude specific non-Senate or anomalous ICPSRs only for the 119th Congress
    if cong == 119:
        exclude_icpsrs = [42304, 41102, 99912] # Includes the President/VP/Marco Rubio
        df_votes = df_votes[~df_votes['icpsr'].isin(exclude_icpsrs)]

    vote_matrix = df_votes.pivot_table(
        index='icpsr', 
        columns='rollnumber', 
        values='vote_value'
    ).fillna(0)
    
    vote_matrix = vote_matrix.loc[:, (vote_matrix != 0).any(axis=0)]
    
    adjacency_matrix = vote_matrix.T.corr().fillna(0)
    weighted_adj = (adjacency_matrix + 1) / 2
    
    L = laplacian(weighted_adj.to_numpy(), normed=True)
    eigenvals, eigenvecs = eigh(L)
    
    if len(eigenvals) < 3:
        continue
        
    fiedler_val = eigenvals[1]
    fiedler_vec = eigenvecs[:, 1]
    sec_vec = eigenvecs[:, 2]
    
# Calculate Centrality Metrics
    centrality_vals = calculate_centrality_data(weighted_adj)
    mean_cent = np.mean(centrality_vals)
    max_cent = np.max(centrality_vals)
    gini_cent = calculate_gini(centrality_vals)
    
    # Calculate Cheeger Metrics 
    h_g = calculate_cheeger_cut(weighted_adj, fiedler_vec)
    lower_bound = fiedler_val / 2.0
    upper_bound = np.sqrt(2 * fiedler_val)
    
    # Dictionary Append
    longitudinal_data.append({
        'Senate': cong,
        'Start_Year': start_year,
        'Fiedler_Value': fiedler_val,
        'Mean_Betweenness': mean_cent,
        'Max_Betweenness': max_cent,
        'Gini_Centrality': gini_cent,
        'Cheeger_Constant': h_g,
        'Cheeger_Lower': lower_bound,
        'Cheeger_Upper': upper_bound
    })
    
    party_map = df_members.groupby('icpsr')['party_code'].first()
    
    plot_data = pd.DataFrame({
        'icpsr': vote_matrix.index,
        'fiedler_value': fiedler_vec,
        'sec_value': sec_vec,
        'centrality': centrality_vals 
    })
    
    plot_data['party_code'] = plot_data['icpsr'].map(party_map)
    
    def get_party_attr(code, attr):
        return party_info.get(code, {'name': f'Other ({code})', 'color': 'lightgrey'})[attr]

    plot_data['color'] = plot_data['party_code'].apply(lambda x: get_party_attr(x, 'color'))
    plot_data['party_name'] = plot_data['party_code'].apply(lambda x: get_party_attr(x, 'name'))
    
    plot_data_sorted = plot_data.sort_values('fiedler_value').reset_index(drop=True)
    
    unique_parties = plot_data_sorted['party_code'].unique()
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', 
               label=get_party_attr(p, 'name'),
               markerfacecolor=get_party_attr(p, 'color'), markersize=8)
        for p in unique_parties
    ]
    
    # ---------------------------------------------------------
    # PLOT A: 1D Spectral Geometry
    # ---------------------------------------------------------
    plt.figure(figsize=(10, 6))
    plt.scatter(plot_data_sorted.index, plot_data_sorted['fiedler_value'], 
                c=plot_data_sorted['color'], alpha=0.7, s=50)
    plt.title(f"The Spectral Geometry of the {cong}th Senate {year_label}", fontsize=15)
    plt.ylabel("Fiedler Vector Value (Primary Ideology)", fontsize=12)
    plt.xlabel("Senator Rank", fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.axhline(0, color='black', linestyle='--', alpha=0.5)
    plt.legend(handles=legend_elements, loc='best')
    plt.savefig(f"./senate/1D/Spectral_1D_{cong_str}.png")
    #plt.show()

    # ---------------------------------------------------------
    # PLOT B: 2D Spectral Geometry
    # ---------------------------------------------------------
    plt.figure(figsize=(10, 6))
    plt.scatter(plot_data['fiedler_value'], plot_data['sec_value'], 
                c=plot_data['color'], alpha=0.7, s=50)
    plt.title(f"The 2D Geometry of the {cong}th Senate {year_label}", fontsize=15)
    plt.xlabel("Primary Axis of Division (Ideology)", fontsize=12)
    plt.ylabel("Secondary Axis of Division", fontsize=12)
    plt.axhline(0, color='grey', linestyle='--', alpha=0.5)
    plt.axvline(0, color='grey', linestyle='--', alpha=0.5)
    plt.grid(True, alpha=0.3)
    plt.legend(handles=legend_elements, loc='best')
    plt.savefig(f"./senate/2D/Spectral_2D_{cong_str}.png")
    #plt.show()

    # ---------------------------------------------------------
    # PLOT C: Betweenness Centrality
    # ---------------------------------------------------------
    plt.figure(figsize=(10, 6))
    plt.scatter(plot_data['fiedler_value'], plot_data['centrality'], 
                c=plot_data['color'], alpha=0.7, s=60)
    plt.title(f"Brokerage Power vs Ideology: {cong}th Senate {year_label}", fontsize=15)
    plt.xlabel("Primary Ideology (Fiedler Vector)", fontsize=12)
    plt.ylabel("Betweenness Centrality (Brokerage Power)", fontsize=12)
    plt.axvline(0, color='black', linestyle='--', alpha=0.3)
    plt.grid(True, alpha=0.3)
    plt.legend(handles=legend_elements, loc='best')
    plt.savefig(f"./senate/Centrality/Centrality_{cong_str}.png")
    #plt.show()

    # ---------------------------------------------------------
    # PLOT D: 3D Plotly Network (Commented for Manual Use)
    # ---------------------------------------------------------
    """
    import plotly.graph_objects as go
    
    G_3d = nx.from_numpy_array(weighted_adj.to_numpy())
    pos_3d = nx.spring_layout(G_3d, dim=3, seed=42, weight='weight', iterations=100)
    
    x_nodes = [pos_3d[i][0] for i in G_3d.nodes()]
    y_nodes = [pos_3d[i][1] for i in G_3d.nodes()]
    z_nodes = [pos_3d[i][2] for i in G_3d.nodes()]
    
    edge_threshold = 0.5 
    x_edges, y_edges, z_edges = [], [], []
    
    for u, v, d in G_3d.edges(data=True):
        if d['weight'] > edge_threshold:
            x_edges += [pos_3d[u][0], pos_3d[v][0], None]
            y_edges += [pos_3d[u][1], pos_3d[v][1], None]
            z_edges += [pos_3d[u][2], pos_3d[v][2], None]
            
    fig = go.Figure()
    
    fig.add_trace(go.Scatter3d(x=x_edges, y=y_edges, z=z_edges,
                               mode='lines', opacity=0.25,
                               line=dict(color='grey', width=1), hoverinfo='none'))
    
    fig.add_trace(go.Scatter3d(x=x_nodes, y=y_nodes, z=z_nodes,
                               mode='markers',
                               marker=dict(size=6, color=plot_data['color'].tolist(), opacity=0.9),
                               hoverinfo='text',
                               text=plot_data['party_name'].tolist()))
                               
    fig.update_layout(title=f"3D Network Topology of the {cong}th Senate {year_label}",
                      showlegend=False, width=900, height=700)
    fig.show()
    """

# ---------------------------------------------------------
# 4. LONGITUDINAL ANALYSIS
# ---------------------------------------------------------

df_longitudinal = pd.DataFrame(longitudinal_data)

print("\n--- Longitudinal DataFrame ---")
print(df_longitudinal.head())

plt.figure(figsize=(14, 7))
plt.plot(df_longitudinal['Start_Year'], df_longitudinal['Fiedler_Value'], 
         marker='o', color='purple', linestyle='-', linewidth=2, markersize=4)
plt.title("The Decay of Connectivity: Fiedler Value over Time (1789-2026)", fontsize=16)
plt.xlabel("Year", fontsize=14)
plt.ylabel("Fiedler Value (λ₂)", fontsize=14)
plt.grid(True, alpha=0.4)
plt.axvline(x=1861, color='red', linestyle='--', alpha=0.5, label='Civil War (1861)')
plt.axvline(x=1994, color='blue', linestyle='--', alpha=0.5, label='Gingrich Revolution (1994)')
plt.legend()
plt.show()

plt.figure(figsize=(14, 7))
plt.plot(df_longitudinal['Start_Year'], df_longitudinal['Mean_Betweenness'], 
         marker='s', color='darkgreen', linestyle='-', linewidth=2, markersize=4)
plt.title("The Extinction of the Broker: Mean Betweenness Centrality (1789-2026)", fontsize=16)
plt.xlabel("Year", fontsize=14)
plt.ylabel("Mean Betweenness Centrality", fontsize=14)
plt.grid(True, alpha=0.4)
plt.axvline(x=1861, color='red', linestyle='--', alpha=0.5, label='Civil War (1861)')
plt.axvline(x=1994, color='blue', linestyle='--', alpha=0.5, label='Gingirch Revolution (1994)')
plt.legend()
plt.show()

# ---------------------------------------------------------
#Maximum Betweenness Centrality (The Monopoly Plot)
# ---------------------------------------------------------
plt.figure(figsize=(14, 7))
plt.plot(df_longitudinal['Start_Year'], df_longitudinal['Max_Betweenness'], 
         marker='D', color='darkred', linestyle='-', linewidth=2, markersize=4)

plt.title("The Rise of the Monopoly Broker: Max Betweenness Centrality (1789-2026)", fontsize=16)
#plt.xlabel("Year", fontsize=14)
plt.ylabel("Maximum Centrality Score (Highest individual score)", fontsize=14)
plt.grid(True, alpha=0.4)
plt.axvline(x=1861, color='red', linestyle='--', alpha=0.5, label='Civil War (1861)')
plt.axvline(x=1994, color='blue', linestyle='--', alpha=0.5, label='Gingrich Revolution (1994)')
plt.legend()
plt.show()

# ---------------------------------------------------------
#The Gini Coefficient of Centrality (Power Inequality)
# ---------------------------------------------------------
plt.figure(figsize=(14, 7))
plt.plot(df_longitudinal['Start_Year'], df_longitudinal['Gini_Centrality'], 
         marker='^', color='indigo', linestyle='-', linewidth=2, markersize=4)

plt.title("Structural Inequality: Gini Coefficient of Brokerage Power (1789-2026)", fontsize=16)
plt.xlabel("Year", fontsize=14)
plt.ylabel("Gini Coefficient (0 = Equal Power, 1 = Absolute Monopoly)", fontsize=14)
plt.grid(True, alpha=0.4)
plt.axvline(x=1861, color='red', linestyle='--', alpha=0.5, label='Civil War (1861)')
plt.axvline(x=1994, color='blue', linestyle='--', alpha=0.5, label='Gingrich Revolution (1994)')
plt.legend()
plt.show()

# ---------------------------------------------------------
# The Cheeger Inequality: Network Cuttability
# ---------------------------------------------------------
plt.figure(figsize=(14, 7))

# Plot the theoretical bounds
plt.plot(df_longitudinal['Start_Year'], df_longitudinal['Cheeger_Upper'], 
         color='grey', linestyle=':', alpha=0.7, label='Upper Bound (sqrt(2 * Fiedler))')
plt.plot(df_longitudinal['Start_Year'], df_longitudinal['Cheeger_Lower'], 
         color='grey', linestyle='--', alpha=0.7, label='Lower Bound (Fiedler / 2)')

# Plot the actual empirical Cheeger Constant
plt.plot(df_longitudinal['Start_Year'], df_longitudinal['Cheeger_Constant'], 
         marker='o', color='teal', linestyle='-', linewidth=2.5, markersize=5, 
         label='Empirical Cheeger Constant (h_G)')

plt.title("Senate Cuttability: Cheeger's Inequality and Partisan Bottlenecks (1789-2026)", fontsize=16)
plt.xlabel("Year", fontsize=14)
plt.ylabel("Conductance (Lower = Easier to Cut)", fontsize=14)
plt.grid(True, alpha=0.4)

plt.axvline(x=1861, color='red', linestyle='--', alpha=0.5, label='Civil War (1861)')
plt.axvline(x=1994, color='blue', linestyle='--', alpha=0.5, label='Gingrich Revolution (1994)')

plt.legend(loc='upper right')
plt.show()


# ---------------------------------------------------------
# RESULT CALCULATION
# ---------------------------------------------------------
# Extract Fiedler Values
fiedler_1980 = df_longitudinal[df_longitudinal['Senate'] == 96]['Fiedler_Value'].item()
fiedler_2026 = df_longitudinal[df_longitudinal['Senate'] == 119]['Fiedler_Value'].item()

# Extract Cheeger Constants
cheeger_1980 = df_longitudinal[df_longitudinal['Senate'] == 96]['Cheeger_Constant'].item()
cheeger_2026 = df_longitudinal[df_longitudinal['Senate'] == 119]['Cheeger_Constant'].item()

# 1. Cheeger Percentage Calculation
# The Cheeger constant (hG) represents the ratio of crossing edges to the volume of the smaller partition.
# To express this as a percentage of the smaller party's ties:
cheeger_percent_1980 = cheeger_1980 * 100
cheeger_percent_2026 = cheeger_2026 * 100

# 2. Mixing Time Calculation (Using Relaxation Time proxy)
# As discussed, the core multiplier bounding mixing time is Relaxation Time (1 / Fiedler)
relax_1980 = 1 / fiedler_1980
relax_2026 = 1 / fiedler_2026

print("--- 96TH SENATE (1980) ---")
print(f"Fiedler Value: {fiedler_1980:.3f}")
print(f"Cheeger Constant: {cheeger_1980:.3f}")
print(f"[XX]% Blank: {cheeger_percent_1980:.1f}%")
print(f"[X] steps Blank (Relaxation Time): {relax_1980:.1f} steps")

print("\n--- 119TH SENATE (2026) ---")
print(f"Fiedler Value: {fiedler_2026:.3f}")
print(f"Cheeger Constant: {cheeger_2026:.3f}")
print(f"[XX]% Blank: {cheeger_percent_2026:.1f}%")
print(f"[X] steps Blank (Relaxation Time): {relax_2026:.1f} steps")

# Growth factor for the text:
explosion_factor = relax_2026 / relax_1980
print(f"\nMixing time multiplier exploded by a factor of {explosion_factor:.2f}x")