import express from "express";
import axios from "axios";
import Query from "../models/Query.js";
import Result from "../models/Result.js";

const router = express.Router();
const ML_SERVICE_URL = process.env.ML_SERVICE_URL || "http://localhost:8001";

/**
 * POST /api/search
 * Body: { query: string, topK?: number, useGqe?: boolean }
 *
 * Full pipeline:
 *  1. (optional) POST /ml/query/expand → get GQE variants + representative embeddings
 *  2. POST /ml/search  → FAISS search + fixed-weight fusion
 *  3. Persist Query + all Results in MongoDB
 *  4. Return ranked results to client
 *
 * useGqe defaults to true. Set to false for a fast "direct encode" search.
 */
router.post("/", async (req, res) => {
  try {
    const { query, topK = 10, useGqe = true } = req.body;

    if (!query || typeof query !== "string" || query.trim().length === 0) {
      return res.status(400).json({ message: "query is required." });
    }

    const cleanQuery = query.trim();
    let gqeData = null;
    let searchPayload = { query: cleanQuery, top_k: topK };

    // ── Step 1: GQE query expansion (optional) ────────────────────────────
    if (useGqe) {
      try {
        const expandRes = await axios.post(`${ML_SERVICE_URL}/ml/query/expand`, {
          query: cleanQuery,
        });
        gqeData = expandRes.data;

        // Pass representative embeddings to search for better recall
        searchPayload.representative_embeddings = gqeData.representative_embeddings;
        searchPayload.modality_weights = gqeData.weights;
      } catch (expandErr) {
        // GQE failure is non-fatal — fall back to direct search
        console.warn("[Search] GQE expansion failed, falling back to direct search:", expandErr.message);
      }
    }

    // ── Step 2: Search ────────────────────────────────────────────────────
    const mlResponse = await axios.post(`${ML_SERVICE_URL}/ml/search`, searchPayload);
    const mlData = mlResponse.data;

    // ── Step 3: Persist to MongoDB ────────────────────────────────────────
    try {
      const queryDoc = await Query.create({
        rawQuery: cleanQuery,
        expandedVariants: gqeData?.variants ?? [],
        representativeQueries: gqeData?.representatives ?? [cleanQuery],
        predictedModality: mlData.modality,
        modalityWeights: mlData.weights,
        resultCount: mlData.results?.length ?? 0,
        searchedBy: req.user?._id ?? null,
      });

      // Persist each result
      if (mlData.results?.length > 0) {
        const resultDocs = mlData.results.map((r) => ({
          queryId: queryDoc._id,
          rawQuery: cleanQuery,
          videoId: r.video_id,
          segmentId: r.segment_id,
          startTime: r.start_time,
          endTime: r.end_time,
          rank: r.rank,
          fusedScore: r.fused_score,
          evidence: {
            visualWeight:      r.modality_weights?.visual ?? 0,
            speechWeight:      r.modality_weights?.speech ?? 0,
            ocrWeight:         r.modality_weights?.ocr    ?? 0,
            visualSimilarity:  r.visual_score ?? 0,
            speechSimilarity:  r.speech_score ?? 0,
            ocrSimilarity:     r.ocr_score    ?? 0,
          },
        }));
        await Result.insertMany(resultDocs);
      }
    } catch (dbErr) {
      // DB persistence failure is non-fatal — still return results to user
      console.error("[Search] Failed to persist to MongoDB:", dbErr.message);
    }

    // ── Step 4: Return results ────────────────────────────────────────────
    res.json({
      query:            cleanQuery,
      results:          mlData.results ?? [],
      modality:         mlData.modality,
      weights:          mlData.weights,
      totalCandidates:  mlData.total_candidates,
      gqeApplied:       mlData.gqe_applied ?? false,
      variants:         gqeData?.variants ?? [],
    });

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
