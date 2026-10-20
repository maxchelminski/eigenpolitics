# -*- coding: utf-8 -*-
"""
Created on Wed Nov 19 00:15:54 2025

@author: Max
"""

import pandas as pd
import numpy as np
from scipy.sparse.csgraph import laplacian
from scipy.linalg import eigh
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
import plotly.graph_objects as go
import plotly.io as pio
pio.renderers.default = 'browser'
from sklearn.decomposition import PCA

url_1_119 = "https://voteview.com/static/data/out/votes/HS119_votes.csv"
df_1_119 = pd.read_csv(url_1_119)
senate_df_1_119 = df_1_119[df_1_119['chamber'] == 'Senate'].copy()

code_map = {1: 1, 2: 1, 3: 1, 
            4: -1, 5: -1, 6: -1,
            7: 0, 8: 0, 9: 0}

senate_df_1_119['vote_value'] = senate_df_1_119['cast_code'].map(code_map)

vote_counts_1 = senate_df_1_119['icpsr'].value_counts()
senate_df_1_119 = senate_df_1_119[(senate_df_1_119['icpsr'] != 42304) & (senate_df_1_119['icpsr'] != 41102) & (senate_df_1_119['icpsr'] != 99912)]

senate_df_1_119['vote_value'] = senate_df_1_119['vote_value'].fillna(0)

vote_matrix_1 = senate_df_1_119.pivot_table(
    index='icpsr', 
    columns='rollnumber', 
    values='vote_value'
)

vote_matrix_1 = vote_matrix_1.fillna(0)

adjacency_matrix_1 = vote_matrix_1.T.corr()

weighted_adj_1 = (adjacency_matrix_1 + 1) / 2


#for computing
matrix_1 = weighted_adj_1.to_numpy()

L2025 = laplacian(matrix_1, normed=True)

eigenvals2025, eigenvecs2025 = eigh(L2025)

fiedler_value2025 = eigenvals2025[1]

fiedler_vector_1 = eigenvecs2025[:, 1]

plot_data_1 = pd.DataFrame({
    'icpsr': vote_matrix_1.index,
    'fiedler_value': fiedler_vector_1
})

url_2_119 = "https://voteview.com/static/data/out/members/HS119_members.csv"
df_2_119 = pd.read_csv(url_2_119)
senate_df_2_119 = df_2_119[df_2_119['chamber'] == 'Senate'].copy()
party_map_1 = senate_df_2_119.groupby('icpsr')['party_code'].first()

plot_data_1['party_code'] = plot_data_1['icpsr'].map(party_map_1)
color_map = {100: 'blue', 200: 'red', 328: 'grey'}
plot_data_1['color'] = plot_data_1['party_code'].map(color_map).fillna('grey')

plot_data_1 = plot_data_1.sort_values('fiedler_value').reset_index(drop=True)

plt.scatter(plot_data_1.index, plot_data_1['fiedler_value'], c=plot_data_1['color'], alpha=0.7)

plt.title("The Spectral Geometry of the 119th Senate", fontsize=15)
plt.ylabel("Fiedler Vector Value (Ideological Position)", fontsize=12)
plt.xlabel("Senator Rank (Sorted by Ideology)", fontsize=12)
plt.grid(True, alpha=0.3)

# Draw a horizontal line at 0 (The Mathematical Center)
plt.axhline(0, color='black', linestyle='--', alpha=0.5)

plt.show()



####################1980



url_1_96 = "https://voteview.com/static/data/out/votes/HS096_votes.csv"
df_1_96 = pd.read_csv(url_1_96)
senate_df_1_96 = df_1_96[df_1_96['chamber'] == 'Senate'].copy()

senate_df_1_96['vote_value'] = senate_df_1_96['cast_code'].map(code_map)

vote_counts_2 = senate_df_1_96['icpsr'].value_counts()
senate_df_1_96 = senate_df_1_96[senate_df_1_96['icpsr'] != 14713]
vote_counts_2 = senate_df_1_96['icpsr'].value_counts()

senate_df_1_96['vote_value'] = senate_df_1_96['vote_value'].fillna(0)

vote_matrix_2 = senate_df_1_96.pivot_table(
    index='icpsr', 
    columns='rollnumber', 
    values='vote_value'
)

vote_matrix_2 = vote_matrix_2.fillna(0)

adjacency_matrix_2 = vote_matrix_2.T.corr()

