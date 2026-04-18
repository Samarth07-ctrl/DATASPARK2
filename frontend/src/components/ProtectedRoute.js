// ==============================================================================
// File: frontend/src/components/ProtectedRoute.js
// Purpose: Route guard HOC — redirects unauthenticated users to /login.
// Why: Separating this from the router makes it reusable and keeps App.js
//      focused solely on route definitions.
// ==============================================================================

import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
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
        <h2 className="loading-title">Loading...</h2>
        <p className="loading-subtitle">Please wait while we verify your session</p>
      </div>
    );
  }

  return user ? children : <Navigate to="/login" replace />;
};

export default ProtectedRoute;
