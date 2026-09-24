import { useEffect, useState } from 'react'
import PortalBrand from './components/PortalBrand'

const API = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '')
const routes = { dashboard: '/admin', crm: '/admin/crm-import', cases: '/admin/cases-import', submissions: '/admin/customer-submissions', customer: '/admin/customer-cases', history: '/admin/import-history' }
const request = (path, token, options = {}) => fetch(`${API}${path}`, { ...options, headers: { Authorization: `Bearer ${token}`, ...(options.headers || {}) } })
const date = (value) => { const m = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})T?(\d{2}):(\d{2})/); if (!m) return value || 'None'; const [, y, mo, d, h, mi] = m; const hour = Number(h); return `${d}-${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(mo)-1]}-${y} ${hour % 12 || 12}:${mi} ${hour >= 12 ? 'PM' : 'AM'}` }

export default function AdminDashboard() {
  const [token, setToken] = useState(sessionStorage.getItem('durafit_admin_token')); const [credentials, setCredentials] = useState({ username: '', password: '' })
  const [section, setSection] = useState(() => Object.entries(routes).find(([, path]) => path === window.location.pathname)?.[0] || 'dashboard')
  const [stats, setStats] = useState(null); const [history, setHistory] = useState([]); const [error, setError] = useState(''); const [loading, setLoading] = useState(false)
  const [importStates, setImportStates] = useState({ crm: { file: null, dry: null, result: null, busy: false, startedAt: null, now: 0, completedSeconds: null }, cases: { file: null, dry: null, result: null, busy: false, startedAt: null, now: 0, completedSeconds: null } })
  const [list, setList] = useState(null); const [search, setSearch] = useState(''); const [crm, setCrm] = useState('all'); const [caseStatus, setCaseStatus] = useState('all'); const [detail, setDetail] = useState(null)

  // Customer Submissions verification module state
  const [submissionList, setSubmissionList] = useState(null)
  const [subSearch, setSubSearch] = useState('')
  const [subCrm, setSubCrm] = useState('all')
  const [subCaseStatus, setSubCaseStatus] = useState('all')
  const [subStatus, setSubStatus] = useState('all')
  const [subDetail, setSubDetail] = useState(null)
  const [saveStatus, setSaveStatus] = useState('')
  const [moveMessage, setMoveMessage] = useState('')

  const load = async () => { setLoading(true); try { const [a, b] = await Promise.all([request('/api/admin/stats', token), request('/api/admin/import/history', token)]); if (a.status === 401) return logout(); if (!a.ok) throw Error(); setStats(await a.json()); if (b.ok) setHistory(await b.json()) } catch { setError('Unable to load dashboard statistics.') } finally { setLoading(false) } }
  const loadCases = async () => { const q = new URLSearchParams({ search, crm_status: crm, case_status: caseStatus }); const r = await request(`/api/admin/customer-cases?${q}`, token); if (r.ok) setList(await r.json()); else setError('Unable to load customer cases.') }
  const loadSubmissions = async () => { const q = new URLSearchParams({ search: subSearch, crm_status: subCrm, case_status: subCaseStatus, submission_status: subStatus }); const r = await request(`/api/admin/customer-submissions?${q}`, token); if (r.ok) setSubmissionList(await r.json()); else setError('Unable to load customer submissions.') }

  useEffect(() => { if (token) load() }, [token])
  useEffect(() => { if (token && section === 'customer') loadCases() }, [token, section])
  useEffect(() => { if (token && section === 'submissions') loadSubmissions() }, [token, section])

  useEffect(() => {
    const currentType = section === 'crm' ? 'crm' : 'cases'
    const currentImport = importStates[currentType]
    if (!currentImport.busy || !currentImport.startedAt) return undefined
    const updateNow = () => setImportStates(states => ({ ...states, [currentType]: { ...states[currentType], now: Date.now() } }))
    updateNow()
    const interval = window.setInterval(updateNow, 1000)
    return () => window.clearInterval(interval)
  }, [section, importStates])

  const login = async (event) => {
    event.preventDefault()
    setError('')
    if (!API) return setError('The admin service is not configured.')
    const body = new FormData()
    body.append('username', credentials.username)
    body.append('password', credentials.password)
    try {
      const response = await fetch(`${API}/api/admin/login`, { method: 'POST', body })
      const data = await response.json().catch(() => ({}))
      if (response.status === 401) return setError('Invalid username or password.')
      if (!response.ok) return setError('The admin service is unavailable. Please try again shortly.')
      sessionStorage.setItem('durafit_admin_token', data.token)
      setToken(data.token)
      window.history.replaceState({}, '', '/admin')
    } catch {
      setError('Cannot reach the admin service. Please ensure the backend is running.')
    }
  }

  const logout = async () => { try { if (token) await request('/api/admin/logout', token, { method: 'POST' }) } finally { sessionStorage.removeItem('durafit_admin_token'); setToken(null); window.history.replaceState({}, '', '/admin/login') } }
  const nav = (next) => { setSection(next); window.history.pushState({}, '', routes[next]); setError(''); setDetail(null); setSubDetail(null) }

  const upload = async (final) => {
    const type = section === 'crm' ? 'crm' : 'cases'; const currentImport = importStates[type]
    if (!currentImport.file) return setError('Choose an .xlsx file first.')
    const startedAt = Date.now()
    setImportStates(states => ({ ...states, [type]: { ...states[type], busy: true, startedAt, now: startedAt, completedSeconds: null } })); setError('')
    const body = new FormData(); body.append('file', currentImport.file)
    try {
      const r = await request(`/api/admin/import/${type}${final ? '' : '/dry-run'}`, token, { method: 'POST', body })
      const data = await r.json()
      if (!r.ok) throw Error(data.detail || 'Import failed')
      const completedSeconds = Math.max(1, Math.ceil((Date.now() - startedAt) / 1000))
      setImportStates(states => ({ ...states, [type]: { ...states[type], ...(final ? { result: data } : { dry: data }), completedSeconds } })); if (final) load()
    } catch (e) { setError(e.message) } finally { setImportStates(states => ({ ...states, [type]: { ...states[type], busy: false } })) }
  }

  const open = async (id) => { const r = await request(`/api/admin/customer-cases/${id}`, token); if (r.ok) setDetail(await r.json()) }
  const download = async (attachment) => { const r = await request(`/api/admin/customer-cases/${detail.submission_id}/attachments/${attachment.attachment_id}`, token); if (!r.ok) return setError('Attachment unavailable.'); const url = URL.createObjectURL(await r.blob()); const a = document.createElement('a'); a.href = url; a.download = attachment.original_filename; a.click(); URL.revokeObjectURL(url) }

  const openSubmission = async (id) => {
    setSaveStatus('')
    setMoveMessage('')
    const r = await request(`/api/admin/customer-submissions/${id}`, token)
    if (r.ok) setSubDetail(await r.json())
    else setError('Unable to load submission details.')
  }

  const saveSubmission = async (updatedFields) => {
    setSaveStatus('Saving changes...')
    setMoveMessage('')
    try {
      const r = await request(`/api/admin/customer-submissions/${subDetail.submission_id}`, token, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedFields),
      })
      const data = await r.json()
      if (!r.ok) throw Error(data.detail || 'Failed to save changes')
      setSubDetail(data)
      setSaveStatus('Changes saved successfully!')
      loadSubmissions()
    } catch (err) {
      setSaveStatus(`Save failed: ${err.message}`)
    }
  }

  const moveToCases = async () => {
    setMoveMessage('Processing Move to Cases action...')
    try {
      const r = await request(`/api/admin/customer-submissions/${subDetail.submission_id}/move-to-cases`, token, {
        method: 'POST',
      })
      const data = await r.json()
      if (!r.ok) throw Error(data.detail || 'Move to Cases failed')
      setMoveMessage(data.message || `Moved to Cases. Case ID: ${data.case_id}`)
      await openSubmission(subDetail.submission_id)
      loadSubmissions()
    } catch (err) {
      setMoveMessage(`Action failed: ${err.message}`)
    }
  }

  const downloadSubAttachment = async (attachment) => {
    const r = await request(`/api/admin/customer-submissions/${subDetail.submission_id}/attachments/${attachment.attachment_id}`, token)
    if (!r.ok) return setError('Attachment unavailable.')
    const url = URL.createObjectURL(await r.blob())
    const a = document.createElement('a')
    a.href = url
    a.download = attachment.original_filename
    a.click()
    URL.revokeObjectURL(url)
  }

  if (!token) return <main className="admin-login"><section><PortalBrand /><h1>Admin Login</h1><form onSubmit={login}><input placeholder="Username" onChange={e => setCredentials({ ...credentials, username: e.target.value })} /><input type="password" placeholder="Password" onChange={e => setCredentials({ ...credentials, password: e.target.value })} /><button>Login</button></form>{error && <p className="admin-error">{error}</p>}</section></main>

  const type = section === 'crm' ? 'crm' : 'cases'; const currentImport = importStates[type]; const displayType = type === 'crm' ? 'CRM' : 'Cases'
  const elapsedSeconds = currentImport.busy && currentImport.startedAt ? Math.floor((currentImport.now - currentImport.startedAt) / 1000) : 0
  const importStatus = currentImport.busy ? (elapsedSeconds < 50 ? `Working... ${50 - elapsedSeconds}s` : 'Working... Still processing...') : currentImport.completedSeconds ? `Completed in ${currentImport.completedSeconds}s` : ''

  return (
    <div className="admin-shell">
      <aside>
        <PortalBrand />
        <h2>Admin</h2>
        {[
          ['dashboard','Dashboard'],
          ['crm','CRM Import'],
          ['cases','Cases Import'],
          ['submissions','Customer Submissions'],
          ['customer','Customer Cases'],
          ['history','Import History']
        ].map(([id,label]) => (
          <button key={id} className={section === id ? 'active' : ''} onClick={() => nav(id)}>{label}</button>
        ))}
        <button className="logout" onClick={logout}>Logout</button>
      </aside>
      <main>
        <div className="admin-title">
          <div>
            <h1>Durafit91 Admin Dashboard</h1>
            <p>Live operational overview</p>
          </div>
          {section === 'dashboard' && <button onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh'}</button>}
        </div>
        {error && <p className="admin-error">{error}</p>}
        {section === 'dashboard' && <Dashboard stats={stats} loading={loading}/>}
        {(section === 'crm' || section === 'cases') && <Import type={displayType} file={currentImport.file} setFile={file => setImportStates(states => ({ ...states, [type]: { ...states[type], file } }))} dry={currentImport.dry} result={currentImport.result} busy={currentImport.busy} importStatus={importStatus} upload={upload}/>}
        {section === 'history' && <History rows={history}/>}
        {section === 'submissions' && (
          <CustomerSubmissions
            data={submissionList}
            search={subSearch}
            setSearch={setSubSearch}
            crm={subCrm}
            setCrm={setSubCrm}
            caseStatus={subCaseStatus}
            setCaseStatus={setSubCaseStatus}
            subStatus={subStatus}
            setSubStatus={setSubStatus}
            load={loadSubmissions}
            open={openSubmission}
          />
        )}
        {section === 'customer' && <CustomerCases data={list} search={search} setSearch={setSearch} crm={crm} setCrm={setCrm} caseStatus={caseStatus} setCaseStatus={setCaseStatus} load={loadCases} open={open}/>}
        {detail && <Detail value={detail} close={() => setDetail(null)} download={download}/>}
        {subDetail && (
          <CustomerSubmissionModal
            value={subDetail}
            close={() => setSubDetail(null)}
            onSave={saveSubmission}
            onMove={moveToCases}
            saveStatus={saveStatus}
            moveMessage={moveMessage}
            download={downloadSubAttachment}
          />
        )}
      </main>
    </div>
  )
}

