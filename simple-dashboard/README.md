# 🧪 Experiments Platform Dashboard

A simple React dashboard to view and manage your experiments platform data.

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   cd simple-dashboard
   npm install
   ```

2. **Start the development server:**
   ```bash
   npm start
   ```

3. **Open your browser:**
   Navigate to `http://localhost:3000`

## 📊 Features

- **Experiments View**: See all experiments with their status and creation dates
- **Variants View**: View experiment variants and their traffic allocation
- **Assignments View**: Track user assignments to experiment variants
- **Events View**: Monitor user events and interactions
- **Users View**: Manage user accounts and their status
- **API Tokens View**: View and manage API authentication tokens

## 🔗 Quick Links

The dashboard includes quick links to:
- **API Health Check**: `http://localhost:8000/health`
- **Prometheus Metrics**: `http://localhost:8000/metrics`
- **Prometheus Dashboard**: `http://localhost:9090`
- **Grafana Dashboard**: `http://localhost:3000`

## 📱 Responsive Design

The dashboard is fully responsive and works on:
- Desktop computers
- Tablets
- Mobile phones

## 🛠️ Technical Details

- **React 18**: Modern React with hooks
- **Axios**: HTTP client for API calls
- **CSS Grid & Flexbox**: Responsive layout
- **Modern CSS**: Clean, professional styling

## 🔐 Authentication Note

Currently, the dashboard shows sample data because most API endpoints require authentication. To enable full functionality:

1. Create an API token
2. Add authentication headers to API calls
3. Implement login/logout functionality

## 📈 Data Overview

Based on your current database, you have:
- **10 Experiments** (mostly in DRAFT status)
- **10 Variants** across 5 experiments
- **9 User Assignments**
- **10 Events** (clicks, page views)
- **10 Users** (mix of active/inactive)
- **3 API Tokens**

## 🎯 Next Steps

1. **Add Authentication**: Implement API token-based authentication
2. **Real-time Updates**: Add WebSocket support for live data
3. **CRUD Operations**: Enable create, update, delete operations
4. **Advanced Filtering**: Add search and filter capabilities
5. **Charts & Graphs**: Integrate data visualization
6. **Export Features**: Add CSV/JSON export functionality
