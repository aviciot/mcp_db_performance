# Create Performance Indexes for Merchant Statement ETL

## **Priority**: High

## **Problem**
ETL query takes **30-60 minutes per batch** (500 contracts). Root cause:
1. INDEX SKIP SCAN - Scans 2000 blocks instead of 50 (wrong index column order)
2. All 7 partitions scanned instead of 1-2 (missing covering index)

## **Solution**
Create 2 indexes. Expected improvement: **30-50% faster** (saves 1-2 hours daily).

---

## **DDL Statements**

```sql
-- Index #1: Fix INDEX SKIP SCAN (reduces 2000 blocks → 50 blocks)
CREATE INDEX idx_ms_contract_ready_status 
ON OWS.MERCHANT_STATEMENT (
  CONTRACT_ID,
  READY_DATE,
  STATEMENT_STATUS,
  PAYMENT_DATE
)
LOCAL
TABLESPACE <appropriate_tablespace>
PARALLEL 4
NOLOGGING;

EXEC DBMS_STATS.GATHER_INDEX_STATS('OWS', 'IDX_MS_CONTRACT_READY_STATUS');

-- Index #2: Enable partition pruning (scans 1-2 partitions instead of all 7)
CREATE INDEX idx_mse_stmt_payment_doc 
ON OWS.MERCHANT_STATEMENT_ENTRY (
  MERCHANT_STATEMENT__OID,
  PAYMENT_DATE,
  TRANS_DOC_ID,
  TRANS_MTR_ID
)
LOCAL
TABLESPACE <appropriate_tablespace>
PARALLEL 4
NOLOGGING;

EXEC DBMS_STATS.GATHER_INDEX_STATS('OWS', 'IDX_MSE_STMT_PAYMENT_DOC');
```

**Disk Space**: ~70-90 MB total

---

## **Implementation**
1. Create in DEV → Test execution plan
2. Deploy to QA → Validate
3. Deploy to PROD (online, no downtime)

**Validation**: 
- INDEX RANGE SCAN (not SKIP SCAN)
- 1-2 partitions scanned (not 7)
- Runtime reduced 30-50%

**Rollback**:
```sql
DROP INDEX OWS.idx_ms_contract_ready_status;
DROP INDEX OWS.idx_mse_stmt_payment_doc;
```
