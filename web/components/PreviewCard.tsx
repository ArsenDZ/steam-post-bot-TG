'use client'

interface ProcessResponse {
  post_id: number
  game_name: string
  final_text: string
  banner_path: string | null
}

interface PreviewCardProps {
  preview: ProcessResponse
  onPublish: () => void
  onCancel: () => void
  publishLoading: boolean
  error: string
}

export default function PreviewCard({
  preview,
  onPublish,
  onCancel,
  publishLoading,
  error,
}: PreviewCardProps) {
  return (
    <div>
      <h2>📋 Предпросмотр</h2>

      {preview.banner_path && (
        <div style={{ marginBottom: '15px' }}>
          <img
            src={preview.banner_path}
            alt={preview.game_name}
            style={{ maxWidth: '100%', borderRadius: '5px' }}
          />
        </div>
      )}

      <div
        style={{
          background: '#f5f5f5',
          padding: '15px',
          borderRadius: '5px',
          marginBottom: '15px',
          whiteSpace: 'pre-wrap',
          wordWrap: 'break-word',
          fontFamily: 'monospace',
          fontSize: '12px',
        }}
      >
        {preview.final_text}
      </div>

      {error && <p style={{ color: 'red' }}>{error}</p>}

      <div style={{ display: 'flex', gap: '10px' }}>
        <button
          onClick={onPublish}
          disabled={publishLoading}
          style={{
            flex: 1,
            padding: '10px 20px',
            background: '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: '5px',
            cursor: publishLoading ? 'not-allowed' : 'pointer',
            opacity: publishLoading ? 0.6 : 1,
          }}
        >
          {publishLoading ? '⏳ Публикация...' : '🚀 Опубликовать'}
        </button>

        <button
          onClick={onCancel}
          disabled={publishLoading}
          style={{
            flex: 1,
            padding: '10px 20px',
            background: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '5px',
            cursor: publishLoading ? 'not-allowed' : 'pointer',
            opacity: publishLoading ? 0.6 : 1,
          }}
        >
          ❌ Отменить
        </button>
      </div>
    </div>
  )
}
