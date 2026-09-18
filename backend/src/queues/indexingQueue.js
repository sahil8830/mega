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

// How long to wait for the pipeline to finish (default: 30 minutes)
const MAX_WAIT_MS = parseInt(process.env.INDEXING_TIMEOUT_MS) || 30 * 60 * 1000;
const POLL_INTERVAL_MS = 5000; // Check MongoDB every 5 seconds

/**
 * Poll MongoDB until the video status is "indexed" or "failed".
 * The ML service pipeline updates the status directly in MongoDB.
 */
async function waitForIndexing(videoId) {
  const deadline = Date.now() + MAX_WAIT_MS;

  while (Date.now() < deadline) {
    const video = await Video.findById(videoId).select("status");
    if (!video) throw new Error(`Video ${videoId} not found in DB`);

    if (video.status === "indexed") return "indexed";
    if (video.status === "failed") throw new Error(`Indexing failed for video ${videoId}`);

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }

  throw new Error(`Indexing timed out after ${MAX_WAIT_MS / 60000} minutes for video ${videoId}`);
}

const worker = new Worker(
  "indexing",
  async (job) => {
    const { videoId, videoFilename } = job.data;
    console.log(`[Indexing Worker] Starting job ${job.id} for video ${videoId}`);

    // Mark video as indexing
    await Video.findByIdAndUpdate(videoId, { status: "indexing" });

    // Trigger ML service — returns immediately with status="indexing"
    // The pipeline runs as a FastAPI BackgroundTask and updates MongoDB directly
    const response = await axios.post(`${ML_SERVICE_URL}/ml/index`, {
      video_id: videoId,
      video_filename: videoFilename,
    });

    console.log(`[Indexing Worker] Pipeline triggered: ${response.data.status}. Polling for completion...`);

    // Poll MongoDB until the pipeline finishes (or fails / times out)
    const finalStatus = await waitForIndexing(videoId);
    console.log(`[Indexing Worker] Job ${job.id} finished with status: ${finalStatus}`);
  },
  {
    connection,
    concurrency: 1, // Process one video at a time to avoid GPU OOM
  }
);

worker.on("completed", (job) => {
  console.log(`[Worker] Job ${job.id} completed`);
});

worker.on("failed", (job, err) => {
  console.error(`[Worker] Job ${job?.id} failed:`, err.message);
  // Ensure DB reflects failure if polling threw
  if (job?.data?.videoId) {
    Video.findByIdAndUpdate(job.data.videoId, {
      status: "failed",
      errorMessage: err.message,
    }).catch(() => {});
  }
});

worker.on("error", (err) => {
  console.error("[Worker] Worker error:", err.message);
});

export { connection };
