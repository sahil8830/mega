import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import Navbar from './components/Navbar/Navbar'
import ProtectedRoute from './components/ProtectedRoute/ProtectedRoute'
import LoadingSpinner from './components/LoadingSpinner/LoadingSpinner'

const LandingPage  = lazy(() => import('./pages/LandingPage'))
const LoginPage    = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const LibraryPage  = lazy(() => import('./pages/LibraryPage'))
const UploadPage   = lazy(() => import('./pages/UploadPage'))
const SearchPage   = lazy(() => import('./pages/SearchPage'))
const ResultsPage  = lazy(() => import('./pages/ResultsPage'))
const HistoryPage  = lazy(() => import('./pages/HistoryPage'))

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Suspense fallback={<LoadingSpinner fullPage size="lg" label="Loading..." />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/library" element={<ProtectedRoute><LibraryPage /></ProtectedRoute>} />
          <Route path="/upload" element={<ProtectedRoute><UploadPage /></ProtectedRoute>} />
          <Route path="/search" element={<ProtectedRoute><SearchPage /></ProtectedRoute>} />
          <Route path="/results" element={<ProtectedRoute><ResultsPage /></ProtectedRoute>} />
          <Route path="/history" element={<ProtectedRoute><HistoryPage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
