import Icon from './Icon'

export default function FileField({ id, label, accept, onChange, fileNames = [], multiple = false, helperText, required = false, error }) {
  const selectedText = fileNames.length ? fileNames.join(', ') : 'Choose a file'
  return (
    <div className="field field--file">
      <label htmlFor={id}>{label} {required && <b>*</b>}</label>
      <label className="file-picker" htmlFor={id}>
        <Icon name="upload" size={19} />
        <span>{selectedText}</span>
        <small>{fileNames.length ? `${fileNames.length} file${fileNames.length > 1 ? 's' : ''} selected` : helperText}</small>
      </label>
      <input id={id} name={id} type="file" accept={accept} multiple={multiple} onChange={onChange} />
      {error && <small className="field-error">{error}</small>}
    </div>
  )
}
