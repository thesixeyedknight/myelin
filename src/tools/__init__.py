"""Tools package initialization."""
from __future__ import annotations

# Re-export the registry API at package level (from src.tools import tool, dispatch, ...)
from .registry import tool, list_tools, dispatch  # noqa: F401

# Import all tools to register them
from src.tools import web
from src.tools import pubmed
from src.tools import blast
from src.tools import pdb_uniprot
from src.tools import shell
from src.tools import files
from src.tools import rag_tools

# Bioinformatics analysis tools
from src.tools import geo_data
from src.tools import diff_expression
from src.tools import enrichment
from src.tools import ppi_network
from src.tools import wgcna
