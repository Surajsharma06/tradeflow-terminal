import { motion } from 'framer-motion';

/**
 * Wraps a route page with a subtle enter/exit transition.
 * Uses transform/opacity only (GPU-friendly, no layout thrash).
 * Honors prefers-reduced-motion via the app-level MotionConfig.
 */
export default function PageTransition({ children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}
