import client from './client'

export const login = async (payload) => {
  const { data } = await client.post('/api/auth/login', payload)
  return data
}

export const register = async (payload) => {
  const { data } = await client.post('/api/auth/register', payload)
  return data
}
