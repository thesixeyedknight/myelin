"""Differential expression analysis tool."""
from __future__ import annotations
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
import json

try:
    from scipy import stats
    from statsmodels.stats.multitest import multipletests
except ImportError as e:
    raise ImportError(f"Missing required package: {e}. Install with: pip install scipy statsmodels")

from src.tools.registry import tool


@tool("DIFF_EXPRESSION")
def differential_expression(
    expression_file: str,
    metadata_file: str,
    group_column: str,
    case_label: str,
    control_label: str,
    output_dir: str = "work/deg_results",
    fc_threshold: float = 1.0,
    pvalue_threshold: float = 0.05
) -> Dict[str, Any]:
    """
    Perform differential expression analysis between two groups.
    
    Args:
        expression_file: Path to expression matrix CSV (genes x samples)
        metadata_file: Path to sample metadata CSV
        group_column: Column name in metadata for grouping (e.g., 'disease_state')
        case_label: Label for case group (e.g., 'SLE', 'disease')
        control_label: Label for control group (e.g., 'healthy', 'normal')
        output_dir: Directory to save results
        fc_threshold: Log2 fold change threshold for DEG filtering (default: 1.0)
        pvalue_threshold: Adjusted p-value threshold (default: 0.05)
    
    Returns:
        Dictionary containing:
        - deg_file: Path to DEG results CSV
        - n_total_genes: Total genes tested
        - n_deg_up: Number of upregulated DEGs
        - n_deg_down: Number of downregulated DEGs
        - top_genes: List of top 20 DEGs by significance
    
    Example:
        {TOOL:DIFF_EXPRESSION, expression_file='work/geo_data/GSE65391_expression.csv', 
         metadata_file='work/geo_data/GSE65391_metadata.csv', group_column='disease_state',
         case_label='SLE', control_label='healthy'}
    """
    try:
        # Load data
        expr_df = pd.read_csv(expression_file, index_col=0)
        metadata_df = pd.read_csv(metadata_file)
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Filter metadata for the two groups
        if group_column not in metadata_df.columns:
            # Try fuzzy matching
            matching_cols = [col for col in metadata_df.columns if group_column.lower() in col.lower()]
            if matching_cols:
                group_column = matching_cols[0]
            else:
                return {
                    "success": False,
                    "error": f"Column '{group_column}' not found in metadata. Available: {list(metadata_df.columns)}"
                }
        
        # Get sample IDs for each group
        # Handle fuzzy matching for group labels
        case_samples = metadata_df[
            metadata_df[group_column].str.contains(case_label, case=False, na=False)
        ]['sample_id'].values
        
        control_samples = metadata_df[
            metadata_df[group_column].str.contains(control_label, case=False, na=False)
        ]['sample_id'].values
        
        if len(case_samples) == 0:
            return {"success": False, "error": f"No samples found for case group '{case_label}'"}
        if len(control_samples) == 0:
            return {"success": False, "error": f"No samples found for control group '{control_label}'"}
        
        # Filter expression matrix for these samples
        case_expr = expr_df[case_samples]
        control_expr = expr_df[control_samples]

        # Microarray/log2-intensity platforms (e.g. Illumina) ship expression
        # values already on a log2 scale (typically ~0-20); raw RNA-seq counts
        # span a much wider linear range. log2FC must be computed differently
        # in each case, otherwise pre-logged data gets log2'd a second time
        # and real fold changes are crushed to near zero.
        is_log_scale = expr_df.max().max() < 30

        # Perform differential expression analysis
        results = []

        for gene_id in expr_df.index:
            case_values = case_expr.loc[gene_id].values
            control_values = control_expr.loc[gene_id].values

            # Remove NaN values
            case_values = case_values[~np.isnan(case_values)]
            control_values = control_values[~np.isnan(control_values)]

            if len(case_values) < 2 or len(control_values) < 2:
                continue

            # Calculate statistics
            case_mean = np.mean(case_values)
            control_mean = np.mean(control_values)

            # Log2 fold change
            if is_log_scale:
                # Values are already log2-scale: difference of means IS the log2FC.
                log2fc = case_mean - control_mean
            else:
                # Raw/linear-scale values: add a small constant to avoid log(0).
                log2fc = np.log2(case_mean + 1) - np.log2(control_mean + 1)
            
            # T-test
            t_stat, p_value = stats.ttest_ind(case_values, control_values)
            
            results.append({
                'gene_id': gene_id,
                'log2_fold_change': log2fc,
                'p_value': p_value,
                'case_mean': case_mean,
                'control_mean': control_mean,
                't_statistic': t_stat
            })
        
        # Convert to DataFrame
        results_df = pd.DataFrame(results)

        # FDR correction (Benjamini-Hochberg)
        # Genes with undefined p-values (e.g. zero-variance samples) can't be
        # corrected and must be excluded, otherwise a single NaN poisons the
        # entire multipletests output.
        results_df['adj_p_value'] = np.nan
        valid_pvalue_mask = results_df['p_value'].notna()
        _, adj_pvalues, _, _ = multipletests(
            results_df.loc[valid_pvalue_mask, 'p_value'],
            method='fdr_bh'
        )
        results_df.loc[valid_pvalue_mask, 'adj_p_value'] = adj_pvalues
        
        # Filter DEGs
        deg_df = results_df[
            (np.abs(results_df['log2_fold_change']) > fc_threshold) &
            (results_df['adj_p_value'] < pvalue_threshold)
        ].copy()
        
        # Sort by adjusted p-value
        deg_df = deg_df.sort_values('adj_p_value')
        
        # Count up/down regulated
        n_up = len(deg_df[deg_df['log2_fold_change'] > 0])
        n_down = len(deg_df[deg_df['log2_fold_change'] < 0])
        
        # Save results
        deg_file = output_path / "deg_results.csv"
        deg_df.to_csv(deg_file, index=False)
        
        # Save all results (not just DEGs)
        all_results_file = output_path / "all_genes_stats.csv"
        results_df.to_csv(all_results_file, index=False)
        
        # Get top genes
        top_genes = deg_df.head(20)[['gene_id', 'log2_fold_change', 'adj_p_value']].to_dict('records')
        
        # Create summary
        result = {
            "success": True,
            "deg_file": str(deg_file),
            "all_results_file": str(all_results_file),
            "n_total_genes": len(results_df),
            "n_deg_total": len(deg_df),
            "n_deg_up": n_up,
            "n_deg_down": n_down,
            "n_case_samples": len(case_samples),
            "n_control_samples": len(control_samples),
            "fc_threshold": fc_threshold,
            "pvalue_threshold": pvalue_threshold,
            "top_genes": top_genes
        }
        
        # Save summary JSON
        summary_file = output_path / "deg_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"✓ DEG Analysis: {n_up} up, {n_down} down (total: {len(deg_df)} DEGs)")
        return result
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
