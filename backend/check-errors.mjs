import mongoose from 'mongoose';

await mongoose.connect('mongodb://localhost:27017/mega');

// Get all failed/indexing videos with error messages
const videos = await mongoose.connection.collection('videos').find(
  { status: { $in: ['failed', 'indexing', 'indexed'] } }
).toArray();

console.log('=== Videos ===');
videos.forEach(v => {
  console.log(`\n[${v.status.toUpperCase()}] ${v.title}`);
  console.log(`  id: ${v._id}`);
  console.log(`  filename: ${v.filename}`);
  if (v.errorMessage) console.log(`  error: ${v.errorMessage}`);
});

await mongoose.disconnect();
