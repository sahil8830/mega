import client from './client'

export const search = async (query, topK = 10, useGqe = true) => {
  const { data } = await client.post('/api/search', { query, topK, useGqe })
  return data
}