weighted_adj_2 = (adjacency_matrix_2 + 1) / 2

#for computing
matrix_2 = weighted_adj_2.to_numpy()

L1980 = laplacian(matrix_2, normed=True)

eigenvals1980, eigenvecs1980 = eigh(L1980)

fiedler_value1980 = eigenvals1980[1]

fiedler_vector_2 = eigenvecs1980[:, 1]

fiedler_vector_2 = fiedler_vector_2 * -1

plot_data_2 = pd.DataFrame({
    'icpsr': vote_matrix_2.index,
    'fiedler_value': fiedler_vector_2
})

url_2_96 = "https://voteview.com/static/data/out/members/HS096_members.csv"
df_2_96 = pd.read_csv(url_2_96)
senate_df_2_96 = df_2_96[df_2_96['chamber'] == 'Senate'].copy()
party_map_2 = senate_df_2_96.groupby('icpsr')['party_code'].first()

plot_data_2['party_code'] = plot_data_2['icpsr'].map(party_map_2)
plot_data_2['color'] = plot_data_2['party_code'].map(color_map).fillna('grey')

plot_data_2 = plot_data_2.sort_values('fiedler_value').reset_index(drop=True)

plt.scatter(plot_data_2.index, plot_data_2['fiedler_value'], c=plot_data_2['color'], alpha=0.7)

plt.title("The Spectral Geometry of the 96th Senate", fontsize=15)
plt.ylabel("Fiedler Vector Value (Ideological Position)", fontsize=12)
plt.xlabel("Senator Rank (Sorted by Ideology)", fontsize=12)
plt.grid(True, alpha=0.3)

# Draw a horizontal line at 0 (The Mathematical Center)
plt.axhline(0, color='black', linestyle='--', alpha=0.5)

plt.show()



#################Loss of structure



plt.figure()

# Plot the first 10 eigenvalues (Index 1 to 10, skipping the trivial 0)
plt.plot(range(1, 5), eigenvals1980[1:5], marker='o', label='96th Senate', color='green')
plt.plot(range(1, 5), eigenvals2025[1:5], marker='o', label='119th Senate', color='red')

plt.title("The Spectral Gap: Loss of Structural Complexity", fontsize=15)
plt.ylabel("Eigenvalue (Energy Cost to Split)", fontsize=12)
plt.xlabel("Eigenvector Index (Dimension of Split)", fontsize=12)
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()




#################2D spectral map

#2025

point_colors_1 = vote_matrix_1.index.map(party_map_1).map(color_map).fillna('grey')

#Fielder Vector, Partisanship
x_axis = eigenvecs2025[:, 1]

#Secondary Structure
y_axis = eigenvecs2025[:, 2]

plt.figure()
plt.scatter(x_axis, y_axis, c=point_colors_1, alpha=0.7)

plt.title("The 2D Geometry of the 119th Senate (2025-2027)")
plt.xlabel("Primary Axis of Division (Ideology)")
plt.ylabel("Secondary Axis of Division")
plt.axhline(0, color='grey', linestyle='--')
plt.axvline(0, color='grey', linestyle='--')
plt.grid(True, alpha=0.3)
plt.show()

#1980

point_colors_2 = vote_matrix_2.index.map(party_map_2).map(color_map).fillna('grey')

#Fielder Vector, Partisanship
x_axis = eigenvecs1980[:, 1] * -1

#Secondary Structure
y_axis = eigenvecs1980[:, 2]

plt.figure()
plt.scatter(x_axis, y_axis, c=point_colors_2, alpha=0.7)

plt.title("The 2D Geometry of the 96th Senate (1979-1981)")
plt.xlabel("Primary Axis of Division (Ideology)")
plt.ylabel("Secondary Axis of Division")
plt.axhline(0, color='grey', linestyle='--')
plt.axvline(0, color='grey', linestyle='--')
plt.grid(True, alpha=0.3)
plt.show()



######## understanding the laplacian


#2025
party_info_1 = senate_df_2_119[['icpsr', 'party_code']].drop_duplicates(subset='icpsr')
merged_df_1 = senate_df_1_119.merge(party_info_1, on='icpsr', how='left')
sorted_df_1 = merged_df_1.sort_values(by=['party_code', 'icpsr'])

sorted_matrix_1 = sorted_df_1.pivot_table(
    index='icpsr', 
    columns='rollnumber', 
    values='vote_value'
).fillna(0)

