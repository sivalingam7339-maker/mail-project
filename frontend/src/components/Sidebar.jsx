import Icon from './Icon'

const navigation = [
  ['Dashboard', 'dashboard'],
  ['CRM', 'users'],
  ['Cases', 'briefcase'],
  ['Daily Sales Import', 'upload'],
  ['Daily Cases Import', 'upload'],
  ['Customer Portal', 'portal'],
]

export default function Sidebar({ open, onClose }) {
  return (
    <aside className={`sidebar ${open ? 'sidebar--open' : ''}`}>
      <div className="brand">
        <span className="brand-mark">D</span>
        <span><strong>Durafit</strong><b>91</b></span>
      </div>
      <p className="nav-label">Workspace</p>
      <nav>
        {navigation.map(([label, icon], index) => (
          <a className={`nav-link ${index === 0 ? 'nav-link--active' : ''}`} href={`#${label.toLowerCase().replaceAll(' ', '-')}`} key={label} onClick={onClose}>
            <Icon name={icon} /> <span>{label}</span>
          </a>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span className="status-dot" /> System status <strong>Ready</strong>
      </div>
    </aside>
  )
}
