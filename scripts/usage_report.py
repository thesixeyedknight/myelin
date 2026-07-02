"""CLI tool to view API usage statistics."""
import sys
sys.path.insert(0, ".")

from src.agent.usage_auditor import USAGE_AUDITOR
from src.agent.rate_limits import MODEL_MANAGER
import json

def main():
    print("="*60)
    print("API USAGE REPORT")
    print("="*60)
    
    # Get today's summary
    summary = USAGE_AUDITOR.get_daily_summary()
    
    if "error" in summary:
        print(f"\n{summary['error']}")
        print("\nNo usage data recorded yet.")
        return
    
    print(f"\nDate: {summary['date']}")
    print(f"Total Requests: {summary['total_requests']}")
    print(f"Total Tokens: {summary['total_tokens']:,}")
    
    print("\n" + "-"*60)
    print("USAGE BY TIER")
    print("-"*60)
    
    for tier in ["pro", "flash", "lite"]:
        data = summary['by_tier'][tier]
        quota = summary['quotas'][tier]
        print(f"{tier.upper():8} | Requests: {quota:15} | Tokens: {data['tokens']:,}")
    
    # Check compliance
    print("\n" + "-"*60)
    print("COMPLIANCE STATUS")
    print("-"*60)
    
    compliance = USAGE_AUDITOR.get_compliance_status()
    
    if compliance['compliant']:
        print("✓ Within free tier limits")
    else:
        print("✗ QUOTA EXCEEDED")
    
    if compliance['warnings']:
        print("\nWarnings:")
        for warning in compliance['warnings']:
            print(f"  ⚠ {warning}")
    
    print("\n" + "="*60)
    print(f"Audit log: work/api_usage_audit.csv")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
