import { MongoClient } from 'mongodb';
import { readFileSync, existsSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const client = new MongoClient('mongodb://localhost:27017/mega');
await client.connect();
const db = client.db('mega');

// Video statuses
const videos = await db.collection('videos').find({}, {
  projection: { title: 1, status: 1, userId: 1, filename: 1, error: 1 }
}).toArray();
console.log('=== Videos ===');
videos.forEach(v => console.log(JSON.stringify(v)));

// Segment count
const segCount = await db.collection('videosegments').countDocuments();
console.log('\nTotal segments in DB:', segCount);

// Sample one segment
const sample = await db.collection('videosegments').findOne({});
if (sample) {
  console.log('\nSample segment keys:', Object.keys(sample));
  console.log('videoId:', sample.videoId?.toString());
  console.log('userId:', sample.userId?.toString());
  console.log('hasVisualEmbed:', Array.isArray(sample.visual_embedding));
  console.log('hasSpeechEmbed:', Array.isArray(sample.speech_embedding));
  console.log('transcript:', String(sample.transcript || '').substring(0, 100));
  console.log('ocr_text:', String(sample.ocr_text || '').substring(0, 100));
} else {
  console.log('\nNO SEGMENTS FOUND IN DB!');
}

// Check FAISS dir
const faissBase = join(__dirname, '..', 'ml-service', 'faiss');
if (existsSync(faissBase)) {
  const userDirs = readdirSync(faissBase);
  console.log('\nFAISS user dirs:', userDirs);
  userDirs.forEach(uid => {
    try {
      const files = readdirSync(join(faissBase, uid));
      console.log(`  ${uid}:`, files);
    } catch(e) {}
  });
} else {
  console.log('\nFAISS dir does not exist at:', faissBase);
}

await client.close();
