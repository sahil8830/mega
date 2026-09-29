import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import './Navbar.css'

export default function Navbar() {
  const { user, isAuthenticated, isAdmin, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="navbar" role="banner">
      <nav className="navbar-inner container" aria-label="Main navigation">
        <NavLink to="/" className="navbar-logo" aria-label="MEGA home">
          <span className="navbar-logo-mark" aria-hidden="true">M</span>
          <span className="navbar-logo-text">MEGA</span>
        </NavLink>

        <div className="navbar-links" role="list">
          {isAuthenticated() && (
            <>
              <NavLink to="/search"  className={({ isActive }) => `navbar-link${isActive ? ' is-active' : ''}`} role="listitem">Search</NavLink>
              <NavLink to="/library" className={({ isActive }) => `navbar-link${isActive ? ' is-active' : ''}`} role="listitem">Library</NavLink>
              <NavLink to="/upload"  className={({ isActive }) => `navbar-link${isActive ? ' is-active' : ''}`} role="listitem">Upload</NavLink>
            </>
          )}
        </div>

        <div className="navbar-end">
          {isAuthenticated() ? (
            <>
              <span className="navbar-username" aria-hidden="true">{user?.name?.split(' ')[0]}</span>
              <button id="navbar-logout-btn" className="btn btn-ghost btn-sm" onClick={handleLogout} aria-label="Log out">
                Sign out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" id="navbar-login-link" className="btn btn-ghost btn-sm">Sign in</NavLink>
              <NavLink to="/register" id="navbar-register-link" className="btn btn-primary btn-sm">Get started</NavLink>
            </>
          )}
        </div>
      </nav>
    </header>
  )
}
