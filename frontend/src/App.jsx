import AdminDashboard from './AdminDashboard'
import CustomerCasePortal from './CustomerCasePortal'

export default function App() {
  const { pathname } = window.location
  if (pathname === '/customer-portal' || pathname === '/customer-case') return <CustomerCasePortal />
  if (pathname === '/customer.portal') {
    window.history.replaceState({}, '', '/admin')
    return <AdminDashboard />
  }
  if (pathname.startsWith('/admin')) return <AdminDashboard />
  window.history.replaceState({}, '', '/admin')
  return <AdminDashboard />
}