adj_1 = sorted_matrix_1.T.corr()
sorted_senator_list_1 = merged_df_1[['icpsr', 'party_code']].drop_duplicates().sort_values(by=['party_code', 'icpsr'])['icpsr']
valid_ids_1 = [x for x in sorted_senator_list_1 if x in adj_1.index]

sorted_adj_1 = adj_1.reindex(index=valid_ids_1, columns=valid_ids_1)


plt.figure()
sns.heatmap(sorted_adj_1, cmap='coolwarm', vmin=-1, vmax=1)

plt.title("The Block Diagonal: 119th Senate Sorted by Party")
plt.show()

weighted_sorted_adj_1 = (sorted_adj_1 + 1) / 2
sorted_matrix_1_L = weighted_sorted_adj_1.to_numpy()
L2025_sorted = laplacian(sorted_matrix_1_L, normed=True)

plt.figure()

sns.heatmap(L2025_sorted, cmap='RdBu', vmax=0.0, vmin=-0.05) 

plt.title("The Laplacian Structure of the 119th Senate (Contrast Boosted)")
plt.show()

#1980
party_info_2 = senate_df_2_96[['icpsr', 'party_code']].drop_duplicates(subset='icpsr')
merged_df_2 = senate_df_1_96.merge(party_info_2, on='icpsr', how='left')
sorted_df_2 = merged_df_2.sort_values(by=['party_code', 'icpsr'])

sorted_matrix_2 = sorted_df_2.pivot_table(
    index='icpsr', 
    columns='rollnumber', 
    values='vote_value'
).fillna(0)

adj_2 = sorted_matrix_2.T.corr()
sorted_senator_list_2 = merged_df_2[['icpsr', 'party_code']].drop_duplicates().sort_values(by=['party_code', 'icpsr'])['icpsr']
valid_ids_2 = [x for x in sorted_senator_list_2 if x in adj_2.index]

sorted_adj_2 = adj_2.reindex(index=valid_ids_2, columns=valid_ids_2)


plt.figure()
sns.heatmap(sorted_adj_2, cmap='coolwarm', vmin=-1, vmax=1)

plt.title("The Block Diagonal: 96th Senate Sorted by Party")
plt.show()

weighted_sorted_adj_2 = (sorted_adj_2 + 1) / 2
sorted_matrix_2_L = weighted_sorted_adj_2.to_numpy()
L1980_sorted = laplacian(sorted_matrix_2_L, normed=True)

plt.figure()

sns.heatmap(L1980_sorted, cmap='RdBu', vmax=0.0, vmin=-0.05) 

plt.title("The Laplacian Structure of the 96th Senate (Contrast Boosted)")
plt.show()



#####Playing with some 3d models


#3d spectral embedding
x2025 = eigenvecs2025[:,1]
y2025 = eigenvecs2025[:,2]
z2025 = eigenvecs2025[:,3]

x1980 = eigenvecs1980[:,1] * -1
y1980 = eigenvecs1980[:,2]
z1980 = eigenvecs1980[:,3]

#2025 plot
fig = plt.figure(figsize=(10,8))
ax = fig.add_subplot(111, projection='3d')

ax.scatter(x2025, y2025, z2025, c=point_colors_1, s=50, alpha=0.6)

ax.set_xlabel('Vec 1 (Party)')
ax.set_ylabel('Vec 2 (Faction)')
ax.set_zlabel('Vec 3 (Noise?)')
ax.set_title("3D Spectral Geometry of the 119th Senate")

plt.show()

#1980 plot
fig = plt.figure(figsize=(10,8))
ax = fig.add_subplot(111, projection='3d')

ax.scatter(x1980, y1980, z1980, c=point_colors_2, s=50, alpha=0.6)

ax.set_xlabel('Vec 1 (Party)')
ax.set_ylabel('Vec 2 (Faction)')
ax.set_zlabel('Vec 3 (Noise?)')
ax.set_title("3D Spectral Geometry of the 96th Senate")

plt.show()


#Spring embedded network
#2025
G1 = nx.from_numpy_array(weighted_adj_1.to_numpy())

pos1 = nx.spring_layout(G1, dim=3, seed=42, weight='weight', iterations=100)
x1_nodes = [pos1[i][0] for i in G1.nodes()]
y1_nodes = [pos1[i][1] for i in G1.nodes()]
z1_nodes = [pos1[i][2] for i in G1.nodes()]

edge_threshold = 0.5
x1_edges = []
y1_edges = []
z1_edges = []

