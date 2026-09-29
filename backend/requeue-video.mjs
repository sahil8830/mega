/**
 * Re-queues a specific video for indexing.
 * Usage: node requeue-video.mjs <videoId> <userId>
 */
import mongoose from 'mongoose';
import { Queue } from 'bullmq';
import IORedis from 'ioredis';

const videoId = process.argv[2];
const userId = process.argv[3] || 'global';

if (!videoId) {
  console.error('Usage: node requeue-video.mjs <videoId> [userId]');
  process.exit(1);
}

const connection = new IORedis({ host: 'localhost', port: 6379, maxRetriesPerRequest: null });
const indexingQueue = new Queue('indexing', { connection });

await mongoose.connect('mongodb://localhost:27017/mega');

const video = await mongoose.connection.collection('videos').findOne({
  _id: new mongoose.Types.ObjectId(videoId),
});

if (!video) {
  console.error('Video not found:', videoId);
  process.exit(1);
}

console.log(`Re-queuing: "${video.title}"`);
console.log(`  filename: ${video.filename}`);
console.log(`  userId:   ${userId}`);

// Reset status
await mongoose.connection.collection('videos').updateOne(
  { _id: video._id },
  { $set: { status: 'queued', errorMessage: null, jobId: null } }
);

// Add to queue
const job = await indexingQueue.add('index-video', {
  videoId: videoId,
  videoFilename: video.filename,
  userId,
});

await mongoose.connection.collection('videos').updateOne(
  { _id: video._id },
  { $set: { jobId: job.id } }
);

console.log(`✅ Job ${job.id} queued. Monitor: GET /api/videos/${videoId}/status`);

await mongoose.disconnect();
await connection.quit();
