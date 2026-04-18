// ==============================================================================
// File: frontend/src/pages/Dashboard.js
// Purpose: User dashboard — shows analytics stats + recent upload history.
// ==============================================================================

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  FileText, Zap, Upload, CheckCircle, TrendingUp
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../config/api';

const Dashboard = () => {
  const { user } = useAuth();
  const [uploadHistory, setUploadHistory] = useState([]);
  const [analytics, setAnalytics] = useState({});
  const [loading, setLoading] = useState(true);
  const [fetchingAnalysis, setFetchingAnalysis] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchDashboardData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchDashboardData = async () => {
    try {
      const token = localStorage.getItem('session_token');
      
      const historyResponse = await fetch(`${API_URL}/history`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (historyResponse.ok) {
        const historyData = await historyResponse.json();
        setUploadHistory(historyData.uploads || []);
      }

      const analyticsResponse = await fetch(`${API_URL}/analytics`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (analyticsResponse.ok) {
        const analyticsData = await analyticsResponse.json();
        setAnalytics(analyticsData);
      }
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleHistoryClick = async (upload) => {
    // Feature 4: Navigate directly to historical job visualization if a completed job exists
    if (upload.latest_job_id) {
      navigate(`/dashboard/analysis/${upload.latest_job_id}`);
      return;
    }

    // Fallback: load analysis data and navigate to upload page for re-analysis
    setFetchingAnalysis(true);
    try {
      const token = localStorage.getItem('session_token');
      const response = await fetch(`${API_URL}/analysis/${upload.id}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!response.ok) {
        throw new Error('Failed to fetch historical analysis data');
      }
      const data = await response.json();
      navigate('/upload', { state: { historicalAnalysis: data } });
    } catch (error) {
      console.error('Error loading historical analysis:', error);
      alert('Could not load historical analysis data. Please try again.');
    } finally {
      setFetchingAnalysis(false);
    }
  };

  if (loading || fetchingAnalysis) {
    return (
      <div className="loading-container centered-container">
        <div className="loading-animation">
          <div className="loading-spinner"></div>
          <div className="loading-dots">
            <div className="dot"></div>
            <div className="dot"></div>
            <div className="dot"></div>
          </div>
        </div>
        <h2 className="loading-title">Fetching your data insights...</h2>
        <p className="loading-subtitle">Loading dashboard</p>
      </div>
    );
  }

  const StatCard = ({ icon, title, value }) => (
    <div className="stat-card">
      <div className="stat-icon">
        {icon}
      </div>
      <div>
        <div className="stat-title">{title}</div>
        <div className="stat-value">{value}</div>
      </div>
    </div>
  );

  return (
    <div className="dashboard-page">
      <div className="app-container">
        <div className="dashboard-header">
          <div>
            <h1 className="dashboard-title">Welcome back, {user?.first_name || user?.username}!</h1>
            <p className="dashboard-subtitle">Here's your data cleaning activity</p>
          </div>
          <Link to="/upload" className="dashboard-upload-btn">
            <Upload size={20} />
            Upload New File
          </Link>
        </div>

        <div className="stats-grid">
          <StatCard
            icon={<FileText size={24} />}
            title="Total Uploads"
            value={analytics.total_uploads || 0}
          />
          <StatCard
            icon={<TrendingUp size={24} />}
            title="Success Rate"
            value={`${analytics.success_rate || 100}%`}
          />
          <StatCard
            icon={<Zap size={24} />}
            title="Processing Jobs"
            value={analytics.total_processing_jobs || 0}
          />
          <StatCard
            icon={<CheckCircle size={24} />}
            title="Data Quality"
            value={(analytics.success_rate || 100) > 95 ? "Excellent" : "Good"}
          />
        </div>

        <div className="dashboard-content">
          <div className="upload-history">
            <h2>Recent Uploads</h2>
            {uploadHistory.length > 0 ? (
              <div className="history-list">
                {uploadHistory.slice(0, 5).map((upload) => (
                  <div 
                    key={upload.id} 
                    className="history-item clickable"
                    onClick={() => handleHistoryClick(upload)}
                    style={{ cursor: 'pointer', transition: 'transform 0.2s, box-shadow 0.2s' }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.transform = 'translateY(-2px)';
                      e.currentTarget.style.boxShadow = '0 6px 12px rgba(0, 0, 0, 0.15)';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.transform = 'translateY(0)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    <div className="history-item-info">
                      <h3>{upload.filename}</h3>
                      <p>{upload.row_count || 'N/A'} rows, {upload.column_count || 'N/A'} columns</p>
                      <div className="history-item-date">
                        {new Date(upload.upload_timestamp).toLocaleString()}
                      </div>
                    </div>
                    <div className={`history-item-status ${upload.status}`}>
                      {upload.status}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-data">
                <FileText size={48} />
                <h3>No uploads yet</h3>
                <p>Start by uploading your first CSV file to begin data cleaning!</p>
                <Link to="/upload" className="dashboard-upload-btn">
                  <Upload size={20} />
                  Upload File
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
