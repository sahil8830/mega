import express from "express";
import multer from "multer";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";
import mongoose from "mongoose";
import axios from "axios";
import Video from "../models/Video.js";
import { indexingQueue } from "../queues/indexingQueue.js";
import { protect } from "../middleware/auth.js";
import { invalidateUserSearchCache } from "../utils/searchCache.js";

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
 * Requires: any authenticated user
 * Each user uploads to their own namespace — isolated storage + FAISS index.
 */
router.post(
  "/upload",
  protect,
  upload.single("file"),
  async (req, res) => {
    try {
      if (!req.file) {
        return res.status(400).json({ message: "No video file uploaded." });
      }

      const title = req.body.title || req.file.originalname;
      const userId = req.user._id.toString();

      const video = await Video.create({
        title,
        filename: req.file.filename,
        storagePath: req.file.path,
        mimeType: req.file.mimetype,
        sizeBytes: req.file.size,
        status: "queued",
        uploadedBy: req.user._id,
      });

      // Enqueue BullMQ indexing job — pass user_id so ML service uses per-user FAISS
      const job = await indexingQueue.add("index-video", {
        videoId: video._id.toString(),
        videoFilename: video.filename,
        userId,
      });

      await Video.findByIdAndUpdate(video._id, { jobId: job.id });

      // Invalidate this user's cached search results — new video content changes what's relevant
      invalidateUserSearchCache(userId).catch(() => {});

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
 * Returns only the authenticated user's own videos.
 */
router.get("/", protect, async (req, res) => {
  try {
    const videos = await Video.find({ uploadedBy: req.user._id })
      .select("-storagePath")
      .sort({ createdAt: -1 });
    res.json(videos);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

/**
 * GET /api/videos/:id/status
 * Poll the indexing status of a specific video (only owner can check).
 */
router.get("/:id/status", protect, async (req, res) => {
  try {
    const video = await Video.findOne({
      _id: req.params.id,
      uploadedBy: req.user._id,
    }).select("title status jobId errorMessage duration");

    if (!video) {
      return res.status(404).json({ message: "Video not found." });
    }
    res.json(video);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

/**
 * GET /api/videos/:id/stream
 * Stream the video file with HTTP range support (required for seeking).
 * Only the video owner can stream it.
 */
router.get("/:id/stream", protect, async (req, res) => {
  try {
    const video = await Video.findOne({
      _id: req.params.id,
      uploadedBy: req.user._id,
    }).select("filename mimeType");

    if (!video) {
      return res.status(404).json({ message: "Video not found." });
    }

    const filePath = path.join(storageDir, video.filename);
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ message: "Video file not found on disk." });
    }

    const stat     = fs.statSync(filePath);
    const fileSize = stat.size;
    const mimeType = video.mimeType || "video/mp4";
    const range    = req.headers.range;

    if (range) {
      const [startStr, endStr] = range.replace(/bytes=/, "").split("-");
      const start     = parseInt(startStr, 10);
      const end       = endStr ? parseInt(endStr, 10) : fileSize - 1;
      const chunkSize = end - start + 1;

      res.status(206).set({
        "Content-Range":  `bytes ${start}-${end}/${fileSize}`,
        "Accept-Ranges":  "bytes",
        "Content-Length": chunkSize,
        "Content-Type":   mimeType,
      });
      fs.createReadStream(filePath, { start, end }).pipe(res);
    } else {
      res.status(200).set({
        "Content-Length": fileSize,
        "Content-Type":   mimeType,
        "Accept-Ranges":  "bytes",
      });
      fs.createReadStream(filePath).pipe(res);
    }
  } catch (err) {
    console.error("[Stream] Error:", err.message);
    if (!res.headersSent) res.status(500).json({ message: err.message });
  }
});


/**
 * POST /api/videos/:id/reindex
 * Re-index a video with the latest improved ML settings.
 * Clears old FAISS entries + segments, then re-runs the full pipeline.
 */
router.post("/:id/reindex", protect, async (req, res) => {
  try {
    const video = await Video.findOne({
      _id: req.params.id,
      uploadedBy: req.user._id,
    }).select("filename status");

    if (!video) {
      return res.status(404).json({ message: "Video not found." });
    }

    // Update status to reindexing
    await Video.findByIdAndUpdate(req.params.id, { status: "indexing" });

    // Call ML service reindex endpoint (fire and forget)
    axios.post(`${process.env.ML_SERVICE_URL || "http://localhost:8001"}/ml/reindex`, {
      video_id: req.params.id,
      video_filename: video.filename,
      user_id: req.user._id.toString(),
    }).catch(err => console.error("[Reindex] ML service error:", err.message));

    res.json({
      message: "Re-indexing started with improved settings. Poll /api/videos/:id/status for completion.",
      videoId: req.params.id,
      status: "indexing",
    });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

/**
 * DELETE /api/videos/:id
 * Delete a video: removes file from disk, segments from MongoDB,
 * FAISS entries from ML service, and the Video document.
 */
router.delete("/:id", protect, async (req, res) => {
  try {
    // Find by _id only — then verify ownership
    const video = await Video.findById(req.params.id);

    if (!video) {
      return res.status(404).json({ message: "Video not found." });
    }

    // Ownership check: admins can delete anything, users can only delete their own
    if (
      req.user.role !== "admin" &&
      video.uploadedBy?.toString() !== req.user._id.toString()
    ) {
      return res.status(403).json({ message: "Not authorized to delete this video." });
    }

    // 1. Delete file from disk
    const filePath = path.join(storageDir, video.filename);
    if (fs.existsSync(filePath)) {
      try { fs.unlinkSync(filePath); } catch (e) { console.warn("[Delete] File unlink:", e.message); }
    }

    // 2. Clear FAISS entries in ML service (best-effort)
    try {
      await axios.post(
        `${process.env.ML_SERVICE_URL || "http://localhost:8001"}/ml/delete-video`,
        { video_id: req.params.id, user_id: req.user._id.toString() }
      );
    } catch (mlErr) {
      console.warn("[Delete] ML FAISS clear skipped:", mlErr.message);
    }

    // 3. Delete segment documents
    await mongoose.connection.db.collection("segments").deleteMany(
      { videoId: new mongoose.Types.ObjectId(req.params.id) }
    );

    // 4. Delete the Video document
    await Video.findByIdAndDelete(req.params.id);

    return res.json({ message: "Video deleted successfully.", videoId: req.params.id });
  } catch (err) {
    console.error("[Delete] Error:", err.message);
    return res.status(500).json({ message: err.message });
  }
});


export default router;
