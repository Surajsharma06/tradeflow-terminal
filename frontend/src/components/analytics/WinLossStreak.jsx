import { useMemo } from 'react';
import { Zap, Trophy, Flame, Activity } from 'lucide-react';
function StatBox({ label, value, sub, icon: Icon, color }) {
  return (
    <div className={`flex flex-col gap-0.5 px-3 py-2.5 rounded-lg bg-surface-elevated/60 border ${color}`}>
      <div className="flex items-center gap-1.5 text-[10px] font-medium text-text-secondary uppercase tracking-wider">
        {Icon && <Icon size={11} />}
        {label}
      </div>
      <div className="text-xl font-bold font-tabular text-text-primary">{value}</div>
      {sub && <div className="text-[10px] text-text-tertiary">{sub}</div>}
    </div>
  );
}

function OutcomeDot({ result }) {
  const cls = result === 'WIN'
    ? 'bg-positive'
    : result === 'LOSS'
      ? 'bg-negative'
      : 'bg-warning';
  return <div className={`w-4 h-4 rounded-sm flex-shrink-0 ${cls}`} title={result} />;
}

export default function WinLossStreak({ trades, loading = false }) {

  const stats = useMemo(() => {
    const closed = (trades ?? []).filter(t => t.result !== 'OPEN');
    if (!closed.length) return null;

    const totalWins   = closed.filter(t => t.result === 'WIN').length;
    const totalLosses = closed.filter(t => t.result === 'LOSS').length;
    const winRate     = (totalWins / closed.length * 100).toFixed(1);

    let maxWin = 0, maxLoss = 0, streak = 0, prev = null;
    for (const t of closed) {
      const isWin = t.result === 'WIN';
      if (prev === isWin) { streak++; } else { streak = 1; }
      prev = isWin;
      if (isWin) maxWin  = Math.max(maxWin, streak);
      else       maxLoss = Math.max(maxLoss, streak);
    }
    const lastResult = closed[closed.length - 1].result;
    let curStreak = 0;
    for (let i = closed.length - 1; i >= 0; i--) {
      if (closed[i].result === lastResult) curStreak++;
      else break;
    }

    const recent = closed.slice(-20).map(t => t.result);
    return { totalWins, totalLosses, winRate, maxWin, maxLoss, curStreak, lastResult, recent };
  }, [trades]);

  if (loading) {
    return (
      <div className="glass-card p-5 h-full flex items-center justify-center text-text-muted text-sm">
        Running backtest…
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="glass-card p-5 h-full flex items-center justify-center text-text-muted text-sm">
        No closed trades yet
      </div>
    );
  }

  return (
    <div className="glass-card p-5">
      <div className="flex items-center gap-3 mb-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-subtle">
          <Zap className="h-4 w-4 text-accent" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Win/Loss Streak</h3>
          <p className="text-xs text-text-secondary">Real backtest outcomes</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 mb-4">
        <StatBox label="Current Streak" value={`${stats.lastResult === 'WIN' ? '+' : '-'}${stats.curStreak}`}
          sub={stats.lastResult === 'WIN' ? 'Winning' : 'Losing'}
          icon={Flame} color={stats.lastResult === 'WIN' ? 'border-positive/20' : 'border-negative/20'} />
        <StatBox label="Win Rate" value={`${stats.winRate}%`}
          sub={`${stats.totalWins}W / ${stats.totalLosses}L`}
          icon={Activity} color="border-accent/20" />
        <StatBox label="Best Streak" value={stats.maxWin}
          sub="consecutive wins" icon={Trophy} color="border-positive/20" />
        <StatBox label="Worst Streak" value={stats.maxLoss}
          sub="consecutive losses" icon={Zap} color="border-negative/20" />
      </div>

      {/* Recent 20 outcomes */}
      <div>
        <p className="text-[10px] text-text-tertiary mb-2 uppercase tracking-wider">Last {stats.recent.length} trades</p>
        <div className="flex flex-wrap gap-1">
          {stats.recent.map((r, i) => <OutcomeDot key={i} result={r} />)}
        </div>
        <div className="flex gap-3 mt-2 text-[10px] text-text-tertiary">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-positive inline-block" />Win</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-negative inline-block" />Loss</span>
        </div>
      </div>
    </div>
  );
}
