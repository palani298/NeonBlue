# ClickHouse Analytics Reports

This directory contains simple reports to check your ClickHouse analytics data.

## 📊 Available Reports

### 1. Basic Status Report
```bash
python3 examples/basic_clickhouse_status.py
```
- Quick overview of your data
- Shows table counts and data health
- Good for daily monitoring

### 2. Dashboard Report
```bash
python3 examples/clickhouse_dashboard.py
```
- Comprehensive dashboard view
- Shows recent activity and system status
- Includes recommendations

### 3. Summary Report
```bash
python3 examples/clickhouse_summary.py
```
- High-level summary of what's working
- Identifies issues that need attention
- Provides next steps

### 4. Generate Fresh Data
```bash
python3 examples/generate_fresh_data.py
```
- Creates test experiments, users, and events
- Helps generate fresh data for testing
- Useful when you need sample data

### 5. Complete Refresh and Report
```bash
python3 examples/refresh_and_report.py
```
- Generates fresh data AND shows reports
- One-command solution for testing
- Good for end-to-end testing

## 🔍 What the Reports Show

### Data Overview
- **Events**: Number of events processed
- **Experiments**: Number of experiments in dictionary
- **Variants**: Number of variants in dictionary  
- **Users**: Number of users in dictionary

### Data Health
- **Valid Events**: Events with proper timestamps and data
- **Latest Event**: Most recent event timestamp
- **Data Quality**: Issues like empty user IDs or invalid timestamps

### System Status
- **CDC Pipeline**: Whether Change Data Capture is working
- **Data Freshness**: How recent your data is
- **Overall Health**: System status based on data quality

## ⚠️ Common Issues

### 1. No Valid Events
- **Symptom**: All events have 1970-01-01 timestamp
- **Cause**: CDC pipeline not working properly
- **Fix**: Check Debezium and Kafka configuration

### 2. Empty User IDs
- **Symptom**: Events have empty user_id field
- **Cause**: Data transformation issues in ClickHouse
- **Fix**: Check materialized view definitions

### 3. Zero Experiment IDs
- **Symptom**: Events have experiment_id = 0
- **Cause**: Data mapping issues
- **Fix**: Check event processing logic

### 4. API Errors (404/500)
- **Symptom**: Assignment creation or event recording fails
- **Cause**: API endpoint issues
- **Fix**: Check API server logs and fix endpoint problems

## 🚀 Quick Start

1. **Check current status**:
   ```bash
   python3 examples/basic_clickhouse_status.py
   ```

2. **Generate fresh data**:
   ```bash
   python3 examples/generate_fresh_data.py
   ```

3. **View dashboard**:
   ```bash
   python3 examples/clickhouse_dashboard.py
   ```

4. **Get summary**:
   ```bash
   python3 examples/clickhouse_summary.py
   ```

## 📈 Understanding the Data

### Events Table (`events_processed`)
- Contains all processed events from your experiments
- Should have valid timestamps, user IDs, and experiment IDs
- Used for analytics and reporting

### Dictionaries
- **`experiments_dict`**: Experiment metadata
- **`variants_dict`**: Variant configurations
- **`users_dict`**: User information

### Materialized Views
- **`events_mv`**: Real-time event processing
- **`daily_stats_mv`**: Daily statistics aggregation

## 🔧 Troubleshooting

### If reports show errors:
1. Check if ClickHouse is running: `docker ps | grep clickhouse`
2. Check if API server is running: `curl http://localhost:8001/health`
3. Check Docker logs: `docker logs experiments-clickhouse`

### If no data appears:
1. Run the complete flow test: `python3 examples/test_complete_flow.py`
2. Check CDC pipeline: `docker logs experiments-debezium`
3. Verify Kafka: `docker logs experiments-kafka`

### If data quality is poor:
1. Check the CDC pipeline configuration
2. Verify event processing logic
3. Check materialized view definitions

## 💡 Tips

- Run reports regularly to monitor data health
- Use the dashboard for quick status checks
- Generate fresh data when testing new features
- Check the summary report for high-level issues
- Use the complete flow test for end-to-end validation

## 📞 Need Help?

If you're seeing issues:
1. Check the error messages in the reports
2. Look at the recommendations section
3. Check Docker logs for detailed error information
4. Run the complete flow test to verify everything works
