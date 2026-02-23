import { lazy, Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ToastProvider } from './contexts/ToastContext'
import { ToastContainer } from './components/Toast'
import { RequireAuth } from './components/RequireAuth'
import './index.css'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const DashboardLayout = lazy(() => import('./layouts/DashboardLayout'))

const CoachDashboard = lazy(() => import('./pages/coach/CoachDashboard'))
const AthleteList = lazy(() => import('./pages/coach/AthleteList'))
const AthleteDetail = lazy(() => import('./pages/coach/AthleteDetail'))
const Interventions = lazy(() => import('./pages/coach/Interventions'))
const Analytics = lazy(() => import('./pages/coach/Analytics'))

const AthleteDashboard = lazy(() => import('./pages/athlete/AthleteDashboard'))
const CheckinPage = lazy(() => import('./pages/athlete/CheckinPage'))
const TrainingPage = lazy(() => import('./pages/athlete/TrainingPage'))
const PlanPage = lazy(() => import('./pages/athlete/PlanPage'))
const EventsPage = lazy(() => import('./pages/athlete/EventsPage'))

function Loading() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
    </div>
  )
}

function RootRedirect() {
  const { auth } = useAuth()
  if (!auth) return <Navigate to="/login" replace />
  return <Navigate to={auth.role === 'coach' ? '/coach' : '/athlete'} replace />
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/" element={<RootRedirect />} />

              <Route
                path="/coach"
                element={
                  <RequireAuth role="coach">
                    <DashboardLayout />
                  </RequireAuth>
                }
              >
                <Route index element={<CoachDashboard />} />
                <Route path="athletes" element={<AthleteList />} />
                <Route path="athletes/:id" element={<AthleteDetail />} />
                <Route path="interventions" element={<Interventions />} />
                <Route path="analytics" element={<Analytics />} />
              </Route>

              <Route
                path="/athlete"
                element={
                  <RequireAuth role="client">
                    <DashboardLayout />
                  </RequireAuth>
                }
              >
                <Route index element={<AthleteDashboard />} />
                <Route path="checkin" element={<CheckinPage />} />
                <Route path="training" element={<TrainingPage />} />
                <Route path="plan" element={<PlanPage />} />
                <Route path="events" element={<EventsPage />} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
          <ToastContainer />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
