import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'

export default function ProtectedRoute({ children, adminOnly = false }) {
  const location = useLocation()
  const { isAuthenticated, isAdmin } = useAuthStore()

  if (!isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  if (adminOnly && !isAdmin()) {
    return <Navigate to="/library" replace />
  }
  return <>{children}</>
}