function Dashboard({ stats, loading }) {
  if (loading && !stats) return <p>Loading dashboard statistics…</p>
  if (!stats) return null
  const caseRecords = stats.case_records ?? stats.cases_records
  const caseBreakdown = stats.case_status_breakdown
  const customerBreakdown = stats.customer_case_breakdown
  const crmBreakdown = stats.crm_status_breakdown
  if (!Array.isArray(caseBreakdown) || !customerBreakdown || !crmBreakdown || typeof caseRecords !== 'number') return <p className="admin-error">Dashboard statistics are incomplete. Refresh the page after the backend has been restarted.</p>
  return <><div className="admin-cards admin-kpis">{[['CRM Records',stats.crm_records,'crm'],['Cases Records',caseRecords,'cases'],['Customer Cases',stats.customer_cases,'customer']].map(([label,value,tone]) => <article className={`kpi-${tone}`} key={label}><span>{label}</span><b>{typeof value === 'number' ? value.toLocaleString() : value}</b></article>)}</div><div className="import-indicators"><ImportIndicator kind="CRM Import" value={date(stats.last_crm_import?.completed_at)} tone="crm"/><ImportIndicator kind="Cases Import" value={date(stats.last_cases_import?.completed_at)} tone="cases"/></div><section className="dashboard-chart combined-cases"><div className="combined-cases-header"><p>Live case workflow</p><b>{caseRecords.toLocaleString()} total cases</b></div><div className="dashboard-cases"><RankedBars data={caseBreakdown} total={caseRecords}/><TopCaseStatuses data={caseBreakdown} total={caseRecords}/></div></section><div className="dashboard-status"><Comparison title="Customer Cases" total={stats.customer_cases ?? 0} primary={{label:'Order ID Exists',value:customerBreakdown.order_id_exists ?? 0,tone:'success'}} secondary={{label:'Need to Create Case',value:customerBreakdown.need_to_create_case ?? 0,tone:'warning'}}/><Comparison title="CRM Order Verification" total={stats.customer_cases ?? 0} primary={{label:'Order ID Exists',value:crmBreakdown.order_id_exists ?? 0,tone:'info'}} secondary={{label:'Order ID Not Found',value:crmBreakdown.order_id_not_found ?? 0,tone:'danger'}}/></div></>
}
function RankedBars({ data, total }) { const max = Math.max(...data.map(item => item.count), 1); return <div className="case-pane ranked-bars"><div className="chart-heading"><div><h2>Cases by Status</h2></div><b>All statuses</b></div><div className="bar-list">{data.map((item, index) => <div className="bar-row" key={item.status}><div className="bar-label"><span>{item.status}</span><b>{item.count.toLocaleString()} <small>{total ? `${Math.round(item.count / total * 100)}%` : '0%'}</small></b></div><div className="bar-track"><i className={`bar-color-${index % 6}`} style={{width:`${item.count / max * 100}%`}}/></div></div>)}</div></div> }
function TopCaseStatuses({ data, total }) { const top = data.slice(0, 5); const max = Math.max(...top.map(item => item.count), 1); return <div className="case-pane top-case-statuses"><div className="chart-heading"><div><h2>Case Status Overview</h2></div><b>Top {top.length}</b></div><div className="top-bar-list">{top.map((item, index) => <div className="top-bar-row" key={item.status}><div><span>{item.status}</span><b>{item.count.toLocaleString()}</b></div><div className="top-bar-track"><i className={`bar-color-${index % 6}`} style={{width:`${item.count / max * 100}%`}}/></div><small>{total ? Math.round(item.count / total * 100) : 0}%</small></div>)}</div></div> }
function ImportIndicator({ kind, value, tone }) { const [day, time] = String(value || 'None').split(/ (?=\d)/); return <article className={`import-indicator ${tone}`}><div><span>{kind}</span><strong>{day}</strong><small>{time || 'No completed import'}</small></div></article> }
function Comparison({ title, total, primary, secondary, compact = false }) { const rows=[primary,secondary]; return <section className={`dashboard-chart comparison ${compact ? 'comparison-compact' : ''}`}><div className="chart-heading"><div><p>Live customer submissions</p><h2>{title}</h2></div><b>{total.toLocaleString()} total</b></div><div className="comparison-grid">{rows.map(row => <article key={row.label} className={row.tone}><span>{row.label}</span><strong>{row.value.toLocaleString()}</strong><div><i style={{width:`${total ? row.value / total * 100 : 0}%`}}/></div><small>{total ? Math.round(row.value / total * 100) : 0}% of submissions</small></article>)}</div></section> }
function Import({type,file,setFile,dry,result,busy,importStatus,upload}) { return <section className="admin-import"><h2>{type} Import</h2><p>Run a dry run first. It validates and previews the workbook without writing any records.</p><input type="file" accept=".xlsx" onChange={e => setFile(e.target.files[0])}/><button disabled={busy} onClick={() => upload(false)}>{busy ? importStatus : 'Run Dry Run'}</button>{importStatus && <p role="status">{importStatus}</p>}{dry && <><p><b>Source sheet:</b> {dry.source_sheet || 'Single source sheet'}</p><div className="admin-result"><span>Total: {dry.total_rows}</span><span>New: {dry.new_records}</span><span>Skipped: {dry.skipped_records}</span><span>Failed: {dry.failed_rows}</span></div><p>{Object.entries(dry.missing_fields).map(([k,v]) => `${k} (${v})`).join(', ') || 'No missing fields detected.'}</p><Preview data={dry.preview}/><button disabled={busy} onClick={() => upload(true)}>{busy ? importStatus : `Import ${type}`}</button></>}{result && <p>Inserted: {result.inserted_rows}; skipped: {result.skipped_rows}; failed: {result.failed_rows}</p>}</section> }
const Preview = ({data}) => !data?.length ? <p>No new records to preview.</p> : <div className="admin-history"><h3>Records to be Imported</h3><table><thead><tr>{Object.keys(data[0]).map(k=><th key={k}>{k}</th>)}</tr></thead><tbody>{data.map((r,i)=><tr key={i}>{Object.keys(data[0]).map(k=><td key={k}>{r[k]||'—'}</td>)}</tr>)}</tbody></table></div>
const History = ({rows}) => <section className="admin-history"><h2>Import History</h2><table><thead><tr><th>Date</th><th>Type</th><th>File</th><th>Total</th><th>Inserted</th><th>Skipped</th><th>Failed</th></tr></thead><tbody>{rows.map(r=><tr key={r.import_id}><td>{date(r.completed_at||r.started_at)}</td><td>{r.import_type}</td><td>{r.original_filename}</td><td>{r.total_rows}</td><td>{r.inserted_rows}</td><td>{r.skipped_rows}</td><td>{r.failed_rows}</td></tr>)}</tbody></table></section>

