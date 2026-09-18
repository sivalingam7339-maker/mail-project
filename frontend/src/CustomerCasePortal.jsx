import { useState } from 'react'
import Icon from './components/Icon'
import PortalBrand from './components/PortalBrand'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '')
const requiredFields = ['full_name', 'phone', 'order_id', 'customer_address', 'pincode', 'issue_category', 'description', 'invoice_image']
const MAX_INVOICE_SIZE = 20 * 1024 * 1024
const initialForm = { full_name: '', phone: '', alternate_number: '', order_id: '', customer_address: '', pincode: '', issue_category: '', description: '', invoice_image: null, attachments: [] }

export default function CustomerCasePortal() {
  const [form, setForm] = useState(initialForm)
  const [orderState, setOrderState] = useState('idle')
  const [verifiedOrder, setVerifiedOrder] = useState(null)
  const [errors, setErrors] = useState({})
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submissionError, setSubmissionError] = useState('')
  const [caseId, setCaseId] = useState('')
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())

  const update = (event) => {
    const { name, value, files } = event.target
    setForm((current) => ({ ...current, [name]: files ? (event.target.multiple ? Array.from(files) : files[0] || null) : value }))
    setSubmitted(false)
    setSubmissionError('')
    if (errors[name]) setErrors((current) => ({ ...current, [name]: '' }))
    if (name === 'order_id') { setOrderState('idle'); setVerifiedOrder(null) }
  }

  const verifyOrder = async () => {
    const orderId = form.order_id.trim()
    setSubmitted(false); setVerifiedOrder(null); setSubmissionError('')
    if (!orderId || !API_BASE_URL) { setOrderState('error'); return }
    setOrderState('loading')
    try {
      const response = await fetch(`${API_BASE_URL}/api/orders/${encodeURIComponent(orderId)}`)
      if (response.ok) { setVerifiedOrder(await response.json()); setOrderState('found') }
      else if (response.status === 404) { setSubmissionError(''); setOrderState('not-found') }
      else setOrderState('error')
    } catch { setOrderState('error') }
  }

  const submit = async (event) => {
    event.preventDefault()
    const nextErrors = requiredFields.reduce((result, field) => {
      if (field === 'invoice_image' ? !form[field] : !String(form[field]).trim()) result[field] = 'This field is required.'
      return result
    }, {})
    if (form.invoice_image?.size > MAX_INVOICE_SIZE) nextErrors.invoice_image = 'Invoice image must be 20 MB or smaller.'
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length !== 0 || submitting || !API_BASE_URL) {
      if (!API_BASE_URL) setSubmissionError('The submission service is not configured. Please try again later.')
      return
    }
    setSubmitting(true)
    setSubmissionError('')
    try {
      const payload = new FormData()
      payload.append('idempotency_key', idempotencyKey)
      ;['full_name', 'phone', 'alternate_number', 'order_id', 'customer_address', 'pincode', 'issue_category', 'description'].forEach((field) => payload.append(field, form[field]))
      payload.append('invoice_image', form.invoice_image)
      form.attachments.forEach((file) => payload.append('attachments', file))
      const response = await fetch(`${API_BASE_URL}/api/submissions`, { method: 'POST', body: payload })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.detail || 'We could not submit your request. Please try again.')
      setCaseId(result.case_id)
      setSubmitted(true)
      setIdempotencyKey(crypto.randomUUID())
    } catch (error) {
      setSubmissionError(error.message || 'We could not submit your request. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return <div className="support-page">
    <header className="support-topbar"><PortalBrand /><p>Durable Fitness. Stronger You.</p></header>
    <main className="support-content">
      <section className="support-hero"><div><p>We are here to help</p><h1>Customer Support Request</h1><span>Thank you for reaching out to Durafit. Please share the details below so our team can assist you as quickly as possible.</span></div><SupportIllustration /></section>
      <form className="support-form" onSubmit={submit} noValidate>
        <FormCard number="1" label="Full Name" helper="Enter your full name" required error={errors.full_name}><input name="full_name" value={form.full_name} onChange={update} placeholder="Your name" /></FormCard>
        <FormCard number="2" label="Phone Number" helper="Enter your 10-digit mobile number. An alternate number is optional." required error={errors.phone}><div className="support-number-grid"><input name="phone" aria-label="Phone Number" inputMode="tel" value={form.phone} onChange={update} placeholder="Primary number" /><input name="alternate_number" aria-label="Alternate Number" inputMode="tel" value={form.alternate_number} onChange={update} placeholder="Alternate number (optional)" /></div></FormCard>
        <FormCard number="3" label="Order ID / Tracking ID" helper="Enter your Order ID or Tracking ID" required error={errors.order_id}><div className="support-order-control"><input name="order_id" value={form.order_id} onChange={update} placeholder="e.g. OD123456789" /><button type="button" onClick={verifyOrder} disabled={orderState === 'loading'}>{orderState === 'loading' ? 'Checking…' : 'Verify'}</button></div>{orderState === 'not-found' && <p className="support-order-message support-order-message--info">Order ID not found in our current CRM records. You can still continue and submit your request.</p>}{orderState === 'error' && <p className="support-order-message support-order-message--error">We could not verify the Order ID right now. Please try again shortly.</p>}{orderState === 'found' && verifiedOrder && <VerifiedOrderDetails order={verifiedOrder} />}</FormCard>
        <FormCard number="4" label="Customer Address" helper="Enter your complete address" required error={errors.customer_address}><textarea name="customer_address" value={form.customer_address} onChange={update} rows="3" placeholder="House / flat number, street, area, city" /></FormCard>
        <FormCard number="5" label="Pincode" helper="Enter your area pincode" required error={errors.pincode}><input name="pincode" inputMode="numeric" value={form.pincode} onChange={update} placeholder="e.g. 600001" /></FormCard>
        <FormCard number="6" label="Enquiries" helper="Select the type of support you need" required error={errors.issue_category}><select name="issue_category" value={form.issue_category} onChange={update}><option value="" disabled>Choose an option</option><option>Installation support</option><option>Product issue</option><option>Missing or damaged part</option><option>Delivery or order support</option><option>Other</option></select></FormCard>
        <FormCard number="7" label="Detailed Description" helper="Please provide more details about the issue" required error={errors.description}><textarea name="description" value={form.description} onChange={update} rows="4" placeholder="Type your message here..." /></FormCard>
        <FormCard number="8" label="Invoice Image" helper="Upload your invoice image (maximum 20 MB)" required error={errors.invoice_image}><label className="support-file-picker"><Icon name="upload" size={22} /><span><b>Choose invoice image</b>{form.invoice_image ? ` ${form.invoice_image.name}` : ' No file chosen'}</span><input name="invoice_image" type="file" onChange={update} accept="image/jpeg,image/png,image/webp" /></label><small className="support-file-note">JPG, PNG or WEBP — maximum 20 MB</small></FormCard>
        <FormCard number="9" label="Attachments" helper="You can upload photos, videos or documents to help us understand the issue"><label className="support-file-picker"><Icon name="upload" size={22} /><span><b>Choose files</b>{form.attachments.length ? ` ${form.attachments.length} file${form.attachments.length > 1 ? 's' : ''} selected` : ' No file chosen'}</span><input name="attachments" type="file" multiple onChange={update} accept="image/jpeg,image/png,application/pdf,video/*" /></label><small className="support-file-note">You can upload up to 5 files (Max 10 MB each)</small></FormCard>
        <button className="support-submit" type="submit" disabled={submitting}>{submitting ? 'Submitting…' : 'Submit Request'}</button><p className="support-footer-note">Our support team will get back to you via email or phone at the earliest.</p>
        {submissionError && <p className="support-order-message support-order-message--error" role="alert">{submissionError}</p>}
        {submitted && <div className="success-message" role="status"><span>✓</span><div><strong>Your service request has been submitted successfully.</strong><p>Case ID: {caseId}</p><p>Thank you. Our team will review your request and contact you shortly.</p></div></div>}
      </form>
    </main>
  </div>
}

function FormCard({ number, label, helper, required = false, error, children }) { return <section className="support-field-card"><label><b>{number}. {label}</b>{required && <em> *</em>}</label><p>{helper}</p>{children}{error && <small className="field-error">{error}</small>}</section> }

function VerifiedOrderDetails({ order }) {
  const details = [['CX Name', order.cx_name], ['Account Name', order.account_name], ['Product Type', order.product_type], ['Product Name', order.product_name], ['Order Date', formatOrderDate(order.order_date)], ['Place of Supply', order.place_of_supply], ['Purchased Product', order.purchased_product], ['SKU', order.sku_new], ['Mobile Number', order.mobile_number], ['Customer Email', order.customer_email]].filter(([, value]) => value)
  return <section className="support-crm-details"><div className="support-crm-heading"><span>✓</span><strong>Order Verified</strong></div><dl>{details.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section>
}

function formatOrderDate(value) {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) return value || ''
  const [, year, month, day] = match
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return Number(month) >= 1 && Number(month) <= 12 ? `${day}-${months[Number(month) - 1]}-${year}` : value
}

function SupportIllustration() { return <div className="support-illustration" aria-hidden="true"><svg viewBox="0 0 160 160" fill="none"><circle cx="80" cy="80" r="54" fill="rgba(255,255,255,.48)" /><path d="M48 83a32 32 0 0 1 64 0" stroke="#247c5b" strokeWidth="7" strokeLinecap="round" /><path d="M48 83v20M112 83v20" stroke="#247c5b" strokeWidth="7" strokeLinecap="round" /><rect x="39" y="91" width="13" height="24" rx="6" fill="#247c5b" /><rect x="108" y="91" width="13" height="24" rx="6" fill="#247c5b" /><path d="M112 116c0 10-7 15-17 15h-5" stroke="#247c5b" strokeWidth="6" strokeLinecap="round" /></svg></div> }
