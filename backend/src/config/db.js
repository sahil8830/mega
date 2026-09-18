import mongoose from "mongoose";

/**
 * Connect to MongoDB using the URI from environment variables.
 * Retries indefinitely until connected (appropriate for dev).
 */
export const connectDB = async () => {
  const uri = process.env.MONGODB_URI;
  if (!uri) {
    throw new Error("MONGODB_URI is not defined in environment variables");
  }

  try {
    await mongoose.connect(uri);
    console.log(`✅ MongoDB connected: ${mongoose.connection.host}`);
  } catch (error) {
    console.error("❌ MongoDB connection error:", error.message);
    process.exit(1);
  }

  mongoose.connection.on("disconnected", () => {
    console.warn("⚠️  MongoDB disconnected. Attempting to reconnect...");
  });

  mongoose.connection.on("error", (err) => {
    console.error("❌ MongoDB error:", err.message);
  });
};
