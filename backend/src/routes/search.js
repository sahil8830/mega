import express from "express";
import axios from "axios";
import Result from "../models/Result.js";
import { protect } from "../middleware/auth.js";

const router = express.Router();

const ML_SERVICE_URL = process.env.ML_SERVICE_URL || "http://localhost:8001";

/**
 * POST /api/search
 * Body: { query: string, topK?: number }
 *
 * Proxies the request to the FastAPI ML service and persists the result.
 * Auth is optional — anonymous search is allowed.
 */
router.post("/", async (req, res) => {
  try {
    const { query, topK = 5 } = req.body;

    if (!query || typeof query !== "string" || query.trim().length === 0) {
      return res.status(400).json({ message: "query is required." });
    }

    // Forward to ML service
    const mlResponse = await axios.post(`${ML_SERVICE_URL}/ml/search`, {
      query: query.trim(),
      top_k: topK,
    });

    const mlData = mlResponse.data;

    // Persist top result to MongoDB for logging / future training
    if (mlData.status === "ok" && mlData.results?.length > 0) {
      const top = mlData.results[0];
      await Result.create({
        rawQuery: query.trim(),
        videoId: top.video_id,
        startTime: top.start_time,
        endTime: top.end_time,
        answerabilityScore: top.answerability_score,
        localizationConfidence: top.localization_confidence,
        refinementTriggered: top.refinement_triggered,
        evidence: {
          visualWeight: top.evidence?.visual_weight ?? 0,
          speechWeight: top.evidence?.speech_weight ?? 0,
          ocrWeight: top.evidence?.ocr_weight ?? 0,
          visualSimilarity: top.evidence?.visual_similarity ?? 0,
          speechSimilarity: top.evidence?.speech_similarity ?? 0,
          ocrSimilarity: top.evidence?.ocr_similarity ?? 0,
        },
        rank: 1,
        // searchedBy: req.user?._id,   // Uncomment when auth is added
      });
    }

    res.json(mlData);
  } catch (err) {
    if (err.code === "ECONNREFUSED") {
      return res.status(503).json({
        message: "ML service is unavailable. Make sure it is running on port 8001.",
      });
    }
    res.status(500).json({ message: err.message });
  }
});

export default router;
