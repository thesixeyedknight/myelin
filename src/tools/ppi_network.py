"""Protein-protein interaction network analysis using STRING database."""
from __future__ import annotations
import requests
import json
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd

try:
    import networkx as nx
except ImportError:
    raise ImportError("Missing networkx. Install with: pip install networkx")

from src.tools.registry import tool


@tool("PPI_NETWORK")
def ppi_network(
    gene_list: List[str],
    species: str = "9606",
    confidence: float = 0.4,
    output_dir: str = "work/ppi_results",
    top_hubs: int = 20
) -> Dict[str, Any]:
    """
    Construct protein-protein interaction network and identify hub genes.
    
    Args:
        gene_list: List of gene symbols
        species: NCBI taxonomy ID (default: 9606 for human)
        confidence: Minimum required interaction score (0-1, default: 0.4)
        output_dir: Directory to save results
        top_hubs: Number of top hub genes to return
    
    Returns:
        Dictionary containing:
        - network_file: Path to network edge list CSV
        - hub_genes_file: Path to hub genes CSV
        - n_genes: Number of genes in network
        - n_interactions: Number of interactions
        - top_hubs: List of top hub genes by degree centrality
    
    Example:
        {TOOL:PPI_NETWORK, gene_list=['STAT1', 'ISG15', 'IRF7'], species='9606', confidence=0.4}
    """
    try:
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # STRING API endpoint
        STRING_API = "https://string-db.org/api"
        
        # Convert gene list to STRING format
        genes_str = '%0d'.join(gene_list[:400])  # STRING has limit of ~400 proteins
        
        # Get network
        params = {
            'identifiers': genes_str,
            'species': species,
            'required_score': int(confidence * 1000),  # STRING uses 0-1000 scale
            'network_type': 'physical',
            'caller_identity': 'myelin_research_agent'
        }
        
        response = requests.post(f"{STRING_API}/tsv/network", data=params)
        
        if not response.ok:
            return {
                "success": False,
                "error": f"STRING API request failed: {response.text}"
            }
        
        # Parse network data
        lines = response.text.strip().split('\n')
        if len(lines) < 2:
            return {
                "success": False,
                "error": "No interactions found"
            }
        
        header = lines[0].split('\t')
        interactions = []
        
        for line in lines[1:]:
            parts = line.split('\t')
            if len(parts) >= 3:
                interactions.append({
                    'protein1': parts[2] if len(parts) > 2 else parts[0],  # preferredName_A
                    'protein2': parts[3] if len(parts) > 3 else parts[1],  # preferredName_B
                    'score': float(parts[5]) if len(parts) > 5 else 0.0    # score
                })
        
        if not interactions:
            return {
                "success": False,
                "error": "No interactions parsed from STRING response"
            }
        
        # Save network
        interactions_df = pd.DataFrame(interactions)
        network_file = output_path / "ppi_network.csv"
        interactions_df.to_csv(network_file, index=False)
        
        # Build NetworkX graph for analysis
        G = nx.Graph()
        for interaction in interactions:
            G.add_edge(
                interaction['protein1'],
                interaction['protein2'],
                weight=interaction['score']
            )
        
        # Calculate network metrics
        degree_centrality = nx.degree_centrality(G)
        betweenness_centrality = nx.betweenness_centrality(G)
        
        # Create hub genes dataframe
        hub_data = []
        for gene in G.nodes():
            hub_data.append({
                'gene': gene,
                'degree': G.degree(gene),
                'degree_centrality': degree_centrality[gene],
                'betweenness_centrality': betweenness_centrality[gene]
            })
        
        hubs_df = pd.DataFrame(hub_data)
        hubs_df = hubs_df.sort_values('degree', ascending=False)
        
        # Save hub genes
        hub_genes_file = output_path / "hub_genes.csv"
        hubs_df.to_csv(hub_genes_file, index=False)
        
        # Get top hubs
        top_hubs_list = hubs_df.head(top_hubs).to_dict('records')
        
        # Create summary
        result = {
            "success": True,
            "network_file": str(network_file),
            "hub_genes_file": str(hub_genes_file),
            "n_genes": len(G.nodes()),
            "n_interactions": len(G.edges()),
            "avg_degree": sum(dict(G.degree()).values()) / len(G.nodes()) if len(G.nodes()) > 0 else 0,
            "top_hubs": top_hubs_list[:10]  # Top 10 for summary
        }
        
        # Save summary JSON
        summary_file = output_path / "ppi_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"✓ PPI Network: {result['n_genes']} genes, {result['n_interactions']} interactions")
        return result
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
