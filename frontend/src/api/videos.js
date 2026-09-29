import client from './client'

export const listVideos = async () => {
  const { data } = await client.get('/api/videos')
  return data
}

export const getVideoStatus = async (id) => {
  const { data } = await client.get(`/api/videos/${id}/status`)
  return data
}

export const uploadVideo = async (file, title, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  form.append('title', title)
  const { data } = await client.post('/api/videos/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total))
    },
  })
  return data
}
