'use client'

import { useState } from 'react'
import axios from 'axios'
import PreviewCard from './PreviewCard'

interface ProcessResponse {
  post_id: number
  game_name: string
  final_text: string
  banner_path: string | null
}

export default function PostForm() {
  const [steamLink, setSteamLink] = useState('')
  const [comment, setComment] = useState('')
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState<ProcessResponse | null>(null)
  const [error, setError] = useState('')
  const [publishLoading, setPublishLoading] = useState(false)

  const handleProcess = async () => {
    if (!steamLink.trim()) {
      setError('Введи ссылку на Steam')
      return
    }

    setLoading(true)
    setError('')

    try {
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/api/process`,
        {
          steam_link: steamLink,
          comment: comment,
        }
      )

      setPreview(response.data)
      setSteamLink('')
      setComment('')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка обработки')
    } finally {
      setLoading(false)
    }
  }

  const handlePublish = async () => {
    if (!preview) return

    setPublishLoading(true)
    setError('')

    try {
      await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/api/publish`,
        {
          post_id: preview.post_id,
        }
      )

      setPreview(null)
      alert('✅ Пост опубликован!')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка публикации')
    } finally {
      setPublishLoading(false)
    }
  }

  const handleCancel = () => {
    setPreview(null)
    setError('')
  }

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto', padding: '20px' }}>
      {!preview ? (
        <div>
          <h1>🎮 Steam Post Bot</h1>
          <p>Введи ссылку на Steam-игру и опиши раздачу</p>

          <div style={{ marginBottom: '15px' }}>
            <label>
              Ссылка на Steam:
              <input
                type="text"
                placeholder="https://store.steampowered.com/app/2019300/"
                value={steamLink}
                onChange={(e) => setSteamLink(e.target.value)}
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '10px',
                  marginTop: '5px',
                  boxSizing: 'border-box',
                }}
              />
            </label>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label>
              Комментарий о раздаче:
              <textarea
                placeholder="Кнопка раздачи внизу страницы, дает +1 к значку, повторная раздача..."
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={4}
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '10px',
                  marginTop: '5px',
                  boxSizing: 'border-box',
                }}
              />
            </label>
          </div>

          {error && <p style={{ color: 'red' }}>{error}</p>}

          <button
            onClick={handleProcess}
            disabled={loading}
            style={{
              padding: '10px 20px',
              background: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '5px',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? '⏳ Обработка...' : '✨ Сгенерировать пост'}
          </button>
        </div>
      ) : (
        <PreviewCard
          preview={preview}
          onPublish={handlePublish}
          onCancel={handleCancel}
          publishLoading={publishLoading}
          error={error}
        />
      )}
    </div>
  )
}
