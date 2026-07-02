"""GEO dataset download and parsing tool."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any
import json

try:
    import GEOparse
    import pandas as pd
except ImportError as e:
    raise ImportError(f"Missing required package: {e}. Install with: pip install GEOparse pandas")

from src.tools.registry import tool


@tool("GEO_DOWNLOAD")
def geo_download(geo_id: str, output_dir: str = "work/geo_data") -> Dict[str, Any]:
    """
    Download and parse GEO dataset.
    
    Args:
        geo_id: GEO accession ID (e.g., 'GSE65391')
        output_dir: Directory to save downloaded data
    
    Returns:
        Dictionary containing:
        - expression_file: Path to expression matrix CSV
        - metadata_file: Path to sample metadata CSV
        - n_samples: Number of samples
        - n_genes: Number of genes/probes
        - platform: Platform ID
        - summary: Dataset description
    
    Example:
        {TOOL:GEO_DOWNLOAD, geo_id='GSE65391', output_dir='work/geo_data'}
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Download GEO dataset
        print(f"Downloading {geo_id} from GEO...")
        gse = GEOparse.get_GEO(geo=geo_id, destdir=str(output_path), silent=False)
        
        # Extract expression data
        # GEO datasets can have multiple platforms (GPL)
        # We'll use the first one for now
        gpl_name = list(gse.gpls.keys())[0]
        gpl = gse.gpls[gpl_name]
        
        # Get expression matrix
        # GEOparse stores data as pandas DataFrames
        expression_data = []
        sample_metadata = []
        
        for gsm_name, gsm in gse.gsms.items():
            # Sample metadata
            sample_info = {
                'sample_id': gsm_name,
                'title': gsm.metadata.get('title', [''])[0],
                'source': gsm.metadata.get('source_name_ch1', [''])[0],
                'characteristics': '; '.join(gsm.metadata.get('characteristics_ch1', [])),
            }
            
            # Extract disease/control status from characteristics
            characteristics = gsm.metadata.get('characteristics_ch1', [])
            disease_state_found = False
            tissue_found = False
            for char in characteristics:
                char_lower = char.lower()
                if not disease_state_found:
                    if char_lower.startswith('disease state'):
                        sample_info['disease_state'] = char.split(':')[-1].strip()
                        disease_state_found = True
                    elif 'disease' in char_lower:
                        # Fallback for series that don't use the 'disease state' label,
                        # but don't lock it in so a later exact 'disease state' match can override it.
                        sample_info['disease_state'] = char.split(':')[-1].strip()
                if not tissue_found:
                    if char_lower.startswith('tissue') or char_lower.startswith('cell type'):
                        sample_info['tissue'] = char.split(':')[-1].strip()
                        tissue_found = True
                    elif 'tissue' in char_lower or 'cell type' in char_lower:
                        sample_info['tissue'] = char.split(':')[-1].strip()
                if disease_state_found and tissue_found:
                    break
            
            sample_metadata.append(sample_info)
            
            # Expression values
            if hasattr(gsm, 'table'):
                expr_values = gsm.table
                expression_data.append(expr_values)
        
        # Convert to DataFrames
        metadata_df = pd.DataFrame(sample_metadata)
        
        # For expression matrix, we need to merge all samples
        # This can be complex depending on GEO structure
        # Simple approach: use the pivot table
        if expression_data:
            # Get probe IDs from first sample
            probe_ids = expression_data[0]['ID_REF'].values if 'ID_REF' in expression_data[0].columns else None
            
            # Build expression matrix
            expr_dict = {}
            for i, gsm_name in enumerate(gse.gsms.keys()):
                if i < len(expression_data):
                    value_col = 'VALUE' if 'VALUE' in expression_data[i].columns else expression_data[i].columns[-1]
                    expr_dict[gsm_name] = expression_data[i][value_col].values
            
            expr_df = pd.DataFrame(expr_dict, index=probe_ids)
        else:
            # Fallback: try to get from GSE metadata
            expr_df = pd.DataFrame()
        
        # Save to CSV
        expression_file = output_path / f"{geo_id}_expression.csv"
        metadata_file = output_path / f"{geo_id}_metadata.csv"
        
        expr_df.to_csv(expression_file)
        metadata_df.to_csv(metadata_file, index=False)
        
        # Create summary
        result = {
            "success": True,
            "geo_id": geo_id,
            "expression_file": str(expression_file),
            "metadata_file": str(metadata_file),
            "n_samples": len(metadata_df),
            "n_genes": len(expr_df),
            "platform": gpl_name,
            "summary": gse.metadata.get('summary', [''])[0][:500],  # Truncate long summaries
            "sample_groups": metadata_df['disease_state'].value_counts().to_dict() if 'disease_state' in metadata_df.columns else {}
        }
        
        # Save metadata JSON
        metadata_json = output_path / f"{geo_id}_info.json"
        with open(metadata_json, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"✓ Downloaded {geo_id}: {result['n_samples']} samples, {result['n_genes']} genes")
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "geo_id": geo_id
        }
