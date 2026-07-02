"""Pathway enrichment analysis tool using Enrichr API."""
from __future__ import annotations
import requests
import json
from pathlib import Path
from typing import Dict, Any, List
import time

from src.tools.registry import tool


@tool("PATHWAY_ENRICHMENT")
def pathway_enrichment(
    gene_list: List[str],
    database: str = "KEGG_2021_Human",
    output_dir: str = "work/enrichment_results",
    top_n: int = 20
) -> Dict[str, Any]:
    """
    Perform pathway enrichment analysis using Enrichr API.
    
    Args:
        gene_list: List of gene symbols or IDs
        database: Enrichr database to use (default: KEGG_2021_Human)
                 Options: KEGG_2021_Human, GO_Biological_Process_2023, 
                         GO_Molecular_Function_2023, WikiPathways_2023_Human
        output_dir: Directory to save results
        top_n: Number of top pathways to return
    
    Returns:
        Dictionary containing:
        - enrichment_file: Path to enrichment results CSV
        - n_genes: Number of genes analyzed
        - n_pathways: Number of enriched pathways found
        - top_pathways: List of top enriched pathways
    
    Example:
        {TOOL:PATHWAY_ENRICHMENT, gene_list=['STAT1', 'ISG15', 'IRF7'], database='KEGG_2021_Human'}
    """
    try:
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Enrichr API endpoints
        ENRICHR_URL = 'https://maayanlab.cloud/Enrichr'
        ADDLIST_URL = f'{ENRICHR_URL}/addList'
        ENRICH_URL = f'{ENRICHR_URL}/enrich'
        
        # Convert gene list to string
        genes_str = '\n'.join([str(g) for g in gene_list])
        
        # Submit gene list
        payload = {
            'list': genes_str,
            'description': 'Myelin Gene List'
        }
        
        response = requests.post(ADDLIST_URL, files=payload)
        if not response.ok:
            return {
                "success": False,
                "error": f"Failed to submit gene list to Enrichr: {response.text}"
            }
        
        # Get user list ID
        data = response.json()
        user_list_id = data['userListId']
        
        # Wait briefly for processing
        time.sleep(1)
        
        # Get enrichment results
        query_string = f'?userListId={user_list_id}&backgroundType={database}'
        response = requests.get(ENRICH_URL + query_string)
        
        if not response.ok:
            return {
                "success": False,
                "error": f"Failed to get enrichment results: {response.text}"
            }
        
        # Parse results
        enrichment_data = response.json()
        
        if database not in enrichment_data:
            return {
                "success": False,
                "error": f"Database '{database}' not found in results. Available: {list(enrichment_data.keys())}"
            }
        
        results = enrichment_data[database]
        
        # Format results
        # Enrichr returns: [Rank, Term, P-value, Z-score, Combined Score, Overlapping Genes, Adjusted P-value, Old P-value, Old Adjusted P-value]
        formatted_results = []
        for item in results[:top_n]:
            formatted_results.append({
                'rank': item[0],
                'term': item[1],
                'p_value': item[2],
                'z_score': item[3],
                'combined_score': item[4],
                'overlapping_genes': item[5],
                'adj_p_value': item[6],
                'n_overlap': len(item[5].split(';')) if item[5] else 0
            })
        
        # Save results
        import pandas as pd
        results_df = pd.DataFrame(formatted_results)
        enrichment_file = output_path / f"enrichment_{database}.csv"
        results_df.to_csv(enrichment_file, index=False)
        
        # Create summary
        result = {
            "success": True,
            "enrichment_file": str(enrichment_file),
            "database": database,
            "n_genes": len(gene_list),
            "n_pathways": len(results),
            "top_pathways": formatted_results[:10]  # Top 10 for summary
        }
        
        # Save summary JSON
        summary_file = output_path / f"enrichment_{database}_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"✓ Enrichment: {len(results)} pathways found for {len(gene_list)} genes")
        return result
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