for u, v, d in G1.edges(data=True):
    if d['weight'] > edge_threshold:
        x1_edges += [pos1[u][0], pos1[v][0], None] # The 'None' breaks the line segment
        y1_edges += [pos1[u][1], pos1[v][1], None]
        z1_edges += [pos1[u][2], pos1[v][2], None]

'''        
fig = go.Figure()
fig.add_trace(go.Scatter3d(
    x=x1_nodes, y=y1_nodes, z=z1_nodes,
    mode='markers',
    marker=dict(
        size=6,
        color=point_colors_1, 
        opacity=0.9
    ),
    hoverinfo='text',
    text=[f"Senator {i}" for i in G1.nodes()]
))
'''
# Map ICPSR to Senator Names for the 119th Senate
name_map_1 = senate_df_2_119.groupby('icpsr')['bioname'].first().to_dict()
senator_names_1 = [name_map_1.get(vote_matrix_1.index[i], f"Unknown ({vote_matrix_1.index[i]})") for i in G1.nodes()]

fig = go.Figure()
fig.add_trace(go.Scatter3d(
    x=x1_nodes, y=y1_nodes, z=z1_nodes,
    mode='markers',
    marker=dict(
        size=6,
        color=point_colors_1, 
        opacity=0.9
    ),
    hoverinfo='text',
    text=senator_names_1
))

fig.add_trace(go.Scatter3d(
        x=x1_edges, y=y1_edges, z=z1_edges,
        mode='lines',
        opacity=0.25,
        line=dict(color='grey', width=1),
        hoverinfo='none'
    ))

fig.update_layout(
    title="3D Network Topology of the 119th Senate (Rotatable)",
    width=900, height=700,
    showlegend=False,
    scene=dict(
        xaxis=dict(showticklabels=False, title=''),
        yaxis=dict(showticklabels=False, title=''),
        zaxis=dict(showticklabels=False, title='')
    )
)

fig.show()

#1980
G2 = nx.from_numpy_array(weighted_adj_2.to_numpy())

pos2 = nx.spring_layout(G2, dim=3, seed=42, weight='weight', iterations=100)
x2_nodes = [pos2[i][0] for i in G2.nodes()]
y2_nodes = [pos2[i][1] for i in G2.nodes()]
z2_nodes = [pos2[i][2] for i in G2.nodes()]

edge_threshold = 0.5
x2_edges = []
y2_edges = []
z2_edges = []

for u, v, d in G2.edges(data=True):
    if d['weight'] > edge_threshold:
        x2_edges += [pos2[u][0], pos2[v][0], None] # The 'None' breaks the line segment
        y2_edges += [pos2[u][1], pos2[v][1], None]
        z2_edges += [pos2[u][2], pos2[v][2], None]
        
fig = go.Figure()
fig.add_trace(go.Scatter3d(
    x=x2_nodes, y=y2_nodes, z=z2_nodes,
    mode='markers',
    marker=dict(
        size=6,
        color=point_colors_2, 
        opacity=0.9
    ),
    hoverinfo='text',
    text=[f"Senator {i}" for i in G2.nodes()]
))

fig.add_trace(go.Scatter3d(
        x=x2_edges, y=y2_edges, z=z2_edges,
        mode='lines',
        opacity=0.25,
        line=dict(color='grey', width=1),
        hoverinfo='none'
    ))

fig.update_layout(
    title="3D Network Topology of the 96th Senate (Rotatable)",
    width=900, height=700,
    showlegend=False,
    scene=dict(
        xaxis=dict(showticklabels=False, title=''),
        yaxis=dict(showticklabels=False, title=''),
        zaxis=dict(showticklabels=False, title='')
    )
)

fig.show()



#3d surface plot
#2025
Z_plot1 = L2025_sorted.copy()
x = np.arange(Z_plot1.shape[0]) # Dynamically grab the number of columns
y = np.arange(Z_plot1.shape[1]) # Dynamically grab the number of rows
X, Y = np.meshgrid(x, y)
np.fill_diagonal(Z_plot1, np.nan)

fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')
ax.plot_surface(X, Y, -Z_plot1, cmap='PuOr')

ax.set_title("The Topology of Agreement of the 119th Senate (Diagonal Removed)", fontsize=15)
ax.set_zlabel("Connection Strength (Inverted)")
ax.set_xlabel("Senator A")
ax.set_ylabel("Senator B")

plt.show()

