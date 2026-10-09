// Trigger reindex via the backend — add a reindex endpoint to backend/videos.js
// First let's find the registered user emails in MongoDB
import mongoose from 'mongoose';
import dotenv from 'dotenv';
dotenv.config();

await mongoose.connect(process.env.MONGODB_URI);

const User = mongoose.model('User', new mongoose.Schema({
  email: String,
  name: String,
  role: String,
}));

const users = await User.find({}).select('email name role');
console.log('Users in DB:', users.map(u => ({ email: u.email, name: u.name, role: u.role })));

await mongoose.disconnect();
