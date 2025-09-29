import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [data, setData] = useState({
    experiments: [],
    variants: [],
    assignments: [],
    events: [],
    users: [],
    reports: [],
    summary: null
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('experiments');

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Check API health
      const healthResponse = await axios.get(`${API_BASE_URL}/health`);
      console.log('API Health:', healthResponse.data);
      
      // Fetch real data from the new analytics endpoints
      const [experimentsRes, variantsRes, assignmentsRes, eventsRes, usersRes, reportsRes, summaryRes] = await Promise.allSettled([
        axios.get(`${API_BASE_URL}/api/v1/analytics/experiments`),
        axios.get(`${API_BASE_URL}/api/v1/analytics/variants`),
        axios.get(`${API_BASE_URL}/api/v1/analytics/assignments`),
        axios.get(`${API_BASE_URL}/api/v1/analytics/events?limit=50`),
        axios.get(`${API_BASE_URL}/api/v1/analytics/users`),
        axios.get(`${API_BASE_URL}/api/v1/analytics/reports`),
        axios.get(`${API_BASE_URL}/api/v1/analytics/summary`)
      ]);
      
      // Extract data from successful responses
      const experiments = experimentsRes.status === 'fulfilled' ? experimentsRes.value.data.experiments : [];
      const variants = variantsRes.status === 'fulfilled' ? variantsRes.value.data.variants : [];
      const assignments = assignmentsRes.status === 'fulfilled' ? assignmentsRes.value.data.assignments : [];
      const events = eventsRes.status === 'fulfilled' ? eventsRes.value.data.events : [];
      const users = usersRes.status === 'fulfilled' ? usersRes.value.data.users : [];
      const reports = reportsRes.status === 'fulfilled' ? reportsRes.value.data.reports : [];
      const summary = summaryRes.status === 'fulfilled' ? summaryRes.value.data : null;
      
      setData({
        experiments: experiments || [],
        variants: variants || [],
        assignments: assignments || [],
        events: events || [],
        users: users || [],
        reports: reports || [],
        summary: summary || null
      });
      
      console.log('Real data loaded:', { 
        experiments: experiments?.length || 0, 
        variants: variants?.length || 0, 
        assignments: assignments?.length || 0, 
        events: events?.length || 0, 
        users: users?.length || 0, 
        reports: reports?.length || 0 
      });
      
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Failed to fetch data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const renderTable = (items, columns) => {
    if (!items || items.length === 0) {
      return <p>No data available</p>;
    }

    return (
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col, index) => (
                <th key={index}>{col.header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item, index) => (
              <tr key={index}>
                {columns.map((col, colIndex) => (
                  <td key={colIndex}>
                    {col.render ? col.render(item[col.key], item) : item[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const tabs = [
    { id: 'experiments', label: 'Experiments', count: data.experiments?.length || 0 },
    { id: 'variants', label: 'Variants', count: data.variants?.length || 0 },
    { id: 'assignments', label: 'Assignments', count: data.assignments?.length || 0 },
    { id: 'events', label: 'Events', count: data.events?.length || 0 },
    { id: 'users', label: 'Users', count: data.users?.length || 0 },
    { id: 'reports', label: 'Reports', count: data.reports?.length || 0 },
    { id: 'summary', label: 'Summary', count: data.summary ? '📊' : 0 }
  ];

  const getColumns = (tab) => {
    switch (tab) {
      case 'experiments':
        return [
          { key: 'id', header: 'ID' },
          { key: 'name', header: 'Name' },
          { key: 'status', header: 'Status' },
          { key: 'created_at', header: 'Created', render: (value) => formatDate(value) }
        ];
      case 'variants':
        return [
          { key: 'id', header: 'ID' },
          { key: 'experiment_id', header: 'Experiment ID' },
          { key: 'name', header: 'Name' },
          { key: 'key', header: 'Key' },
          { key: 'allocation_pct', header: 'Allocation %' },
          { key: 'is_control', header: 'Control', render: (value) => value ? 'Yes' : 'No' }
        ];
      case 'assignments':
        return [
          { key: 'id', header: 'ID' },
          { key: 'experiment_name', header: 'Experiment' },
          { key: 'variant_name', header: 'Variant' },
          { key: 'user_id', header: 'User ID' },
          { key: 'is_control', header: 'Control', render: (value) => value ? 'Yes' : 'No' },
          { key: 'assigned_at', header: 'Assigned', render: (value) => formatDate(value) }
        ];
      case 'events':
        return [
          { key: 'id', header: 'ID', render: (value) => value.substring(0, 8) + '...' },
          { key: 'experiment_name', header: 'Experiment' },
          { key: 'variant_name', header: 'Variant' },
          { key: 'user_name', header: 'User' },
          { key: 'event_type', header: 'Type' },
          { key: 'timestamp', header: 'Time', render: (value) => formatDate(value) }
        ];
      case 'users':
        return [
          { key: 'user_id', header: 'User ID' },
          { key: 'email', header: 'Email' },
          { key: 'name', header: 'Name' },
          { key: 'is_active', header: 'Active', render: (value) => value ? 'Yes' : 'No' },
          { key: 'created_at', header: 'Created', render: (value) => formatDate(value) }
        ];
      case 'reports':
        return [
          { key: 'experiment_id', header: 'Experiment ID' },
          { key: 'variant_id', header: 'Variant ID' },
          { key: 'variant_name', header: 'Variant Name' },
          { key: 'is_control', header: 'Control', render: (value) => value ? 'Yes' : 'No' },
          { key: 'experiment_name', header: 'Experiment Name' },
          { key: 'date', header: 'Date', render: (value) => value ? formatDate(value) : 'N/A' },
          { key: 'total_events', header: 'Total Events' },
          { key: 'unique_users', header: 'Unique Users' },
          { key: 'conversion_rate', header: 'Conversion Rate', render: (value) => `${(value * 100).toFixed(2)}%` },
          { key: 'avg_score', header: 'Avg Score', render: (value) => value.toFixed(2) },
          { key: 'statistical_significance', header: 'Significance', render: (value) => `${(value * 100).toFixed(1)}%` }
        ];
      case 'summary':
        return [
          { key: 'source', header: 'Data Source' },
          { key: 'experiments', header: 'Experiments' },
          { key: 'variants', header: 'Variants' },
          { key: 'assignments', header: 'Assignments' },
          { key: 'users', header: 'Users' },
          { key: 'events', header: 'Events' },
          { key: 'reports', header: 'Reports' }
        ];
      default:
        return [];
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🧪 Experiments Platform Dashboard</h1>
        <p>View and manage your experiments, users, and data</p>
      </header>

      <div className="App-content">
        <div className="tabs">
          {tabs.map(tab => (
            <button
              key={tab.id}
              className={`tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label} ({tab.count})
            </button>
          ))}
        </div>

        <div className="tab-content">
          {loading && <p>Loading...</p>}
          {error && <p className="error">Error: {error}</p>}
          
          {!loading && !error && data ? (
            <div>
              <h2>{tabs.find(t => t.id === activeTab)?.label}</h2>
              {activeTab === 'summary' ? (
                <div className="summary-content">
                  {data.summary ? (
                    <div>
                      <div className="summary-grid">
                        <div className="summary-card">
                          <h3>📊 PostgreSQL Data</h3>
                          <div className="summary-stats">
                            <div className="stat">
                              <span className="stat-label">Experiments:</span>
                              <span className="stat-value">{data.summary.postgresql?.experiments || 0}</span>
                            </div>
                            <div className="stat">
                              <span className="stat-label">Variants:</span>
                              <span className="stat-value">{data.summary.postgresql?.variants || 0}</span>
                            </div>
                            <div className="stat">
                              <span className="stat-label">Assignments:</span>
                              <span className="stat-value">{data.summary.postgresql?.assignments || 0}</span>
                            </div>
                            <div className="stat">
                              <span className="stat-label">Active Users:</span>
                              <span className="stat-value">{data.summary.postgresql?.active_users || 0}</span>
                            </div>
                          </div>
                        </div>
                        
                        <div className="summary-card">
                          <h3>⚡ ClickHouse Data</h3>
                          <div className="summary-stats">
                            <div className="stat">
                              <span className="stat-label">Events:</span>
                              <span className="stat-value">{data.summary.clickhouse?.events || 0}</span>
                            </div>
                            <div className="stat">
                              <span className="stat-label">Reports:</span>
                              <span className="stat-value">{data.summary.clickhouse?.reports || 0}</span>
                            </div>
                          </div>
                        </div>
                        
                        <div className="summary-card">
                          <h3>🎯 Total Records</h3>
                          <div className="summary-stats">
                            <div className="stat total">
                              <span className="stat-label">All Data:</span>
                              <span className="stat-value">{data.summary.total_records || 0}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p>No summary data available</p>
                  )}
                </div>
              ) : (
                renderTable(data[activeTab] || [], getColumns(activeTab))
              )}
            </div>
          ) : !loading && !error ? (
            <div>
              <p>No data available. Please try refreshing the page.</p>
            </div>
          ) : null}
        </div>

        <div className="info-section">
          <h3>📊 System Status</h3>
          <div className="status-grid">
            <div className="status-item">
              <strong>API Status:</strong> <span className="status-healthy">✅ Healthy</span>
            </div>
            <div className="status-item">
              <strong>Database:</strong> <span className="status-healthy">✅ Connected</span>
            </div>
            <div className="status-item">
              <strong>Prometheus:</strong> <span className="status-healthy">✅ Monitoring</span>
            </div>
            <div className="status-item">
              <strong>Grafana:</strong> <span className="status-healthy">✅ Available</span>
            </div>
          </div>
          
          <div className="links">
            <h4>🔗 Quick Links</h4>
            <a href="http://localhost:8000/health" target="_blank" rel="noopener noreferrer">
              API Health Check
            </a>
            <a href="http://localhost:8000/metrics" target="_blank" rel="noopener noreferrer">
              Prometheus Metrics
            </a>
            <a href="http://localhost:9090" target="_blank" rel="noopener noreferrer">
              Prometheus Dashboard
            </a>
            <a href="http://localhost:3000" target="_blank" rel="noopener noreferrer">
              Grafana Dashboard
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