#1980
Z_plot2 = L1980_sorted.copy()
x = np.arange(Z_plot2.shape[0]) # Dynamically grab the number of columns
y = np.arange(Z_plot2.shape[1]) # Dynamically grab the number of rows
X, Y = np.meshgrid(x, y)
np.fill_diagonal(Z_plot2, np.nan)

fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')
ax.plot_surface(X, Y, -Z_plot2, cmap='PuOr')

ax.set_title("The Topology of Agreement of the 96th Senate (Diagonal Removed)", fontsize=15)
ax.set_zlabel("Connection Strength (Inverted)")
ax.set_xlabel("Senator A")
ax.set_ylabel("Senator B")

plt.show()


####### PCA


X_119 = vote_matrix_1.fillna(0)
X_96 = vote_matrix_2.fillna(0)

pca_119 = PCA(n_components=10)
pca_119.fit(X_119)

pca_96 = PCA(n_components=10)
pca_96.fit(X_96)

plt.figure(figsize=(10, 6))
# Plot 96th Senate (Green)
plt.plot(range(1, 11), pca_96.explained_variance_ratio_, 
         marker='o', color='green', label='96th Senate (1980)')

# Plot 119th Senate (Red)
plt.plot(range(1, 11), pca_119.explained_variance_ratio_, 
         marker='o', color='red', label='119th Senate (2025)')

plt.title("The Collapse of Information: PCA Scree Plot")
plt.xlabel("Principal Component (Dimension)")
plt.ylabel("Percentage of Variance Explained")
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()



######## Betweenness Centrality
####### Betweenness Centrality
# --- STEP 1: Define a Helper Function for Centrality ---
def calculate_centrality_data(adj_matrix, fiedler_vec, party_colors):
    # 1. Create Graph
    G = nx.from_numpy_array(adj_matrix.to_numpy())
    
    # 2. APPLY THRESHOLD (Optional but Recommended)
    # Remove very weak edges to clean up noise
    # We keep edges only if Weight > 0.5 (Positive Correlation)
    G_sparse = G.copy()
    remove_list = []
    for u, v, d in G.edges(data=True):
        if d['weight'] < .5: # If Correlation is negative
            remove_list.append((u, v))
        else:
            # 3. NEW DISTANCE FORMULA (Linear Penalty)
            # Stronger penalty for weak ties forces flow through the center
            d['distance'] = (1.0 - d['weight']) 

    G_sparse.remove_edges_from(remove_list)
        
    # 3. Calculate Betweenness Centrality
    centrality_dict = nx.betweenness_centrality(G_sparse, weight='distance', normalized=True)
    centrality_values = [centrality_dict[i] for i in range(len(G.nodes))]
    
    # 4. Package into DataFrame
    df = pd.DataFrame({
        'fiedler': fiedler_vec,
        'centrality': centrality_values,
        'color': party_colors
    })
    
    return df

# --- STEP 2: Calculate for Both Senates ---
print("Calculating Centrality for 119th Senate...")
df_2025 = calculate_centrality_data(weighted_adj_1, fiedler_vector_1, point_colors_1)

print("Calculating Centrality for 96th Senate...")
df_1980 = calculate_centrality_data(weighted_adj_2, fiedler_vector_2, point_colors_2)


# --- STEP 3: Plot The "Death of the Broker" ---
fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)
# Plot 1980 (The Bridge Era)
axes[0].scatter(df_1980['fiedler'], df_1980['centrality'], c=df_1980['color'], alpha=0.7, s=60)
axes[0].set_title("1980 (96th Senate): The Bell Curve of Power", fontsize=14)
axes[0].set_xlabel("Ideology (Fiedler Vector)", fontsize=12)
axes[0].set_ylabel("Betweenness Centrality (Brokerage Power)", fontsize=12)
axes[0].grid(True, alpha=0.3)
axes[0].axvline(0, color='black', linestyle='--', alpha=0.3)


# Plot 2025 (The Valley Era)
axes[1].scatter(df_2025['fiedler'], df_2025['centrality'], c=df_2025['color'], alpha=0.7, s=60)
axes[1].set_title("2025 (119th Senate): The Valley of Death", fontsize=14)
axes[1].set_xlabel("Ideology (Fiedler Vector)", fontsize=12)
axes[1].grid(True, alpha=0.3)
axes[1].axvline(0, color='black', linestyle='--', alpha=0.3)

plt.tight_layout()
plt.show()

