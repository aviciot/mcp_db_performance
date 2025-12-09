# server/tools/plan_visualizer.py
# Visual execution plan formatter

def build_visual_plan(plan_details: list, show_costs: bool = True) -> str:
    """
    Build ASCII tree visualization of execution plan.
    
    Args:
        plan_details: List of plan steps from oracle_collector_impl
        show_costs: Include cost/cardinality in output
    
    Returns:
        Formatted ASCII tree string
    """
    if not plan_details:
        return "No execution plan available"
    
    lines = []
    
    # Root operation (usually SELECT STATEMENT)
    root = plan_details[0]
    root_cost = root.get("cost", 0)
    lines.append(f"📊 {root.get('operation', 'QUERY')} (Total Cost: {root_cost})")
    lines.append("")
    
    # Build tree recursively
    for i, step in enumerate(plan_details[1:], 1):  # Skip root
        depth = step.get("depth", 0)
        operation = step.get("operation", "")
        options = step.get("options", "")
        object_name = step.get("object_name", "")
        cost = step.get("cost", 0)
        cardinality = step.get("cardinality", 0)
        
        # Determine if this is the last child at this depth
        is_last = True
        for j in range(i + 1, len(plan_details)):
            if plan_details[j].get("depth", 0) <= depth:
                if plan_details[j].get("depth", 0) == depth:
                    is_last = False
                break
        
        # Build tree branch characters
        if depth == 0:
            prefix = ""
        else:
            prefix = "  " * (depth - 1)
            if is_last:
                prefix += "└─ "
            else:
                prefix += "├─ "
        
        # Format operation line
        op_text = f"{operation} {options}".strip()
        if object_name:
            op_text += f": {object_name}"
        
        # Add performance indicators
        if show_costs:
            op_text += f" (Cost: {cost}"
            if cardinality is not None and cardinality > 0:
                op_text += f", Rows: {cardinality:,}"
            op_text += ")"
        
        # Add warning emoji for problematic operations
        warning = get_operation_warning(operation, options, cost, cardinality)
        if warning:
            op_text += f" {warning}"
        
        lines.append(prefix + op_text)
    
    return "\n".join(lines)


def get_operation_warning(operation: str, options: str, cost: int, cardinality: int) -> str:
    """
    Return warning emoji for potentially slow operations.
    """
    warnings = []
    
    # Handle None options
    if options is None:
        options = ""
    
    # Full table scans on large tables
    if operation == "TABLE ACCESS" and options == "FULL" and cost > 100:
        warnings.append("⚠️ HIGH-COST FULL SCAN")
    
    # Index skip scans (usually inefficient)
    if "INDEX" in operation and "SKIP SCAN" in options:
        warnings.append("⚠️ SKIP SCAN")
    
    # Large nested loops
    if "NESTED LOOPS" in operation and cardinality is not None and cardinality > 10000:
        warnings.append("⚠️ LARGE NESTED LOOP")
    
    # Partition operations scanning all partitions
    if "PARTITION" in options and "ALL" in options:
        warnings.append("⚠️ ALL PARTITIONS")
    
    # Cartesian products
    if "CARTESIAN" in operation:
        warnings.append("🚨 CARTESIAN JOIN")
    
    # Good operations get checkmarks
    if operation == "INDEX" and "RANGE SCAN" in options and cost < 10:
        warnings.append("✅")
    if operation == "INDEX" and "UNIQUE SCAN" in options:
        warnings.append("✅")
    
    return " ".join(warnings)


def get_plan_summary(plan_details: list) -> dict:
    """
    Extract key metrics from execution plan.
    
    Returns:
        Dict with summary statistics
    """
    if not plan_details:
        return {}
    
    full_scans = 0
    index_scans = 0
    skip_scans = 0
    nested_loops = 0
    hash_joins = 0
    partition_all = 0
    
    for step in plan_details:
        op = step.get("operation", "")
        opts = step.get("options", "")
        
        if op == "TABLE ACCESS" and opts == "FULL":
            full_scans += 1
        if "INDEX" in op:
            index_scans += 1
            if opts and "SKIP SCAN" in opts:
                skip_scans += 1
        if "NESTED LOOPS" in op:
            nested_loops += 1
        if "HASH JOIN" in op:
            hash_joins += 1
        if opts and "PARTITION" in opts and "ALL" in opts:
            partition_all += 1
    
    return {
        "total_steps": len(plan_details),
        "full_table_scans": full_scans,
        "index_operations": index_scans,
        "skip_scans": skip_scans,
        "nested_loops": nested_loops,
        "hash_joins": hash_joins,
        "partition_all_scans": partition_all
    }
