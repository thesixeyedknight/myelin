"""Verify file parsers."""
from pathlib import Path
from src.tools.parsers.file_parsers import parse_cif, parse_pdb

def test_parsers():
    print("Testing File Parsers...")
    
    # Test CIF Parser
    cif_path = Path("tests/mock_test.cif")
    if cif_path.exists():
        print(f"\nParsing {cif_path}...")
        cif_output = parse_cif(cif_path)
        print(cif_output)
        
        if "Test Structure for CIF Parser" in cif_output and "Homo sapiens" in cif_output and "1.5" in cif_output:
            print("✅ CIF Parser: SUCCESS")
        else:
            print("❌ CIF Parser: FAILURE (Missing metadata)")
    else:
        print(f"❌ CIF Parser: FAILURE (File not found: {cif_path})")

    # Test PDB Parser
    pdb_path = Path("tests/mock_test.pdb")
    if pdb_path.exists():
        print(f"\nParsing {pdb_path}...")
        pdb_output = parse_pdb(pdb_path)
        print(pdb_output)
        
        if "TEST STRUCTURE FOR PDB PARSER" in pdb_output and "HOMO SAPIENS" in pdb_output and "2.0" in pdb_output:
            if "GIVEQCCASV" in pdb_output or "GIVEQCCASVC" in pdb_output: # Checking partial sequence match (GIVEQCCASV...)
                 # Note: My mock sequence was "GLY ILE VAL GLU GLN CYS CYS ALA SER VAL" -> GIVEQCCASV
                 print("✅ PDB Parser: SUCCESS")
            else:
                 print("❌ PDB Parser: FAILURE (Sequence mismatch)")
        else:
            print("❌ PDB Parser: FAILURE (Missing metadata)")
    else:
        print(f"❌ PDB Parser: FAILURE (File not found: {pdb_path})")

if __name__ == "__main__":
    test_parsers()
