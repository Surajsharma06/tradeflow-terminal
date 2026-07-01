import Header from './Header';
import Sidebar from './Sidebar';

// ══════════════════════════════════════════════════════════════════
//  LAYOUT SHELL
//  CSS Grid: header spans full width on top,
//  sidebar + content below
// ══════════════════════════════════════════════════════════════════
export default function Layout({ children }) {
  return (
    <div className="h-screen w-screen overflow-hidden bg-bg flex flex-col">
      {/* ── Header (full-width top bar) ── */}
      <Header />

      {/* ── Body: Sidebar + Content ── */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        {/* ── Main content area ── */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 bg-bg">
          <div className="max-w-[1800px] mx-auto animate-fade-in">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
