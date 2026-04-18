// ==============================================================================
// File: frontend/src/pages/HomePage.js
// Purpose: Landing page with hero section, feature cards, and CTA.
// ==============================================================================

import React from 'react';
import { Link } from 'react-router-dom';
import {
  Brain, Zap, Image, Cpu, Database, BarChart2,
  ArrowRight, Upload, Star
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const HomePage = () => {
  const { user } = useAuth();

  const features = [
    {
      icon: <Brain size={32} />,
      title: "AI-Powered Analysis",
      description: "Our backend now uses the Gemini API to provide deep, contextual insights and recommendations for your data."
    },
    {
      icon: <Zap size={32} />,
      title: "Lightning Fast Processing",
      description: "Process datasets of any size in seconds. Our optimized FastAPI backend and Redis cache handle millions of rows."
    },
    {
      icon: <Image size={32} />,
      title: "Unified Platform",
      description: "The only tool you need. Preprocess both tabular CSV data and complex image datasets in one seamless workflow."
    },
    {
      icon: <Cpu size={32} />,
      title: "Smart Automation",
      description: "Intelligent automation reduces manual work, allowing you to focus on insights rather than data preparation."
    },
    {
      icon: <Database size={32} />,
      title: "Robust Data Handling",
      description: "Support for CSV, Excel, and ZIP (for images). We handle data ingestion and storage reliably with SQLAlchemy."
    },
    {
      icon: <BarChart2 size={32} />,
      title: "Before vs. After",
      description: "Our new analysis dashboard with Recharts provides a clear, visual comparison of your data quality before and after cleaning."
    }
  ];

  return (
    <div className="home-page">
      <section className="hero-section">
        <div className="app-container">
          <div className="hero-container">
            <div className="hero-content">
              <div className="hero-badge">
                <Star size={16} />
                Powered by Gemini & Scikit-learn
              </div>
              
              <h1 className="hero-title">
                Clean Your Data with{' '}
                <span className="hero-title-gradient">AI Intelligence</span>
              </h1>
              
              <p className="hero-description">
                DataSpark revolutionizes data cleaning with intelligent automation. Upload your messy datasets and watch our AI transform them into analysis-ready, high-quality data in minutes, not hours.
              </p>
              
              <div className="hero-buttons">
                <Link to={user ? "/dashboard" : "/register"} className="hero-btn-primary">
                  {user ? "Go to Dashboard" : "Start Free Trial"}
                  <ArrowRight size={20} />
                </Link>
                <Link to="/upload" className="hero-btn-secondary">
                  <Upload size={20} />
                  Try Demo
                </Link>
              </div>
              
              <div className="hero-stats">
                <div className="hero-stat">
                  <div className="hero-stat-number">10M+</div>
                  <div className="hero-stat-label">Rows Cleaned</div>
                </div>
                <div className="hero-stat">
                  <div className="hero-stat-number">99.9%</div>
                  <div className="hero-stat-label">Accuracy Rate</div>
                </div>
                <div className="hero-stat">
                  <div className="hero-stat-number">5 Min</div>
                  <div className="hero-stat-label">Avg Process Time</div>
                </div>
                <div className="hero-stat">
                  <div className="hero-stat-number">24/7</div>
                  <div className="hero-stat-label">Support</div>
                </div>
              </div>
            </div>
            
            <div className="hero-visual">
              <div className="floating-dashboard">
                <div className="dashboard-header-preview">
                  <div className="preview-dots">
                    <div className="dot red"></div>
                    <div className="dot yellow"></div>
                    <div className="dot green"></div>
                  </div>
                  <div className="preview-title">Data Cleaning Dashboard</div>
                </div>
                <div className="dashboard-content-preview">
                  <div className="preview-chart">
                    <div className="chart-bars">
                      <div className="bar" style={{height: '60%', '--height': '60%'}}></div>
                      <div className="bar" style={{height: '80%', '--height': '80%'}}></div>
                      <div className="bar" style={{height: '100%', '--height': '100%'}}></div>
                      <div className="bar" style={{height: '45%', '--height': '45%'}}></div>
                      <div className="bar" style={{height: '75%', '--height': '75%'}}></div>
                    </div>
                  </div>
                  <div className="preview-metrics">
                    <div className="metric">
                      <div className="metric-value">95%</div>
                      <div className="metric-label">Clean Rate</div>
                    </div>
                    <div className="metric">
                      <div className="metric-value">1.2M</div>
                      <div className="metric-label">Rows</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="features-section">
        <div className="container">
          <div className="section-header">
            <h2 className="section-title">Why Choose DataSpark?</h2>
            <p className="section-subtitle">
              Cutting-edge technology meets intuitive design to deliver unparalleled data cleaning capabilities
            </p>
          </div>
          
          <div className="features-grid">
            {features.map((feature, index) => (
              <div key={index} className="feature-card">
                <div className="feature-icon">
                  {feature.icon}
                </div>
                <h3 className="feature-title">{feature.title}</h3>
                <p className="feature-description">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="cta-section">
        <div className="container">
          <div className="cta-content">
            <h2 className="cta-title">Ready to Transform Your Data?</h2>
            <p className="cta-description">
              Join thousands of data professionals who trust DataSpark for their critical data cleaning workflows.
            </p>
            <Link to={user ? "/dashboard" : "/register"} className="cta-button">
              <ArrowRight size={20} />
              {user ? "Go to Dashboard" : "Start Your Free Trial"}
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
