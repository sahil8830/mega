import express from "express";
import multer from "multer";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";
import Video from "../models/Video.js";
import { indexingQueue } from "../queues/indexingQueue.js";
import { protect, requireAdmin } from "../middleware/auth.js";

const router = express.Router();

// ─── Multer Setup ─────────────────────────────────────────────────────────────
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const storageDir = path.resolve(
  __dirname,
  "../../",
  process.env.VIDEO_STORAGE_PATH || "storage/videos"
);

// Ensure storage directory exists
fs.mkdirSync(storageDir, { recursive: true });

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, storageDir),
  filename: (_req, file, cb) => {
    const uniqueSuffix = `${Date.now()}-${Math.round(Math.random() * 1e9)}`;
    cb(null, `${uniqueSuffix}${path.extname(file.originalname)}`);
  },
});

const upload = multer({
  storage,
  limits: {
    fileSize: (parseInt(process.env.MAX_FILE_SIZE_MB) || 500) * 1024 * 1024,
  },
  fileFilter: (_req, file, cb) => {
    const allowed = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"];
    if (allowed.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error("Only video files (mp4, mov, avi, webm) are allowed."));
    }
  },
});

// ─── Routes ───────────────────────────────────────────────────────────────────

/**
 * POST /api/videos/upload
 * Requires: admin role
 * Body: multipart/form-data — file (video), title (string)
 */
router.post(
  "/upload",
  protect,
  requireAdmin,
  upload.single("file"),
  async (req, res) => {
    try {
      if (!req.file) {
        return res.status(400).json({ message: "No video file uploaded." });
      }

      const title = req.body.title || req.file.originalname;

      const video = await Video.create({
        title,
        filename: req.file.filename,
        storagePath: req.file.path,
        mimeType: req.file.mimetype,
        sizeBytes: req.file.size,
        status: "queued",
        uploadedBy: req.user._id,
      });

      // Enqueue BullMQ indexing job
      const job = await indexingQueue.add("index-video", {
        videoId: video._id.toString(),
        videoFilename: video.filename,
      });

      await Video.findByIdAndUpdate(video._id, { jobId: job.id });

      res.status(202).json({
        videoId: video._id,
        title: video.title,
        status: video.status,
        jobId: job.id,
        message: "Video uploaded successfully. Indexing job queued.",
      });
    } catch (err) {
      res.status(500).json({ message: err.message });
    }
  }
);

/**
 * GET /api/videos
 * Returns all videos with their indexing status.
 * Public (no auth required for browsing).
 */
router.get("/", async (_req, res) => {
  try {
    const videos = await Video.find()
      .select("-storagePath")
      .sort({ createdAt: -1 });
    res.json(videos);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

/**
 * GET /api/videos/:id/status
 * Poll the indexing status of a specific video.
 */
router.get("/:id/status", async (req, res) => {
  try {
    const video = await Video.findById(req.params.id).select(
      "title status jobId errorMessage duration"
    );
    if (!video) {
      return res.status(404).json({ message: "Video not found." });
    }
    res.json(video);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

export default router;
