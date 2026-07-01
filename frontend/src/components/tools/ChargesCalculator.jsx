import { useState, useMemo } from 'react';
import { Receipt, IndianRupee, Percent } from 'lucide-react';

const ORDER_TYPES = [
  { key: 'delivery', label: 'Delivery (CNC)', stt: { buy: 0.001, sell: 0.001 }, brokerage: 0 },
  { key: 'intraday', label: 'Intraday (MIS)', stt: { buy: 0, sell: 0.00025 }, brokerage: 20 },
  { key: 'futures', label: 'F&O Futures', stt: { buy: 0, sell: 0.0001 }, brokerage: 20 },
  { key: 'options', label: 'F&O Options', stt: { buy: 0, sell: 0.0005 }, brokerage: 20 },
];

export default function ChargesCalculator({ className = '' }) {
  const [buyPrice, setBuyPrice] = useState(2450);
  const [sellPrice, setSellPrice] = useState(2520);
  const [quantity, setQuantity] = useState(100);
  const [orderType, setOrderType] = useState('intraday');

  const results = useMemo(() => {
    const config = ORDER_TYPES.find(o => o.key === orderType) || ORDER_TYPES[0];
    const turnover = (buyPrice + sellPrice) * quantity;
    const buyTurnover = buyPrice * quantity;
    const sellTurnover = sellPrice * quantity;

    // Brokerage: ₹20 per order or 0 for delivery
    const brokerage = config.key === 'delivery'
      ? 0
      : Math.min(20, buyTurnover * 0.0003) + Math.min(20, sellTurnover * 0.0003);

    // STT
    const sttBuy = buyTurnover * config.stt.buy;
    const sttSell = sellTurnover * config.stt.sell;
    const stt = sttBuy + sttSell;

    // Exchange charges (NSE): ~0.00345%
    const exchangeCharges = turnover * 0.0000345;

    // SEBI charges: ₹10 per crore
    const sebiCharges = turnover * 0.000001;

    // GST: 18% on (brokerage + exchange charges + SEBI)
    const gst = (brokerage + exchangeCharges + sebiCharges) * 0.18;

    // Stamp duty: 0.015% on buy (delivery), 0.003% on buy (intraday)
    const stampRate = config.key === 'delivery' ? 0.00015 : 0.00003;
    const stampDuty = buyTurnover * stampRate;

    const totalCharges = brokerage + stt + exchangeCharges + gst + sebiCharges + stampDuty;
    const grossPnL = (sellPrice - buyPrice) * quantity;
    const netPnL = grossPnL - totalCharges;
    const effectiveCharge = totalCharges / turnover * 100;

    // Tax calculation
    const holdingPeriod = config.key === 'delivery' ? 'long' : 'short';
    const taxableAmount = Math.max(0, netPnL);
    const stcg = taxableAmount * 0.20; // 20% STCG
    const ltcgExemption = 125000; // ₹1.25L exemption
    const ltcgTaxable = Math.max(0, taxableAmount - ltcgExemption);
    const ltcg = ltcgTaxable * 0.125; // 12.5% LTCG

    return {
      brokerage: Math.round(brokerage * 100) / 100,
      stt: Math.round(stt * 100) / 100,
      exchangeCharges: Math.round(exchangeCharges * 100) / 100,
      gst: Math.round(gst * 100) / 100,
      sebiCharges: Math.round(sebiCharges * 100) / 100,
      stampDuty: Math.round(stampDuty * 100) / 100,
      totalCharges: Math.round(totalCharges * 100) / 100,
      grossPnL,
      netPnL: Math.round(netPnL * 100) / 100,
      effectiveCharge: effectiveCharge.toFixed(4),
      turnover,
      holdingPeriod,
      stcg: Math.round(stcg),
      ltcg: Math.round(ltcg),
      ltcgExemption,
    };
  }, [buyPrice, sellPrice, quantity, orderType]);

  const isProfit = results.netPnL >= 0;

  return (
    <div className={`glass-card p-5 ${className}`}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gold-subtle">
          <Receipt className="h-4.5 w-4.5 text-gold" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Brokerage & Charges</h3>
          <p className="text-xs text-text-secondary">Indian market charges calculator</p>
        </div>
      </div>

      <div className="space-y-5">
        {/* Order Type Tabs */}
        <div className="flex gap-1 rounded-lg bg-surface p-1 overflow-x-auto">
          {ORDER_TYPES.map((type) => (
            <button
              key={type.key}
              onClick={() => setOrderType(type.key)}
              className={`flex-1 px-2.5 py-2 text-xs font-medium rounded-md transition-all duration-200 whitespace-nowrap
                ${orderType === type.key
                  ? 'bg-accent text-white shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
                }`}
            >
              {type.label}
            </button>
          ))}
        </div>

        {/* Price inputs */}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Buy Price</label>
            <div className="relative">
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-tertiary text-xs">₹</span>
              <input
                type="number"
                value={buyPrice}
                onChange={(e) => setBuyPrice(Number(e.target.value))}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 pl-6 text-sm font-mono font-tabular text-text-primary
                  focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none transition-all"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Sell Price</label>
            <div className="relative">
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-tertiary text-xs">₹</span>
              <input
                type="number"
                value={sellPrice}
                onChange={(e) => setSellPrice(Number(e.target.value))}
                className="w-full rounded-lg bg-surface border border-border px-3 py-2 pl-6 text-sm font-mono font-tabular text-text-primary
                  focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none transition-all"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Quantity</label>
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              className="w-full rounded-lg bg-surface border border-border px-3 py-2 text-sm font-mono font-tabular text-text-primary
                focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none transition-all"
            />
          </div>
        </div>

        {/* Charges breakdown */}
        <div className="rounded-lg bg-surface p-4 space-y-2.5">
          <h4 className="text-[10px] uppercase tracking-wider text-text-tertiary font-semibold mb-3">
            Charges Breakdown
          </h4>

          {[
            { label: 'Brokerage', value: results.brokerage },
            { label: 'STT', value: results.stt },
            { label: 'Exchange Txn Charges', value: results.exchangeCharges },
            { label: 'GST (18%)', value: results.gst },
            { label: 'SEBI Charges', value: results.sebiCharges },
            { label: 'Stamp Duty', value: results.stampDuty },
          ].map((charge) => (
            <div key={charge.label} className="flex items-center justify-between py-0.5">
              <span className="text-xs text-text-secondary">{charge.label}</span>
              <span className="text-xs font-mono font-tabular text-text-primary">
                ₹{charge.value.toFixed(2)}
              </span>
            </div>
          ))}

          <div className="border-t border-border pt-2 mt-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-text-primary">Total Charges</span>
            <span className="text-sm font-semibold font-mono font-tabular text-warning">
              ₹{results.totalCharges.toFixed(2)}
            </span>
          </div>
        </div>

        {/* P&L Summary */}
        <div className={`rounded-lg p-4 border ${isProfit ? 'border-positive/20 bg-positive-subtle/30' : 'border-negative/20 bg-negative-subtle/30'}`}>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium block">
                Gross P&L
              </span>
              <span className={`text-lg font-semibold font-mono font-tabular ${results.grossPnL >= 0 ? 'text-profit' : 'text-loss'}`}>
                {results.grossPnL >= 0 ? '+' : ''}₹{results.grossPnL.toLocaleString('en-IN')}
              </span>
            </div>
            <div>
              <span className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium block">
                Net P&L
              </span>
              <span className={`text-lg font-bold font-mono font-tabular ${isProfit ? 'text-profit' : 'text-loss'}`}>
                {isProfit ? '+' : ''}₹{results.netPnL.toLocaleString('en-IN')}
              </span>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-border/50 flex items-center gap-4">
            <div className="flex items-center gap-1">
              <Percent className="h-3 w-3 text-text-tertiary" />
              <span className="text-xs text-text-secondary">Effective Charge:</span>
              <span className="text-xs font-mono font-tabular text-warning">{results.effectiveCharge}%</span>
            </div>
            <div className="flex items-center gap-1">
              <IndianRupee className="h-3 w-3 text-text-tertiary" />
              <span className="text-xs text-text-secondary">Turnover:</span>
              <span className="text-xs font-mono font-tabular text-text-primary">
                ₹{results.turnover.toLocaleString('en-IN')}
              </span>
            </div>
          </div>
        </div>

        {/* Tax Section */}
        <div className="rounded-lg bg-surface p-4">
          <h4 className="text-[10px] uppercase tracking-wider text-text-tertiary font-semibold mb-3">
            Tax Implications
          </h4>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg bg-bg p-3">
              <div className="flex items-center gap-1 mb-1">
                <span className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium">
                  STCG (20%)
                </span>
              </div>
              <p className="text-sm font-semibold font-mono font-tabular text-warning">
                ₹{results.stcg.toLocaleString('en-IN')}
              </p>
              <p className="text-[10px] text-text-tertiary mt-0.5">
                Holding &lt; 1 year
              </p>
            </div>
            <div className="rounded-lg bg-bg p-3">
              <div className="flex items-center gap-1 mb-1">
                <span className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium">
                  LTCG (12.5%)
                </span>
              </div>
              <p className="text-sm font-semibold font-mono font-tabular text-warning">
                ₹{results.ltcg.toLocaleString('en-IN')}
              </p>
              <p className="text-[10px] text-text-tertiary mt-0.5">
                Exempt up to ₹{(results.ltcgExemption / 100000).toFixed(2)}L
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
