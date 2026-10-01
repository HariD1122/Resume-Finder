import { Component } from 'react'

// A crash in one screen must never leave the whole app blank
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error) {
    console.error('UI error:', error)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="gate">
        <div className="card" role="alert" style={{ maxWidth: 440, textAlign: 'center' }}>
          <h2>Something went wrong</h2>
          <p className="muted" style={{ margin: '8px 0 16px' }}>This screen hit an unexpected error. Your data is safe.</p>
          <div className="modal-actions" style={{ justifyContent: 'center' }}>
            <button className="btn btn-secondary" onClick={() => { window.location.hash = 'upload'; this.setState({ error: null }) }}>Go to Upload</button>
            <button className="btn btn-primary" onClick={() => window.location.reload()}>Reload</button>
          </div>
        </div>
      </div>
    )
  }
}
