"""API Usage Auditing and Tracking."""
from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any
from src.configs.settings import SETTINGS


class UsageAuditor:
    """Tracks and logs API usage to CSV for compliance monitoring."""
    
    def __init__(self, audit_file: str = "work/api_usage_audit.csv"):
        self.audit_file = Path(audit_file)
        self.audit_file.parent.mkdir(exist_ok=True)
        
        # Create CSV with headers if it doesn't exist
        if not self.audit_file.exists():
            with open(self.audit_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp",
                    "date",
                    "tier",
                    "model",
                    "prompt_tokens",
                    "response_tokens",
                    "total_tokens",
                    "operation",
                    "run_id"
                ])
    
    def log_request(
        self,
        tier: str,
        model: str,
        usage_metadata: Dict[str, Any],
        operation: str = "generate",
        run_id: str = ""
    ):
        """Log an API request to the audit file."""
        timestamp = datetime.now().isoformat()
        today = str(date.today())
        
        prompt_tokens = usage_metadata.get("prompt_token_count", 0)
        response_tokens = usage_metadata.get("candidates_token_count", 0)
        total_tokens = usage_metadata.get("total_token_count", 0)
        
        with open(self.audit_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                today,
                tier,
                model,
                prompt_tokens,
                response_tokens,
                total_tokens,
                operation,
                run_id
            ])
    
    def get_daily_summary(self, target_date: str = None) -> Dict[str, Any]:
        """Get summary of usage for a specific date."""
        if target_date is None:
            target_date = str(date.today())
        
        if not self.audit_file.exists():
            return {"error": "No audit data available"}
        
        summary = {
            "date": target_date,
            "total_requests": 0,
            "total_tokens": 0,
            "by_tier": {
                "pro": {"requests": 0, "tokens": 0},
                "flash": {"requests": 0, "tokens": 0},
                "lite": {"requests": 0, "tokens": 0}
            }
        }
        
        with open(self.audit_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["date"] == target_date:
                    summary["total_requests"] += 1
                    summary["total_tokens"] += int(row.get("total_tokens", 0) or 0)
                    
                    tier = row["tier"]
                    if tier in summary["by_tier"]:
                        summary["by_tier"][tier]["requests"] += 1
                        summary["by_tier"][tier]["tokens"] += int(row.get("total_tokens", 0) or 0)
        
        # Add quota information
        summary["quotas"] = {
            "pro": f"{summary['by_tier']['pro']['requests']}/{SETTINGS.quota_pro}",
            "flash": f"{summary['by_tier']['flash']['requests']}/{SETTINGS.quota_flash}",
            "lite": f"{summary['by_tier']['lite']['requests']}/{SETTINGS.quota_lite}"
        }
        
        return summary
    
    def get_compliance_status(self) -> Dict[str, Any]:
        """Check if usage is within free tier limits."""
        summary = self.get_daily_summary()
        
        compliance = {
            "date": summary["date"],
            "compliant": True,
            "warnings": []
        }
        
        # Check each tier
        for tier in ["pro", "flash", "lite"]:
            requests = summary["by_tier"][tier]["requests"]
            quota = getattr(SETTINGS, f"quota_{tier}")
            usage_pct = (requests / quota * 100) if quota > 0 else 0
            
            if requests >= quota:
                compliance["compliant"] = False
                compliance["warnings"].append(f"{tier.upper()} tier exhausted ({requests}/{quota})")
            elif usage_pct >= 90:
                compliance["warnings"].append(f"{tier.upper()} tier at {usage_pct:.0f}% ({requests}/{quota})")
            elif usage_pct >= 75:
                compliance["warnings"].append(f"{tier.upper()} tier at {usage_pct:.0f}% ({requests}/{quota})")
        
        return compliance


# Global auditor instance
USAGE_AUDITOR = UsageAuditor()
