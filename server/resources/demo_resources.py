from mcp_app import mcp
import json


# ═══════════════════════════════════════════════════════════════════════════
# RESOURCE - Refund Policy
# ═══════════════════════════════════════════════════════════════════════════
@mcp.resource(uri="company://policies/refund")
def get_refund_policy() -> str:
    """Company refund policy resource."""
    policy = {
        "policy_name": "Company Refund Policy",
        "version": "2.0",
        "effective_date": "2024-01-01",
        "details": {
            "refund_window": "30 days from purchase",
            "valid_reasons": [
                "defective - product has defects",
                "wrong_item - received incorrect item",
                "changed_mind - customer changed their mind",
                "not_as_described - product doesn't match description"
            ],
            "restocking_fee": "10% for non-defective items",
            "defective_items": "Full refund, no fees",
            "processing_time": "3-5 business days",
            "requirements": [
                "Original packaging intact",
                "Receipt or order number",
                "Valid reason from approved list"
            ]
        }
    }
    return json.dumps(policy, indent=2)