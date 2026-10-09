import jwt from "jsonwebtoken";
import User from "../models/User.js";

/**
 * Middleware: verify JWT from Authorization header.
 * Attaches `req.user` on success.
 */
export const protect = async (req, res, next) => {
  // Accept token from Authorization header OR ?token= query param
  // (query param needed for <video src="..."> which can't set headers)
  let token = null

  const authHeader = req.headers.authorization
  if (authHeader && authHeader.startsWith("Bearer ")) {
    token = authHeader.split(" ")[1]
  } else if (req.query.token) {
    token = req.query.token
  }

  if (!token) {
    return res.status(401).json({ message: "Not authorized. No token provided." })
  }

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET)
    req.user = await User.findById(decoded.id).select("-passwordHash")

    if (!req.user) {
      return res.status(401).json({ message: "User not found." })
    }

    next()
  } catch {
    return res.status(401).json({ message: "Invalid or expired token." })
  }
}


/**
 * Middleware: restrict route to admins only.
 * Must be used AFTER `protect`.
 */
export const requireAdmin = (req, res, next) => {
  if (req.user?.role !== "admin") {
    return res.status(403).json({ message: "Forbidden. Admin role required." });
  }
  next();
};
