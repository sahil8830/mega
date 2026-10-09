import client from './client'

export const getHistory = async (page = 1, limit = 20) => {
  const { data } = await client.get('/api/search/history', { params: { page, limit } })
  return data
}

export const getHistoryDetail = async (queryId) => {
  const { data } = await client.get(`/api/search/history/${queryId}`)
  return data
}

export const deleteHistory = async (queryId) => {
  const { data } = await client.delete(`/api/search/history/${queryId}`)
  return data
}
