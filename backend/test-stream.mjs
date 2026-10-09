// Login and test the stream endpoint
import axios from 'axios';
import fs from 'fs';

const BASE = 'http://localhost:3000';

try {
  // 1. Login to get a real token
  const loginRes = await axios.post(`${BASE}/api/auth/login`, {
    email: 'sahil@example.com',  // will try common emails
    password: 'password123'
  }).catch(() => null);

  // Try to find a valid token from authStore in localStorage (not possible from Node)
  // Instead, check what the stream endpoint returns with a bad token
  const badTest = await axios.get(
    `${BASE}/api/videos/6abb8dcd8716ebc99ce0d8a1/stream?token=badtoken`,
    { validateStatus: () => true }
  );
  console.log('Bad token response:', badTest.status, JSON.stringify(badTest.data));

  if (loginRes) {
    const token = loginRes.data.token;
    console.log('Got token:', token?.substring(0, 20) + '...');
    
    const streamRes = await axios.get(
      `${BASE}/api/videos/6abb8dcd8716ebc99ce0d8a1/stream?token=${token}`,
      { 
        responseType: 'stream',
        validateStatus: () => true,
        headers: { Range: 'bytes=0-1000' }
      }
    );
    console.log('Stream status:', streamRes.status);
    console.log('Stream headers:', JSON.stringify(streamRes.headers, null, 2));
    streamRes.data.destroy();
  }
} catch (e) {
  console.error('Error:', e.message);
}
