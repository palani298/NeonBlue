# Data Management Strategy: PostgreSQL vs ClickHouse

## Overview

This document outlines the data management strategy for maintaining data across PostgreSQL (operational database) and ClickHouse (analytics database) in the experimentation platform.

## Why Both Databases?

### PostgreSQL (Source of Truth)
- **ACID Transactions**: Ensures data consistency for business operations
- **Real-time Queries**: Fast response for user assignments and experiment configuration
- **Relational Integrity**: Maintains referential integrity between experiments, variants, assignments, and events
- **Immediate Consistency**: Critical for user-facing operations

### ClickHouse (Analytics Engine)
- **Columnar Storage**: Optimized for analytical queries and aggregations
- **Time-series Optimizations**: Perfect for event analytics and reporting
- **Massive Scale**: Handles billions of events efficiently
- **Complex Analytics**: Sub-second response times for complex analytical queries

## Data Flow Architecture

```
┌─────────────────┐    CDC     ┌─────────────────┐
│   PostgreSQL    │ ──────────► │   ClickHouse    │
│  (Operational)  │   Kafka    │   (Analytics)   │
└─────────────────┘            └─────────────────┘
         │                              │
         ▼                              ▼
   Real-time APIs                Analytics APIs
   User Assignments              Reports & Dashboards
   Experiment Config             Historical Analysis
```

## Data Retention Strategy

### PostgreSQL Retention Policies

| Table | Retention Period | Reason |
|-------|------------------|---------|
| `experiments` | 2 years | Historical analysis and compliance |
| `variants` | 2 years | Referenced by experiments |
| `assignments` | 1 year | User behavior analysis |
| `events` | 90 days | Real-time operations only |
| `outbox_events` | 30 days | CDC processing complete |
| `users` | Indefinite | User management |

### ClickHouse Retention Policies

| Table | Retention Period | Reason |
|-------|------------------|---------|
| `events_processed` | 2 years | Long-term analytics |
| `experiment_daily_stats` | 5 years | Historical trends |
| `assignments_processed` | 2 years | User behavior analysis |

## Data Management APIs

### 1. Data Statistics
```bash
GET /api/v1/data-management/stats
```
Returns current data volumes and statistics for both databases.

### 2. Data Cleanup
```bash
POST /api/v1/data-management/cleanup
```
Cleans up old data based on retention policies.

### 3. Retention Policies
```bash
GET /api/v1/data-management/retention-policies
```
Shows current data retention policies.

## Recommended Data Management Schedule

### Daily Tasks
- **Event Cleanup**: Remove events older than 90 days from PostgreSQL
- **Outbox Cleanup**: Remove processed outbox events older than 30 days
- **Health Checks**: Monitor data flow between PostgreSQL and ClickHouse

### Weekly Tasks
- **Data Validation**: Verify data consistency between databases
- **Performance Analysis**: Check query performance and optimize if needed
- **Storage Monitoring**: Monitor disk usage and growth rates

### Monthly Tasks
- **Retention Review**: Review and adjust retention policies based on usage
- **Archive Old Data**: Move very old data to cold storage (S3)
- **Capacity Planning**: Plan for future storage needs

## Data Archival Strategy

### Hot Data (PostgreSQL)
- **Current month**: All data in PostgreSQL
- **Real-time queries**: User assignments, experiment configuration
- **Immediate consistency**: Business operations

### Warm Data (ClickHouse)
- **Last 2 years**: All data in ClickHouse
- **Analytical queries**: Reports, dashboards, analysis
- **Optimized for reads**: Columnar storage, aggregations

### Cold Data (S3)
- **Older than 2 years**: Archived to S3
- **Compliance**: Long-term storage for regulatory requirements
- **Cost optimization**: Cheaper storage for rarely accessed data

## Implementation Examples

### Clean Up Old Events
```bash
curl -X POST "http://localhost:8001/api/v1/data-management/cleanup" \
  -H "Authorization: Bearer admin_token_123" \
  -H "Content-Type: application/json" \
  -d '{
    "cleanup_events": true,
    "events_retention_days": 90,
    "dry_run": true
  }'
```

### Get Data Statistics
```bash
curl -X GET "http://localhost:8001/api/v1/data-management/stats" \
  -H "Authorization: Bearer admin_token_123"
```

## Benefits of This Strategy

### Cost Optimization
- **PostgreSQL**: Only keeps recent data (90 days for events)
- **ClickHouse**: Optimized for analytical workloads
- **S3**: Long-term storage at minimal cost

### Performance
- **PostgreSQL**: Fast for transactional operations
- **ClickHouse**: Fast for analytical queries
- **Separation of Concerns**: Each database optimized for its use case

### Scalability
- **Horizontal Scaling**: ClickHouse can scale independently
- **Storage Growth**: Managed through retention policies
- **Query Performance**: Each database optimized for its workload

## Monitoring and Alerting

### Key Metrics to Monitor
- **Data Volume Growth**: Track growth rates in both databases
- **CDC Lag**: Monitor replication delay between PostgreSQL and ClickHouse
- **Query Performance**: Track query response times
- **Storage Usage**: Monitor disk usage and growth

### Alerts to Set Up
- **High CDC Lag**: Alert if replication delay > 5 minutes
- **Storage Threshold**: Alert if disk usage > 80%
- **Query Timeout**: Alert if analytical queries > 30 seconds
- **Data Inconsistency**: Alert if data doesn't match between databases

## Conclusion

This dual-database strategy provides:
- **Operational Excellence**: PostgreSQL for real-time operations
- **Analytical Power**: ClickHouse for complex analytics
- **Cost Efficiency**: Right-sized storage for each use case
- **Scalability**: Independent scaling of operational and analytical workloads

The data management APIs provide the tools needed to maintain this strategy effectively while ensuring data consistency and optimal performance.
