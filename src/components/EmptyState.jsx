import { FileIcon } from './Icons.jsx'

export default function EmptyState({ onGoUpload, title = 'No candidates yet', text = 'Upload resumes to see ranked scores and contacts here.' }) {
  return (
    <div className="card empty">
      <FileIcon size={48} />
      <h3>{title}</h3>
      <p className="muted">{text}</p>
      <button className="btn btn-primary" onClick={onGoUpload}>Go to Upload</button>
    </div>
  )
}
