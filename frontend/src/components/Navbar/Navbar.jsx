import { NavLink, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Search, Library, Clock, Upload, LogOut, LogIn, UserPlus } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import './Navbar.css'

const NAV_LINKS = [
  { to: '/search',  label: 'Search',  icon: Search },
  { to: '/library', label: 'Library', icon: Library },
  { to: '/history', label: 'History', icon: Clock },
  { to: '/upload',  label: 'Upload',  icon: Upload },
]

export default function Navbar() {
  const { user, isAuthenticated, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="navbar" role="banner">
      <nav className="navbar-inner container" aria-label="Main navigation">
        <NavLink to="/" className="navbar-logo" aria-label="MEGA home">
          <motion.span
            className="navbar-logo-mark"
            aria-hidden="true"
            whileHover={{ rotate: [0, -8, 8, 0], scale: 1.1 }}
            transition={{ duration: 0.4 }}
          >M</motion.span>
          <span className="navbar-logo-text">MEGA</span>
        </NavLink>

        <div className="navbar-links" role="list">
          {isAuthenticated() && NAV_LINKS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              role="listitem"
              className={({ isActive }) => `navbar-link${isActive ? ' is-active' : ''}`}
            >
              {({ isActive }) => (
                <motion.span
                  className="navbar-link-inner"
                  whileHover={{ y: -1 }}
                  transition={{ duration: 0.15 }}
                >
                  <Icon size={15} aria-hidden="true" />
                  {label}
                  {isActive && (
                    <motion.span
                      className="navbar-active-bar"
                      layoutId="navbar-indicator"
                      transition={{ type: 'spring', stiffness: 400, damping: 35 }}
                    />
                  )}
                </motion.span>
              )}
            </NavLink>
          ))}
        </div>

        <div className="navbar-end">
          {isAuthenticated() ? (
            <>
              <span className="navbar-username" aria-hidden="true">{user?.name?.split(' ')[0]}</span>
              <motion.button
                id="navbar-logout-btn"
                className="btn btn-ghost btn-sm navbar-logout"
                onClick={handleLogout}
                aria-label="Log out"
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.96 }}
              >
                <LogOut size={14} style={{ marginRight: 4 }} />
                Sign out
              </motion.button>
            </>
          ) : (
            <>
              <NavLink to="/login" id="navbar-login-link" className="btn btn-ghost btn-sm">
                <LogIn size={14} style={{ marginRight: 4 }} />
                Sign in
              </NavLink>
              <NavLink to="/register" id="navbar-register-link" className="btn btn-primary btn-sm">
                <UserPlus size={14} style={{ marginRight: 4 }} />
                Get started
              </NavLink>
            </>
          )}
        </div>
      </nav>
    </header>
  )
}
