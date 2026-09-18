import { Queue, Worker } from "bullmq";
import IORedis from "ioredis";
import axios from "axios";
import Video from "../models/Video.js";

// ─── Redis Connection ──────────────────────────────────────────────────────────
const connection = new IORedis({
  host: process.env.REDIS_HOST || "localhost",
  port: parseInt(process.env.REDIS_PORT) || 6379,
  password: process.env.REDIS_PASSWORD || undefined,
  maxRetriesPerRequest: null, // Required by BullMQ
});

// ─── Queue ────────────────────────────────────────────────────────────────────
export const indexingQueue = new Queue("indexing", {
  connection,
  defaultJobOptions: {
    attempts: 3,
    backoff: { type: "exponential", delay: 5000 },
    removeOnComplete: 100,
    removeOnFail: 200,
  },
});

// ─── Worker ───────────────────────────────────────────────────────────────────
const ML_SERVICE_URL = process.env.ML_SERVICE_URL || "http://localhost:8001";

const worker = new Worker(
  "indexing",
  async (job) => {
    const { videoId, videoFilename } = job.data;
    console.log(`🔧 [Indexing Worker] Starting job ${job.id} for video ${videoId}`);

    // Mark video as indexing
    await Video.findByIdAndUpdate(videoId, { status: "indexing" });

    try {
      // Call ML service indexing endpoint
      await axios.post(`${ML_SERVICE_URL}/ml/index`, {
        video_id: videoId,
        video_filename: videoFilename,
      });

      // Mark video as indexed
      await Video.findByIdAndUpdate(videoId, { status: "indexed" });
      console.log(`✅ [Indexing Worker] Job ${job.id} completed for video ${videoId}`);
    } catch (err) {
      // Mark video as failed
      await Video.findByIdAndUpdate(videoId, {
        status: "failed",
        errorMessage: err.message,
      });
      throw err; // BullMQ will retry based on defaultJobOptions
    }
  },
  {
    connection,
    concurrency: 1, // Process one video at a time to avoid GPU OOM
  }
);

worker.on("completed", (job) => {
  console.log(`✅ [Worker] Job ${job.id} completed`);
});

worker.on("failed", (job, err) => {
  console.error(`❌ [Worker] Job ${job?.id} failed:`, err.message);
});

worker.on("error", (err) => {
  console.error("❌ [Worker] Worker error:", err.message);
});

export { connection };
