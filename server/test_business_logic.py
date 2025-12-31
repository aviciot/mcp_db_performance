# test_business_logic.py
"""
Test script for the Oracle business logic explanation feature.

Run from the server directory:
    python test_business_logic.py

This script tests:
1. SQL table extraction
2. Business context inference
3. Mermaid graph generation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from tools.oracle_explain_logic import extract_tables_from_sql, build_relationship_graph
from tools.oracle_business_context import (
    infer_entity_type,
    infer_domain,
    is_lookup_table
)


def test_extract_tables():
    """Test SQL parsing to extract table names."""
    print("\n=== Testing Table Extraction ===\n")
    
    test_cases = [
        # Simple SELECT
        (
            "SELECT * FROM orders WHERE status = 'ACTIVE'",
            [(None, "ORDERS")]
        ),
        # JOIN with schema
        (
            "SELECT o.*, c.name FROM SALES.orders o JOIN SALES.customers c ON o.customer_id = c.id",
            [("SALES", "ORDERS"), ("SALES", "CUSTOMERS")]
        ),
        # CTE - Note: CTE alias ACTIVE_ORDERS will also be extracted as a table reference
        # This is acceptable behavior since we resolve against actual tables later
        (
            """WITH active_orders AS (
                SELECT * FROM orders WHERE status = 'ACTIVE'
            )
            SELECT * FROM active_orders ao JOIN order_items oi ON ao.id = oi.order_id""",
            [(None, "ORDERS"), (None, "ORDER_ITEMS"), (None, "ACTIVE_ORDERS")]
        ),
        # Multiple JOINs
        (
            """SELECT t.*, m.name, s.description
            FROM PAYMENT.transactions t
            JOIN PAYMENT.merchants m ON t.merchant_id = m.id
            LEFT JOIN PAYMENT.status_codes s ON t.status = s.code""",
            [("PAYMENT", "TRANSACTIONS"), ("PAYMENT", "MERCHANTS"), ("PAYMENT", "STATUS_CODES")]
        ),
    ]
    
    passed = 0
    failed = 0
    
    for sql, expected in test_cases:
        result = extract_tables_from_sql(sql)
        result_set = set(result)
        expected_set = set(expected)
        
        if result_set == expected_set:
            print(f"✅ PASS: Extracted {len(result)} tables correctly")
            passed += 1
        else:
            print(f"❌ FAIL:")
            print(f"   SQL: {sql[:50]}...")
            print(f"   Expected: {expected_set}")
            print(f"   Got:      {result_set}")
            failed += 1
    
    print(f"\nTable Extraction: {passed} passed, {failed} failed")
    return failed == 0


def test_entity_inference():
    """Test entity type inference from table names."""
    print("\n=== Testing Entity Type Inference ===\n")
    
    test_cases = [
        ("CUSTOMER_ORDERS", ["ID", "ORDER_DATE", "TOTAL"], "order"),  # ORDER pattern matches first
        ("USER_ACCOUNTS", ["USER_ID", "EMAIL", "FIRST_NAME"], "user"),
        ("TRANS_HISTORY", ["TXN_ID", "AMOUNT", "TIMESTAMP"], "transaction"),
        ("STATUS_CODES", ["CODE", "DESCRIPTION"], "lookup"),  # _CODE pattern
        ("MERCHANT_PROFILES", ["MERCHANT_ID", "NAME", "ADDRESS"], "merchant"),
        ("AUDIT_LOG", ["LOG_ID", "ACTION", "TIMESTAMP"], "audit_log"),  # AUDIT_LOG exact match
        ("CUST_MASTER", ["ID", "NAME"], "customer"),  # CUST_ pattern
    ]
    
    passed = 0
    failed = 0
    
    for table_name, columns, expected in test_cases:
        result = infer_entity_type(table_name, columns)
        
        if result == expected:
            print(f"✅ PASS: {table_name} → {result}")
            passed += 1
        else:
            print(f"❌ FAIL: {table_name}")
            print(f"   Expected: {expected}, Got: {result}")
            failed += 1
    
    print(f"\nEntity Inference: {passed} passed, {failed} failed")
    return failed == 0


def test_domain_inference():
    """Test domain inference from context."""
    print("\n=== Testing Domain Inference ===\n")
    
    test_cases = [
        ("TRANSACTIONS", ["AMOUNT", "CARD_NUMBER", "MERCHANT_ID"], ["MERCHANTS"], "payments"),
        ("ORDERS", ["ORDER_DATE", "SHIPPING_ID", "PRODUCT_ID"], ["PRODUCTS", "SHIPPING"], "ecommerce"),
        ("EMPLOYEES", ["SALARY", "DEPARTMENT_ID", "HIRE_DATE"], ["DEPARTMENTS"], "hr"),
        ("AUDIT_TRAIL", ["ACTION", "TIMESTAMP", "CHANGE_LOG"], [], "audit"),
    ]
    
    passed = 0
    failed = 0
    
    for table_name, columns, fk_tables, expected in test_cases:
        result = infer_domain(table_name, columns, fk_tables)
        
        if result == expected:
            print(f"✅ PASS: {table_name} → {result}")
            passed += 1
        else:
            print(f"❌ FAIL: {table_name}")
            print(f"   Expected: {expected}, Got: {result}")
            failed += 1
    
    print(f"\nDomain Inference: {passed} passed, {failed} failed")
    return failed == 0


def test_lookup_detection():
    """Test lookup table detection."""
    print("\n=== Testing Lookup Table Detection ===\n")
    
    test_cases = [
        (100, 3, True, "Small row count + few columns"),
        (50000000, 3, False, "50M rows - definitely not lookup"),
        (500, 5, True, "Small count + 5 columns"),
        (None, 4, True, "Unknown count but few columns"),
        (10000, 20, False, "Many columns"),
        (5000, 3, True, "Medium count but very few columns"),
        (200000, 5, False, "200K rows - not a lookup"),
    ]
    
    passed = 0
    failed = 0
    
    for row_count, col_count, expected, desc in test_cases:
        result = is_lookup_table(row_count, col_count)
        
        if result == expected:
            print(f"✅ PASS: {desc} → {result}")
            passed += 1
        else:
            print(f"❌ FAIL: {desc}")
            print(f"   Expected: {expected}, Got: {result}")
            failed += 1
    
    print(f"\nLookup Detection: {passed} passed, {failed} failed")
    return failed == 0


def test_graph_generation():
    """Test Mermaid graph generation."""
    print("\n=== Testing Graph Generation ===\n")
    
    # Mock context with tables and relationships
    context = {
        "table_context": {
            ("SALES", "ORDERS"): {
                "table_name": "ORDERS",
                "is_core_table": True,
                "is_lookup": False,
                "inferred_entity_type": "order",
                "inferred_domain": "ecommerce",
                "row_count": 100000,
                "comment": "Customer orders"
            },
            ("SALES", "CUSTOMERS"): {
                "table_name": "CUSTOMERS",
                "is_core_table": True,
                "is_lookup": False,
                "inferred_entity_type": "customer",
                "inferred_domain": "ecommerce",
                "row_count": 50000,
                "comment": "Customer master data"
            },
            ("SALES", "STATUS_CODES"): {
                "table_name": "STATUS_CODES",
                "is_core_table": False,
                "is_lookup": True,
                "inferred_entity_type": "lookup",
                "row_count": 10,
                "comment": "Order status lookup"
            }
        },
        "relationships": [
            {
                "from": ("SALES", "ORDERS"),
                "to": ("SALES", "CUSTOMERS"),
                "from_columns": ["CUSTOMER_ID"],
                "to_columns": ["ID"]
            },
            {
                "from": ("SALES", "ORDERS"),
                "to": ("SALES", "STATUS_CODES"),
                "from_columns": ["STATUS"],
                "to_columns": ["CODE"]
            }
        ]
    }
    
    graph = build_relationship_graph(context)
    
    passed = 0
    failed = 0
    
    # Test nodes
    if len(graph["nodes"]) == 3:
        print("✅ PASS: Generated 3 nodes")
        passed += 1
    else:
        print(f"❌ FAIL: Expected 3 nodes, got {len(graph['nodes'])}")
        failed += 1
    
    # Test edges
    if len(graph["edges"]) == 2:
        print("✅ PASS: Generated 2 edges")
        passed += 1
    else:
        print(f"❌ FAIL: Expected 2 edges, got {len(graph['edges'])}")
        failed += 1
    
    # Test mermaid output
    if "erDiagram" in graph["mermaid"]:
        print("✅ PASS: Mermaid diagram starts with erDiagram")
        passed += 1
    else:
        print("❌ FAIL: Mermaid should start with erDiagram")
        failed += 1
    
    if "ORDERS" in graph["mermaid"] and "CUSTOMERS" in graph["mermaid"]:
        print("✅ PASS: Mermaid contains table names")
        passed += 1
    else:
        print("❌ FAIL: Mermaid missing table names")
        failed += 1
    
    # Show generated mermaid for visual inspection
    print("\n📊 Generated Mermaid Diagram:")
    print("-" * 40)
    print(graph["mermaid"])
    print("-" * 40)
    
    print(f"\nGraph Generation: {passed} passed, {failed} failed")
    return failed == 0


def run_all_tests():
    """Run all unit tests."""
    print("=" * 60)
    print("Oracle Business Logic Feature - Unit Tests")
    print("=" * 60)
    
    all_passed = True
    
    all_passed &= test_extract_tables()
    all_passed &= test_entity_inference()
    all_passed &= test_domain_inference()
    all_passed &= test_lookup_detection()
    all_passed &= test_graph_generation()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
