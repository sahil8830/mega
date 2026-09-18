import "dotenv/config";
import express from "express";
import cors from "cors";
import morgan from "morgan";

import { connectDB } from "./config/db.js";
import authRouter from "./routes/auth.js";
import videosRouter from "./routes/videos.js";
import searchRouter from "./routes/search.js";

// ─── Connect to MongoDB ────────────────────────────────────────────────────────
await connectDB();

// ─── App ──────────────────────────────────────────────────────────────────────
const app = express();

// Middleware
app.use(cors({ origin: ["http://localhost:5173", "http://localhost:3000"] }));
app.use(express.json());
app.use(morgan("dev"));

// ─── Routes ───────────────────────────────────────────────────────────────────
app.use("/api/auth", authRouter);
app.use("/api/videos", videosRouter);
app.use("/api/search", searchRouter);

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "mega-backend" });
});

// ─── 404 handler ──────────────────────────────────────────────────────────────
app.use((_req, res) => {
  res.status(404).json({ message: "Route not found." });
});

// ─── Global error handler ─────────────────────────────────────────────────────
app.use((err, _req, res, _next) => {
  console.error("❌ Unhandled error:", err.message);
  res.status(500).json({ message: err.message || "Internal server error." });
});

// ─── Start ────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 Backend running at http://localhost:${PORT}`);
  console.log(`   MongoDB : ${process.env.MONGODB_URI}`);
  console.log(`   Redis   : ${process.env.REDIS_HOST}:${process.env.REDIS_PORT}`);
  console.log(`   ML Svc  : ${process.env.ML_SERVICE_URL}`);
});
