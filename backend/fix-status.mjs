import mongoose from 'mongoose';
import dotenv from 'dotenv';
dotenv.config();

await mongoose.connect(process.env.MONGODB_URI);

// Reset any stuck 'indexing' videos back to 'indexed'
const result = await mongoose.connection.collection('videos').updateMany(
  { status: 'indexing' },
  { $set: { status: 'indexed' } }
);
console.log('Reset', result.modifiedCount, 'stuck videos → indexed');

// Also show all videos and their status
const videos = await mongoose.connection.collection('videos').find({}).toArray();
console.log('All videos:');
videos.forEach(v => console.log(' -', v._id, '|', v.title, '|', v.status, '| uploadedBy:', v.uploadedBy));

await mongoose.disconnect();
