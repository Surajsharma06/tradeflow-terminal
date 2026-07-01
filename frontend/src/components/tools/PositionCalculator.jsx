import { useState, useMemo } from 'react';
import { Calculator, Shield, AlertTriangle, Target, IndianRupee } from 'lucide-react';

export default function PositionCalculator({ className = '' }) {
  const [capital, setCapital] = useState(1000000);
  const [riskPercent, setRiskPercent] = useState(1.5);
  const [entryPrice, setEntryPrice] = useState(2450);
  const [stopLoss, setStopLoss] = useState(2380);

  const results = useMemo(() => {
    const riskAmount = capital * (riskPercent / 100);
    const riskPerShare = Math.abs(entryPrice - stopLoss);

    if (riskPerShare === 0) return null;

    const shares = Math.floor(riskAmount / riskPerShare);
    const totalCost = shares * entryPrice;
    const actualRisk = shares * riskPerShare;
    const capitalUsed = (totalCost / capital) * 100;
    const riskReward = riskPerShare > 0 ? ((entryPrice - stopLoss) > 0 ? 'Long' : 'Short') : '-';

    return {
      shares,
      totalCost,
      actualRisk,
      riskPerShare,
      capitalUsed,
      direction: riskReward,
      riskAmount,
    };
  }, [capital, riskPercent, entryPrice, stopLoss]);

  const riskLevel = riskPercent <= 1 ? 'low' : riskPercent <= 2 ? 'medium' : 'high';
  const riskColors = {
    low: { bar: 'bg-positive', text: 'text-positive', label: 'Conservative' },
    medium: { bar: 'bg-warning', text: 'text-warning', label: 'Moderate' },
    high: { bar: 'bg-negative', text: 'text-negative', label: 'Aggressive' },
  };

  return (
    <div className={`glass-card p-5 ${className}`}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-subtle">
          <Calculator className="h-4.5 w-4.5 text-accent" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Position Calculator</h3>
          <p className="text-xs text-text-secondary">Calculate optimal position size</p>
        </div>
      </div>

      <div className="space-y-5">
        {/* Capital input */}
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1.5">
            Trading Capital
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary text-sm">₹</span>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="w-full rounded-lg bg-surface border border-border px-3 py-2.5 pl-7 text-sm font-mono font-tabular text-text-primary
                focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none transition-all"
            />
          </div>
        </div>

        {/* Risk % slider */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium text-text-secondary">Risk per Trade</label>
            <span className={`text-sm font-semibold font-mono font-tabular ${riskColors[riskLevel].text}`}>
              {riskPercent}%
            </span>
          </div>
          <input
            type="range"
            min="0.5"
            max="3"
            step="0.1"
            value={riskPercent}
            onChange={(e) => setRiskPercent(parseFloat(e.target.value))}
            className="w-full h-1.5 rounded-full appearance-none cursor-pointer
              bg-surface accent-accent
              [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
              [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent [&::-webkit-slider-thumb]:shadow-lg
              [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-surface"
          />
          <div className="flex justify-between mt-1">
            <span className="text-[10px] text-text-tertiary">0.5%</span>
            <span className={`text-[10px] font-medium ${riskColors[riskLevel].text}`}>
              {riskColors[riskLevel].label}
            </span>
            <span className="text-[10px] text-text-tertiary">3.0%</span>
          </div>

          {/* Visual risk indicator */}
          <div className="mt-2 h-1.5 rounded-full bg-surface overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${riskColors[riskLevel].bar}`}
              style={{ width: `${((riskPercent - 0.5) / 2.5) * 100}%` }}
            />
          </div>
        </div>

        {/* Entry & Stop Loss */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">
              Entry Price
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary text-sm">₹</span>
              <input
                type="number"
                value={entryPrice}
                onChange={(e) => setEntryPrice(Number(e.target.value))}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2.5 pl-7 text-sm font-mono font-tabular text-text-primary
                  focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none transition-all"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">
              Stop Loss
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-negative text-sm">₹</span>
              <input
                type="number"
                value={stopLoss}
                onChange={(e) => setStopLoss(Number(e.target.value))}
                className="w-full rounded-lg bg-surface border border-negative/30 px-3 py-2.5 pl-7 text-sm font-mono font-tabular text-text-primary
                  focus:border-negative focus:ring-1 focus:ring-negative/30 outline-none transition-all"
              />
            </div>
          </div>
        </div>

        {/* Results */}
        {results && (
          <div className="mt-2 pt-4 border-t border-border space-y-3">
            <div className="grid grid-cols-2 gap-3">
              {[
                {
                  label: 'Position Size',
                  value: `₹${results.totalCost.toLocaleString('en-IN')}`,
                  icon: Target,
                  color: 'text-accent',
                },
                {
                  label: 'No. of Shares',
                  value: results.shares.toLocaleString(),
                  icon: IndianRupee,
                  color: 'text-text-primary',
                },
                {
                  label: 'Risk per Share',
                  value: `₹${results.riskPerShare.toLocaleString('en-IN')}`,
                  icon: Shield,
                  color: 'text-warning',
                },
                {
                  label: 'Amount at Risk',
                  value: `₹${results.actualRisk.toLocaleString('en-IN')}`,
                  icon: AlertTriangle,
                  color: 'text-negative',
                },
              ].map((item) => (
                <div key={item.label} className="rounded-lg bg-surface p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <item.icon className={`h-3 w-3 ${item.color}`} />
                    <span className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium">
                      {item.label}
                    </span>
                  </div>
                  <p className={`text-base font-semibold font-mono font-tabular ${item.color}`}>
                    {item.value}
                  </p>
                </div>
              ))}
            </div>

            {/* Capital usage bar */}
            <div className="rounded-lg bg-surface p-3">
              <div className="flex justify-between items-center mb-1.5">
                <span className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium">
                  Capital Utilization
                </span>
                <span className="text-xs font-mono font-tabular text-text-secondary">
                  {results.capitalUsed.toFixed(1)}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-bg overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    results.capitalUsed > 80 ? 'bg-negative' : results.capitalUsed > 50 ? 'bg-warning' : 'bg-accent'
                  }`}
                  style={{ width: `${Math.min(results.capitalUsed, 100)}%` }}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
