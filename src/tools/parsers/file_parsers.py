"""File format parsers for RAG indexing."""
from pathlib import Path
from typing import Dict, Any, Optional
import json
import pandas as pd

import re
from collections import defaultdict

def parse_cif(filepath: Path) -> str:
    """
    Parse mmCIF file (STAR format) to extract metadata and sequences.
    Robust implementation without BioPython.
    """
    with open(filepath, "r") as f:
        content = f.read()

    # Tokenizer for STAR format
    # Handles quoted strings (', "), simple values, and comments
    token_pattern = re.compile(r"(?P<quote>['\"])(?P<quoted_value>[\s\S]*?)(?P=quote)|(?P<value>[^\s#]+)|(?P<comment>#.*)")
    
    tokens = []
    for match in token_pattern.finditer(content):
        if match.group("quoted_value") is not None:
            tokens.append(match.group("quoted_value"))
        elif match.group("value") is not None:
            val = match.group("value")
            # Handle multi-line text fields (semi-colon delimited) - simplified for now
            if val == ";": 
                continue 
            tokens.append(val)
        # Skip comments

    # Parser state
    data = defaultdict(list)
    current_loop_keys = []
    in_loop = False
    i = 0
    
    metadata = {
        "title": "",
        "organism": set(),
        "resolution": None,
        "chains": set(),
        "sequences": []
    }

    while i < len(tokens):
        token = tokens[i]
        
        if token == "loop_":
            in_loop = True
            current_loop_keys = []
            i += 1
            continue
            
        if token.startswith("_"):
            if in_loop:
                current_loop_keys.append(token)
                i += 1
            else:
                # Single key-value pair
                key = token
                if i + 1 < len(tokens):
                    val = tokens[i+1]
                    # Store specific metadata
                    if key == "_struct.title":
                        metadata["title"] = val
                    elif key == "_refine.ls_d_res_high":
                        try:
                            metadata["resolution"] = float(val)
                        except ValueError:
                            pass
                    i += 2
                else:
                    i += 1
        else:
            # Value in a loop
            if in_loop and current_loop_keys:
                # Map values to keys
                row_values = {}
                for k in current_loop_keys:
                    if i < len(tokens):
                        row_values[k] = tokens[i]
                        i += 1
                    else:
                        break
                
                # Extract data from loop rows
                if "_entity_src_gen.pdbx_gene_src_scientific_name" in row_values:
                    name = row_values["_entity_src_gen.pdbx_gene_src_scientific_name"]
                    if name and name != "?":
                        metadata["organism"].add(name)
                
                if "_entity_poly.pdbx_seq_one_letter_code" in row_values:
                    seq = row_values["_entity_poly.pdbx_seq_one_letter_code"]
                    # Clean up sequence (remove newlines, spaces if any)
                    seq = seq.replace("\n", "").replace(";", "")
                    if seq and seq != "?":
                        metadata["sequences"].append(seq)
                        
            else:
                i += 1

    # Format output
    output = "mmCIF Structure:\n"
    if metadata["title"]:
        output += f"  Title: {metadata['title']}\n"
    if metadata["organism"]:
        output += f"  Organism: {', '.join(sorted(metadata['organism']))}\n"
    if metadata["resolution"]:
        output += f"  Resolution: {metadata['resolution']} Å\n"
    
    if metadata["sequences"]:
        output += f"  Sequences ({len(metadata['sequences'])} found):\n"
        for idx, seq in enumerate(metadata['sequences'], 1):
            output += f"    #{idx}: {seq[:50]}..." + (f" ({len(seq)} aa)" if len(seq) > 50 else "") + "\n"

    return output


