import mongoose from 'mongoose';

await mongoose.connect('mongodb://localhost:27017/mega');

const result = await mongoose.connection.collection('users').updateMany(
  {},
  { $set: { role: 'admin' } }
);

console.log(`✅ Promoted ${result.modifiedCount} user(s) to admin role.`);

const users = await mongoose.connection.collection('users').find({}).toArray();
console.log('Current users:');
users.forEach(u => console.log(`  - ${u.email} (${u.role})`));

await mongoose.disconnect();
