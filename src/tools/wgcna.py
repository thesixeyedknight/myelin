"""Weighted Gene Co-expression Network Analysis (WGCNA) tool."""
from __future__ import annotations
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any
import json

try:
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform
    from sklearn.preprocessing import StandardScaler
except ImportError as e:
    raise ImportError(f"Missing required package: {e}. Install with: pip install scipy scikit-learn")

from src.tools.registry import tool


@tool("WGCNA_ANALYSIS")
def wgcna_analysis(
    expression_file: str,
    trait_file: str = None,
    output_dir: str = "work/wgcna_results",
    min_module_size: int = 30,
    correlation_threshold: float = 0.7
) -> Dict[str, Any]:
    """
    Perform simplified Weighted Gene Co-expression Network Analysis.
    
    This is a Python approximation of WGCNA. For full WGCNA, use R package.
    
    Args:
        expression_file: Path to expression matrix CSV (genes x samples)
        trait_file: Path to sample trait/metadata CSV (optional)
        output_dir: Directory to save results
        min_module_size: Minimum number of genes per module
        correlation_threshold: Correlation threshold for module detection
    
    Returns:
        Dictionary containing:
        - modules_file: Path to gene module assignments CSV
        - n_modules: Number of modules identified
        - module_sizes: Dictionary of module sizes
        - module_genes: Top genes from each module
    
    Example:
        {TOOL:WGCNA_ANALYSIS, expression_file='work/geo_data/GSE65391_expression.csv'}
    """
    try:
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Load expression data
        expr_df = pd.read_csv(expression_file, index_col=0)
        
        # Transpose (WGCNA works with samples as rows)
        # But for correlation, we want genes x genes
        # So we calculate gene-gene correlations across samples
        
        # Remove genes with low variance or missing data
        expr_df = expr_df.dropna(axis=0, how='any')
        expr_df = expr_df.loc[expr_df.var(axis=1) > 0.01]  # Remove low-variance genes
        
        print(f"Analyzing {len(expr_df)} genes across {len(expr_df.columns)} samples")
        
        # Calculate gene-gene correlation matrix
        # Due to computational constraints, we may need to subsample
        max_genes = 5000  # Limit for memory
        if len(expr_df) > max_genes:
            print(f"Subsampling to {max_genes} most variable genes")
            gene_vars = expr_df.var(axis=1).sort_values(ascending=False)
            selected_genes = gene_vars.head(max_genes).index
            expr_df = expr_df.loc[selected_genes]
        
        # Standardize expression
        scaler = StandardScaler()
        expr_scaled = scaler.fit_transform(expr_df.T).T  # Standardize across samples
        expr_scaled_df = pd.DataFrame(expr_scaled, index=expr_df.index, columns=expr_df.columns)
        
        # Calculate correlation matrix
        corr_matrix = expr_scaled_df.T.corr()
        
        # Convert correlation to distance for clustering
        # Distance = 1 - |correlation|
        dist_matrix = 1 - np.abs(corr_matrix.values)
        
        # Hierarchical clustering
        # dist_matrix is already a gene x gene distance matrix; convert it to
        # condensed form directly rather than re-deriving distances between
        # its rows (which would cluster on distance *profiles*, not on the
        # correlation distances themselves).
        condensed_dist = squareform(dist_matrix, checks=False)
        linkage_matrix = linkage(condensed_dist, method='average')
        
        # Cut tree to form modules
        # Use distance threshold based on correlation threshold
        distance_threshold = 1 - correlation_threshold
        module_labels = fcluster(linkage_matrix, distance_threshold, criterion='distance')
        
        # Create module assignments
        module_df = pd.DataFrame({
            'gene_id': expr_df.index,
            'module': module_labels
        })
        
        # Filter small modules
        module_counts = module_df['module'].value_counts()
        valid_modules = module_counts[module_counts >= min_module_size].index
        module_df = module_df[module_df['module'].isin(valid_modules)]
        
        # Renumber modules sequentially
        module_mapping = {old_id: new_id for new_id, old_id in enumerate(sorted(valid_modules), 1)}
        module_df['module'] = module_df['module'].map(module_mapping)
        
        # Save module assignments
        modules_file = output_path / "gene_modules.csv"
        module_df.to_csv(modules_file, index=False)
        
        # Calculate module statistics
        module_sizes = module_df['module'].value_counts().to_dict()
        
        # Get representative genes from each module (highest connectivity)
        module_genes = {}
        for module_id in sorted(module_df['module'].unique()):
            module_gene_ids = module_df[module_df['module'] == module_id]['gene_id'].values
            
            # Calculate average correlation for each gene in module
            gene_connectivity = {}
            for gene in module_gene_ids:
                # Average absolute correlation with other genes in module
                other_genes = [g for g in module_gene_ids if g != gene]
                if other_genes:
                    avg_corr = np.mean([abs(corr_matrix.loc[gene, g]) for g in other_genes])
                    gene_connectivity[gene] = avg_corr
            
            # Top 5 most connected genes
            top_genes = sorted(gene_connectivity.items(), key=lambda x: x[1], reverse=True)[:5]
            module_genes[f"Module_{module_id}"] = [g[0] for g in top_genes]
        
        # Create summary
        result = {
            "success": True,
            "modules_file": str(modules_file),
            "n_modules": len(module_sizes),
            "n_genes_in_modules": len(module_df),
            "module_sizes": {f"Module_{k}": v for k, v in module_sizes.items()},
            "module_representative_genes": module_genes
        }
        
        # Save summary JSON
        summary_file = output_path / "wgcna_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"✓ WGCNA: {result['n_modules']} modules identified")
        return result
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