def parse_text(filepath: Path) -> str:
    """Parse plain text file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        # Try with latin-1 if UTF-8 fails
        with open(filepath, "r", encoding="latin-1") as f:
            return f.read()


def parse_json(filepath: Path) -> str:
    """Parse JSON file and return as formatted text."""
    with open(filepath, "r") as f:
        data = json.load(f)
    # Convert to pretty-printed JSON string
    return json.dumps(data, indent=2)


def parse_csv(filepath: Path) -> str:
    """Parse CSV file and return as text."""
    df = pd.read_csv(filepath)
    # Convert to readable format
    return f"CSV Data ({len(df)} rows, {len(df.columns)} columns):\n\n{df.to_string()}"


def parse_fasta(filepath: Path) -> str:
    """Parse FASTA file and return sequences with metadata."""
    sequences = []
    with open(filepath, "r") as f:
        current_header = None
        current_seq = []
        
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                # Save previous sequence
                if current_header:
                    sequences.append({
                        "header": current_header,
                        "sequence": "".join(current_seq)
                    })
                # Start new sequence
                current_header = line[1:]
                current_seq = []
            else:
                current_seq.append(line)
        
        # Save last sequence
        if current_header:
            sequences.append({
                "header": current_header,
                "sequence": "".join(current_seq)
            })
    
    # Format as text
    output = f"FASTA file with {len(sequences)} sequences:\n\n"
    for i, seq in enumerate(sequences, 1):
        output += f"Sequence {i}:\n"
        output += f"  Header: {seq['header']}\n"
        output += f"  Length: {len(seq['sequence'])} bp\n"
        output += f"  Sequence (first 100bp): {seq['sequence'][:100]}...\n\n"
    
    return output


def parse_pdb(filepath: Path) -> str:
    """Parse PDB file and extract metadata."""
    with open(filepath, "r") as f:
        lines = f.readlines()
    
    metadata = {
        "title": [],
        "chains": set(),
        "resolution": None,
        "organism": set(),
        "sequences": defaultdict(list) # chain -> list of residues
    }
    
    # 3-letter to 1-letter mapping
    aa_map = {
        'ALA': 'A', 'CYS': 'C', 'ASP': 'D', 'GLU': 'E', 'PHE': 'F',
        'GLY': 'G', 'HIS': 'H', 'ILE': 'I', 'LYS': 'K', 'LEU': 'L',
        'MET': 'M', 'ASN': 'N', 'PRO': 'P', 'GLN': 'Q', 'ARG': 'R',
        'SER': 'S', 'THR': 'T', 'VAL': 'V', 'TRP': 'W', 'TYR': 'Y'
    }

    for line in lines:
        record = line[:6].strip()
        
        if record == "TITLE":
            metadata["title"].append(line[10:].strip())
            
        elif record == "REMARK":
            # Resolution
            if line.startswith("REMARK   2 RESOLUTION"):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        metadata["resolution"] = float(parts[3])
                    except ValueError:
                        pass
                        
        elif record == "SOURCE":
            if "ORGANISM_SCIENTIFIC" in line:
                # Extract organism name (rough parsing)
                parts = line.split("ORGANISM_SCIENTIFIC:")
                if len(parts) > 1:
                    org = parts[1].split(";")[0].strip()
                    if org:
                        metadata["organism"].add(org)

        elif record == "SEQRES":
            # SEQRES  1 A  21  GLY ILE VAL GLU GLN CYS CYS ...
            chain = line[11:12].strip()
            residues = line[19:].split()
            for res in residues:
                if res in aa_map:
                    metadata["sequences"][chain].append(aa_map[res])
                    metadata["chains"].add(chain)

    # Format output
    output = "PDB Structure:\n"
    
    full_title = " ".join(metadata["title"])
    if full_title:
        output += f"  Title: {full_title}\n"
        
    if metadata["organism"]:
        output += f"  Organism: {', '.join(sorted(metadata['organism']))}\n"
        
    if metadata["resolution"]:
        output += f"  Resolution: {metadata['resolution']} Å\n"
        
    if metadata["chains"]:
        output += f"  Chains: {', '.join(sorted(metadata['chains']))}\n"
        
    if metadata["sequences"]:
        output += "  Sequences:\n"
        for chain, seq_list in sorted(metadata["sequences"].items()):
            seq_str = "".join(seq_list)
            output += f"    Chain {chain}: {seq_str[:50]}..." + (f" ({len(seq_str)} aa)" if len(seq_str) > 50 else "") + "\n"
    
    return output


# Supported formats and their parsers
PARSERS = {
    ".txt": parse_text,
    ".md": parse_text,
    ".json": parse_json,
    ".csv": parse_csv,
    ".fasta": parse_fasta,
    ".fa": parse_fasta,
    ".fa": parse_fasta,
    ".pdb": parse_pdb,
    ".cif": parse_cif,
    ".mmcif": parse_cif
}


def parse_file(filepath: str) -> Dict[str, Any]:
    """
    Parse a file and return its content as text.
    
    Returns:
        Dict with 'text' and 'metadata' keys, or 'error' key on failure
    """
    path = Path(filepath)
    
    # Validation
    if not path.exists():
        return {"error": f"File not found: {filepath}"}
    
    if not path.is_file():
        return {"error": f"Path is not a file: {filepath}"}
    
    # Check file size
    size_mb = path.stat().st_size / (1024 * 1024)
    from src.configs.settings import SETTINGS
    if size_mb > SETTINGS.rag_max_file_size_mb:
        return {"error": f"File too large ({size_mb:.1f}MB). Maximum: {SETTINGS.rag_max_file_size_mb}MB"}
    
    # Get parser
    suffix = path.suffix.lower()
    if suffix not in PARSERS:
        return {
            "error": f"Unsupported file format: {suffix}. "
                     f"Supported formats: {', '.join(PARSERS.keys())}"
        }
    
    # Parse file
    try:
        parser = PARSERS[suffix]
        text = parser(path)
        
        return {
            "text": text,
            "metadata": {
                "source": str(path),
                "format": suffix,
                "size_bytes": path.stat().st_size
            }
        }
    except Exception as e:
        return {"error": f"Failed to parse {suffix} file: {str(e)}"}