function CustomerSubmissions({ data, search, setSearch, crm, setCrm, caseStatus, setCaseStatus, subStatus, setSubStatus, load, open }) {
  return (
    <section className="admin-history">
      <h2>Customer Submissions (Verification Area)</h2>
      <p style={{ color: '#687b76', margin: '4px 0 16px' }}>
        Review customer-entered details, inspect CRM matches and case records, edit submissions, and verify before moving to Cases.
      </p>
      <div className="admin-filters">
        <input value={search} placeholder="Order ID, customer or phone" onChange={e => setSearch(e.target.value)} />
        <select value={crm} onChange={e => setCrm(e.target.value)}>
          <option value="all">All CRM statuses</option>
          <option>Order ID Exists</option>
          <option>Order ID Not Found</option>
        </select>
        <select value={caseStatus} onChange={e => setCaseStatus(e.target.value)}>
          <option value="all">All case statuses</option>
          <option>Need to Create Case</option>
          {data?.case_status_options?.map(x => <option key={x}>{x}</option>)}
        </select>
        <select value={subStatus} onChange={e => setSubStatus(e.target.value)}>
          <option value="all">All submission statuses</option>
          <option value="pending_verification">Pending Verification</option>
          <option value="moved_to_cases">Moved to Cases</option>
        </select>
        <button onClick={load}>Filter</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Submission Date</th>
            <th>Order ID</th>
            <th>Customer Name</th>
            <th>Phone</th>
            <th>Product / CRM Product</th>
            <th>Enquiry</th>
            <th>CRM Status</th>
            <th>Existing Case Status</th>
            <th>Submission Status</th>
          </tr>
        </thead>
        <tbody>
          {data?.items?.map(r => (
            <tr className="click-row" key={r.submission_id} onClick={() => open(r.submission_id)}>
              <td>{date(r.created_at)}</td>
              <td><strong>{r.order_id}</strong></td>
              <td>{r.full_name}</td>
              <td>{r.phone_number}</td>
              <td>{r.crm_product_name || r.crm_purchased_product || 'Not Available'}</td>
              <td>{r.issue_category}</td>
              <td><span className={`status-badge ${r.crm_status === 'Order ID Exists' ? 'badge-crm-ok' : 'badge-crm-missing'}`}>{r.crm_status}</span></td>
              <td>{r.case_statuses.map((x, i) => <span className="status-badge" key={i}>{x}</span>)}</td>
              <td>
                <span className={`status-badge ${r.submission_status_display === 'Moved to Cases' ? 'badge-moved' : 'badge-pending'}`}>
                  {r.submission_status_display}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>{data?.total || 0} customer submissions</p>
    </section>
  )
}

function CustomerSubmissionModal({ value, close, onSave, onMove, saveStatus, moveMessage, download }) {
  const crm = value.crm || {}
  const [formData, setFormData] = useState({
    full_name: value.full_name || '',
    phone_number: value.phone_number || '',
    alternate_number: value.alternate_number || '',
    order_id: value.order_id || '',
    customer_address: value.customer_address || '',
    pincode: value.pincode || '',
    issue_category: value.issue_category || '',
    detailed_description: value.detailed_description || '',
  })

  const handleChange = (field, val) => {
    setFormData(prev => ({ ...prev, [field]: val }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onSave(formData)
  }

  const isMoved = value.submission_status === 'moved_to_cases' || !!value.case_id

  return (
    <section className="admin-detail submission-modal">
      <div className="modal-header">
        <div>
          <h2>Customer Submission Verification</h2>
          <p className="modal-subtext">
            Submission ID: {value.submission_id} • Submitted: {date(value.created_at)}
            {value.case_id && <span className="case-id-badge"> • Case ID: <strong>{value.case_id}</strong></span>}
          </p>
        </div>
        <div className="modal-header-actions">
          <span className={`status-badge ${isMoved ? 'badge-moved' : 'badge-pending'}`}>
            {isMoved ? 'Moved to Cases' : 'Pending Verification'}
          </span>
          <button type="button" className="btn-close" onClick={close}>Close</button>
        </div>
      </div>

      {saveStatus && (
        <div className={`modal-alert ${saveStatus.includes('failed') || saveStatus.includes('Error') ? 'alert-danger' : 'alert-success'}`}>
          {saveStatus}
        </div>
      )}

      {moveMessage && (
        <div className="modal-alert alert-info">
          {moveMessage}
        </div>
      )}

      <div className="modal-two-col">
        {/* Left column: Editable Customer-Entered Fields */}
        <form onSubmit={handleSubmit} className="admin-edit-card">
          <div className="card-header">
            <h3>Customer Form Details (Editable)</h3>
            <span className="card-badge">Editable</span>
          </div>

          <div className="form-row-2">
            <div className="admin-field">
              <label>Full Name</label>
              <input value={formData.full_name} onChange={e => handleChange('full_name', e.target.value)} required />
            </div>
            <div className="admin-field">
              <label>Order ID</label>
              <input value={formData.order_id} onChange={e => handleChange('order_id', e.target.value)} required />
            </div>
          </div>

          <div className="form-row-2">
            <div className="admin-field">
              <label>Phone Number</label>
              <input value={formData.phone_number} onChange={e => handleChange('phone_number', e.target.value)} required />
            </div>
            <div className="admin-field">
              <label>Alternate Number</label>
              <input value={formData.alternate_number} onChange={e => handleChange('alternate_number', e.target.value)} />
            </div>
          </div>

          <div className="form-row-2">
            <div className="admin-field">
              <label>Address</label>
              <input value={formData.customer_address} onChange={e => handleChange('customer_address', e.target.value)} required />
            </div>
            <div className="admin-field">
              <label>Pincode</label>
              <input value={formData.pincode} onChange={e => handleChange('pincode', e.target.value)} required />
            </div>
          </div>

          <div className="admin-field">
            <label>Issue Category</label>
            <input value={formData.issue_category} onChange={e => handleChange('issue_category', e.target.value)} required />
          </div>

          <div className="admin-field">
            <label>Detailed Description</label>
            <textarea rows={3} value={formData.detailed_description} onChange={e => handleChange('detailed_description', e.target.value)} required />
          </div>

          <div className="modal-action-bar">
            <button type="submit" className="btn-save">Save Changes</button>
            {isMoved ? (
              <button type="button" className="btn-move btn-moved" disabled title="This submission has already been moved to cases.">
                ✓ Moved to Cases {value.case_id ? `(${value.case_id})` : ''}
              </button>
            ) : (
              <button type="button" className="btn-move" onClick={onMove}>Move to Cases</button>
            )}
          </div>
        </form>

        {/* Right column: CRM matched details & Case info */}
        <div className="admin-side-info">
          {/* Matched CRM Information */}
          <div className="admin-info-card">
            <div className="card-header">
              <h3>Matched CRM Order Details</h3>
              <span className={`status-badge ${value.crm_status === 'Order ID Exists' ? 'badge-crm-ok' : 'badge-crm-missing'}`}>{value.crm_status}</span>
            </div>
            {value.crm ? (
              <div className="info-kv-grid">
                <div><span>CX Name</span><strong>{crm.cx_name || '—'}</strong></div>
                <div><span>Account Name</span><strong>{crm.account_name || '—'}</strong></div>
                <div><span>Product Type</span><strong>{crm.product_type || '—'}</strong></div>
                <div><span>Product Name</span><strong>{crm.product_name || value.crm_product_name || '—'}</strong></div>
                <div><span>Order Date</span><strong>{crm.order_date || '—'}</strong></div>
                <div><span>Place of Supply</span><strong>{crm.place_of_supply || '—'}</strong></div>
                <div><span>Purchased Product</span><strong>{crm.purchased_product || value.crm_purchased_product || '—'}</strong></div>
                <div><span>SKU</span><strong>{crm.sku_new || value.crm_sku_new || '—'}</strong></div>
              </div>
            ) : (
              <p className="not-found-note">No matching CRM record found for Order ID "{formData.order_id}".</p>
            )}
          </div>

          {/* Existing Case Information */}
          <div className="admin-info-card">
            <div className="card-header">
              <h3>Existing Cases in Database</h3>
              <span className="card-badge">Durafit Cases</span>
            </div>
            {value.case_id && (
              <div className="portal-case-callout">
                <span>Created Case ID:</span>
                <strong>{value.case_id}</strong>
              </div>
            )}
            <div className="case-status-tags">
              {value.case_statuses?.map((st, i) => (
                <span key={i} className="status-badge case-pill">{st}</span>
              ))}
            </div>
          </div>

          {/* Invoice & Attachments */}
          <div className="admin-info-card">
            <div className="card-header">
              <h3>Invoice & Attachments</h3>
              <span className="card-badge">{value.attachments?.length || 0} files</span>
            </div>
            <div className="attachment-list">
              {value.attachments?.length ? value.attachments.map(a => (
                <button key={a.attachment_id} type="button" className="attachment-chip" onClick={() => download(a)}>
                  📎 {a.attachment_kind}: {a.original_filename}
                </button>
              )) : <p className="not-found-note">No attachments provided.</p>}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function CustomerCases({data,search,setSearch,crm,setCrm,caseStatus,setCaseStatus,load,open}) { return <section className="admin-history"><h2>Customer Cases</h2><div className="admin-filters"><input value={search} placeholder="Order ID, customer or phone" onChange={e=>setSearch(e.target.value)}/><select value={crm} onChange={e=>setCrm(e.target.value)}><option value="all">All CRM statuses</option><option>Order ID Exists</option><option>Order ID Not Found</option></select><select value={caseStatus} onChange={e=>setCaseStatus(e.target.value)}><option value="all">All case statuses</option><option>Need to Create Case</option>{data?.case_status_options?.map(x=><option key={x}>{x}</option>)}</select><button onClick={load}>Search</button></div><table><thead><tr><th>Date</th><th>Order ID</th><th>Customer</th><th>Phone</th><th>Product</th><th>Enquiries</th><th>CRM Status</th><th>Case Status</th></tr></thead><tbody>{data?.items?.map(r=><tr className="click-row" key={r.submission_id} onClick={()=>open(r.submission_id)}><td>{date(r.created_at)}</td><td>{r.order_id}</td><td>{r.full_name}</td><td>{r.phone_number}</td><td>{r.crm_product_name || 'Not Available'}</td><td>{r.issue_category}</td><td>{r.crm_status}</td><td>{r.case_statuses.map((x,i)=><span className="status-badge" key={i}>{x}</span>)}</td></tr>)}</tbody></table><p>{data?.total || 0} submissions</p></section> }
function Detail({value,close,download}) { const crm=value.crm||{}; const rows=[['Customer Name',value.full_name],['Phone',value.phone_number],['Alternate Number',value.alternate_number],['Order ID',value.order_id],['Address',value.customer_address],['Pincode',value.pincode],['Enquiries',value.issue_category],['Description',value.detailed_description],['Submission Date',date(value.created_at)],['CRM Status',value.crm_status],['Case Status',value.case_statuses?.join(', ')],['CX Name',crm.cx_name],['Account Name',crm.account_name],['Product Type',crm.product_type],['Product Name',crm.product_name||value.crm_product_name],['Order Date',crm.order_date],['Place of Supply',crm.place_of_supply],['Purchased Product',crm.purchased_product||value.crm_purchased_product],['SKU',crm.sku_new||value.crm_sku_new]]; return <section className="admin-detail"><button onClick={close}>Close</button><h2>Customer Submission</h2>{rows.filter(([,v])=>v).map(([a,b])=><p key={a}><b>{a}:</b> {b}</p>)}<h3>Attachments</h3>{value.attachments.map(a=><button key={a.attachment_id} onClick={()=>download(a)}>{a.attachment_kind}: {a.original_filename}</button>)}</section> }

