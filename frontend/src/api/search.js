import client from './client'

export const search = async (query, topK = 5, useGqe = true) => {
  const { data } = await client.post('/api/search', { query, topK, useGqe })
  return { ...data, results: (data.results ?? []).slice(0, topK) }
}
