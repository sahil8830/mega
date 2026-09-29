import mongoose from 'mongoose';

await mongoose.connect('mongodb://localhost:27017/mega');

// Reset all failed videos back to 'queued' so they can be re-indexed
const result = await mongoose.connection.collection('videos').updateMany(
  { status: 'failed' },
  { $set: { status: 'queued', errorMessage: null, jobId: null } }
);

console.log(`✅ Reset ${result.modifiedCount} failed video(s) to 'queued'`);

const videos = await mongoose.connection.collection('videos').find({}).toArray();
console.log('\nAll videos:');
videos.forEach(v => console.log(`  [${v.status}] ${v.title} — ${v.filename}`));

await mongoose.disconnect();
