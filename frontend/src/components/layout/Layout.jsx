import Header from './Header';
import Sidebar from './Sidebar';

// ══════════════════════════════════════════════════════════════════
//  LAYOUT SHELL
//  CSS Grid: header spans full width on top,
//  sidebar + content below
// ══════════════════════════════════════════════════════════════════
export default function Layout({ children }) {
  return (
    // app-bg paints the ambient gradient blobs once on this
    // non-scrolling shell; children stay transparent above it.
    <div className="h-screen w-screen overflow-hidden app-bg flex flex-col">
      {/* ── Header (full-width top bar) ── */}
      <Header />

      {/* ── Body: Sidebar + Content ── */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        {/* ── Main content area ── */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-4">
          <div className="max-w-[1800px] mx-auto animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
