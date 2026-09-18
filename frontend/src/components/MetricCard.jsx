import Icon from './Icon'

export default function MetricCard({ label, value, detail, icon, tone }) {
  return (
    <article className="metric-card">
      <div className={`metric-icon metric-icon--${tone}`}><Icon name={icon} /></div>
      <div>
        <p>{label}</p>
        <h2>{value}</h2>
        <span>{detail}</span>
      </div>
    </article>
  )
}
