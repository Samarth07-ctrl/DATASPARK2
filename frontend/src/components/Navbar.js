// ==============================================================================
// File: frontend/src/components/Navbar.js
// Purpose: Global navigation bar — renders different links based on auth state.
// ==============================================================================

import React from 'react';
import { Link } from 'react-router-dom';
import {
  Brain, Home, Upload, Image, User, LogOut, LogIn, UserPlus
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Navbar = () => {
  const { user, logout } = useAuth();

  return (
    <nav className="navbar">
      <div className="nav-container">
        <Link to="/" className="nav-logo">
          <Brain className="nav-logo-icon" size={28} />
          DataSpark
        </Link>

        <div className="nav-menu">
          {user ? (
            <>
              <Link to="/dashboard" className="nav-link">
                <Home size={18} />
                Dashboard
              </Link>
              <Link to="/upload" className="nav-link">
                <Upload size={18} />
                Upload CSV
              </Link>
              <Link to="/image-processing" className="nav-link">
                <Image size={18} />
                Image Processing
              </Link>
              <div className="nav-user-menu">
                <div className="nav-user-info">
                  <User size={18} />
                  {user.username}
                </div>
                <button onClick={logout} className="nav-logout-btn">
                  <LogOut size={16} />
                  Logout
                </button>
              </div>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link">
                <LogIn size={18} />
                Login
              </Link>
              <Link to="/register" className="nav-register">
                <UserPlus size={18} />
                Get Started
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
