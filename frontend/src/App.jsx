import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { MotionConfig, AnimatePresence } from 'framer-motion';
import Layout from './components/layout/Layout';
import PageTransition from './components/common/PageTransition';
import DashboardPage from './pages/DashboardPage';
import AnalyticsPage from './pages/AnalyticsPage';
import BacktestPage from './pages/BacktestPage';
import ToolsPage from './pages/ToolsPage';
import SettingsPage from './pages/SettingsPage';
import ForexPage from './pages/ForexPage';
import LipschutzPage from './pages/LipschutzPage';
import CryptoPage from './pages/CryptoPage';
import CommodityPage from './pages/CommodityPage';

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<PageTransition><DashboardPage /></PageTransition>} />
        <Route path="/forex" element={<PageTransition><ForexPage /></PageTransition>} />
        <Route path="/discipline" element={<PageTransition><LipschutzPage /></PageTransition>} />
        <Route path="/analytics" element={<PageTransition><AnalyticsPage /></PageTransition>} />
        <Route path="/backtest" element={<PageTransition><BacktestPage /></PageTransition>} />
        <Route path="/tools" element={<PageTransition><ToolsPage /></PageTransition>} />
        <Route path="/settings" element={<PageTransition><SettingsPage /></PageTransition>} />
        <Route path="/crypto" element={<PageTransition><CryptoPage /></PageTransition>} />
        <Route path="/commodity" element={<PageTransition><CommodityPage /></PageTransition>} />
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    // reducedMotion="user" disables/simplifies all framer-motion
    // animations for users with prefers-reduced-motion enabled.
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <Layout>
          <AnimatedRoutes />
        </Layout>
      </BrowserRouter>
    </MotionConfig>
  );
}
