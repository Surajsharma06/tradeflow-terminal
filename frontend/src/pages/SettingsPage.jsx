import { useEffect, useState, useCallback } from 'react';
import {
  Settings,
  AlertTriangle,
  ShieldAlert,
  Key,
  Sliders,
  MessageCircle,
  Save,
  Eye,
  EyeOff,
  ToggleLeft,
  ToggleRight,
  X,
  CheckCircle2,
  Info,
} from 'lucide-react';

// ═══════════════════════════════════════════════════════
// Live Mode Confirmation Modal
// ═══════════════════════════════════════════════════════

function LiveModeModal({ onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onCancel}
      />
      {/* Modal */}
      <div className="relative glass-card-elevated p-6 max-w-md w-full animate-[bounce-in_0.4s_cubic-bezier(0.68,-0.55,0.265,1.55)]">
        {/* Close button */}
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 text-text-muted hover:text-text-secondary transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Warning icon */}
        <div className="flex justify-center mb-4">
          <div className="w-16 h-16 rounded-2xl bg-negative-subtle flex items-center justify-center">
            <ShieldAlert className="w-8 h-8 text-negative" />
          </div>
        </div>

        <h3 className="text-lg font-bold text-text-primary text-center mb-2">
          Switch to Live Trading?
        </h3>

        <p className="text-sm text-text-secondary text-center mb-4 leading-relaxed">
          You are about to enable <span className="text-negative font-bold">LIVE TRADING MODE</span>. 
          This will execute real orders with real money through your connected broker.
        </p>

        <div className="bg-negative-subtle rounded-lg p-3 mb-5 border border-negative/20">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-negative shrink-0 mt-0.5" />
            <div className="text-xs text-negative/90 leading-relaxed">
              <strong>WARNING:</strong> Algorithmic trading carries substantial
              risk of financial loss. Ensure your strategies are thoroughly
              backtested. Past performance does not guarantee future results.
              The developers are not liable for any trading losses.
            </div>
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2.5 rounded-lg bg-surface border border-border text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-surface-hover transition-all"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 px-4 py-2.5 rounded-lg bg-negative text-white text-sm font-bold hover:bg-negative-strong transition-all shadow-lg shadow-negative/20"
          >
            Enable Live Trading
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
// Toast Notification
// ═══════════════════════════════════════════════════════

function Toast({ message, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-[slide-up_0.4s_cubic-bezier(0.16,1,0.3,1)]">
      <div className="glass-card-elevated px-4 py-3 flex items-center gap-2 shadow-xl">
        <CheckCircle2 className="w-4 h-4 text-positive" />
        <span className="text-sm text-text-primary font-medium">{message}</span>
        <button
          onClick={onClose}
          className="ml-2 text-text-muted hover:text-text-secondary transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
// Password Input with Toggle
// ═══════════════════════════════════════════════════════

function PasswordInput({ label, placeholder, value, onChange }) {
  const [visible, setVisible] = useState(false);

  return (
    <div>
      <label className="text-xs text-text-secondary mb-1.5 block font-medium">
        {label}
      </label>
      <div className="relative">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full bg-surface border border-border rounded-lg px-3 py-2.5 pr-10 text-sm text-text-primary font-mono placeholder:text-text-muted focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition-all"
        />
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors"
        >
          {visible ? (
            <EyeOff className="w-4 h-4" />
          ) : (
            <Eye className="w-4 h-4" />
          )}
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
// Settings Page
// ═══════════════════════════════════════════════════════

export default function SettingsPage() {
  const [mounted, setMounted] = useState(false);
  const [showLiveModal, setShowLiveModal] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const [toastMsg, setToastMsg] = useState('');

  // Trading Mode
  const [isLive, setIsLive] = useState(false);

  // API Keys
  const [apiKeys, setApiKeys] = useState({
    zerodha: '',
    upstox: '',
    angelOne: '',
    fyers: '',
    alpaca: '',
  });

  // Trading Parameters
  const [params, setParams] = useState({
    riskPercent: 1.5,
    maxPositions: 5,
    signalThreshold: 70,
  });

  // Telegram
  const [telegram, setTelegram] = useState({
    botToken: '',
    chatId: '',
  });

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50);
    return () => clearTimeout(t);
  }, []);

  const stagger = (index) => ({
    opacity: mounted ? 1 : 0,
    transform: mounted ? 'translateY(0px)' : 'translateY(20px)',
    transition: `all 0.5s cubic-bezier(0.16, 1, 0.3, 1) ${index * 0.08}s`,
  });

  const handleToggleLive = useCallback(() => {
    if (!isLive) {
      setShowLiveModal(true);
    } else {
      setIsLive(false);
      setToastMsg('Switched to Paper Trading mode');
      setShowToast(true);
    }
  }, [isLive]);

  const handleConfirmLive = useCallback(() => {
    setIsLive(true);
    setShowLiveModal(false);
    setToastMsg('⚠️ Live Trading mode enabled');
    setShowToast(true);
  }, []);

  const handleSave = useCallback(() => {
    setToastMsg('Settings saved successfully');
    setShowToast(true);
  }, []);

  const brokers = [
    { key: 'zerodha', label: 'Zerodha API Key', placeholder: 'kite_api_key_xxxxx' },
    { key: 'upstox', label: 'Upstox API Key', placeholder: 'upstox_api_key_xxxxx' },
    { key: 'angelOne', label: 'Angel One API Key', placeholder: 'angel_api_key_xxxxx' },
    { key: 'fyers', label: 'Fyers API Key', placeholder: 'fyers_app_id_xxxxx' },
    { key: 'alpaca', label: 'Alpaca API Key', placeholder: 'PKXXXXXXXXXXXXX' },
  ];

  return (
    <div className="p-4 lg:p-6 min-h-screen max-w-4xl mx-auto">
      {/* ── Header ── */}
      <div style={stagger(0)} className="mb-6">
        <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
          <Settings className="w-6 h-6 text-accent" />
          Settings
        </h1>
        <p className="text-xs text-text-tertiary mt-0.5">
          Configure API connections, trading parameters, and notifications
        </p>
      </div>

      {/* ── SEBI Warning Banner ── */}
      <div style={stagger(1)} className="mb-6">
        <div className="rounded-xl border border-negative/30 bg-negative-subtle p-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-negative/20 flex items-center justify-center shrink-0">
              <ShieldAlert className="w-5 h-5 text-negative" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-negative mb-1">
                SEBI Compliance Notice
              </h3>
              <p className="text-xs text-negative/80 leading-relaxed">
                Algorithmic trading in India is regulated by SEBI. Retail traders
                must use SEBI-registered brokers with proper API access. Ensure
                you comply with SEBI circular SEBI/HO/MRD/DP/CIR/P/2018/73.
                Unauthorized algo trading may attract penalties. This platform is
                for <strong>educational and research purposes only</strong>.
                Users are solely responsible for compliance with applicable
                regulations and any financial losses incurred.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Paper / Live Toggle ── */}
      <div style={stagger(2)} className="mb-6">
        <div className="glass-card p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  isLive
                    ? 'bg-negative-subtle'
                    : 'bg-positive-subtle'
                }`}
              >
                {isLive ? (
                  <AlertTriangle className="w-5 h-5 text-negative" />
                ) : (
                  <Info className="w-5 h-5 text-positive" />
                )}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-text-primary">
                  Trading Mode
                </h3>
                <p className="text-xs text-text-tertiary">
                  {isLive
                    ? 'LIVE — Real orders will be executed'
                    : 'PAPER — Simulated trading, no real orders'}
                </p>
              </div>
            </div>

            <button
              onClick={handleToggleLive}
              className="flex items-center gap-2 group"
            >
              <span
                className={`text-xs font-bold uppercase tracking-wider ${
                  isLive ? 'text-negative' : 'text-positive'
                }`}
              >
                {isLive ? 'LIVE' : 'PAPER'}
              </span>
              {isLive ? (
                <ToggleRight className="w-10 h-10 text-negative transition-colors" />
              ) : (
                <ToggleLeft className="w-10 h-10 text-positive transition-colors" />
              )}
            </button>
          </div>

          {isLive && (
            <div className="mt-3 px-3 py-2 rounded-lg bg-negative-subtle border border-negative/20">
              <div className="flex items-center gap-2">
                <div className="status-dot status-dot-live !bg-negative" />
                <span className="text-xs text-negative font-semibold">
                  Live trading is active — real orders will be placed through
                  your broker
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── API Keys ── */}
      <div style={stagger(3)} className="mb-6">
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-5">
            <Key className="w-5 h-5 text-gold" />
            <h3 className="text-sm font-semibold text-text-primary">
              Broker API Keys
            </h3>
            <span className="text-[10px] text-text-muted bg-surface-hover px-2 py-0.5 rounded-full">
              Encrypted at rest
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {brokers.map((broker) => (
              <PasswordInput
                key={broker.key}
                label={broker.label}
                placeholder={broker.placeholder}
                value={apiKeys[broker.key]}
                onChange={(val) =>
                  setApiKeys((prev) => ({ ...prev, [broker.key]: val }))
                }
              />
            ))}
          </div>

          <p className="mt-4 text-[10px] text-text-muted flex items-center gap-1">
            <Info className="w-3 h-3" />
            API keys are stored locally and never sent to third-party servers.
            Use read-only keys where possible.
          </p>
        </div>
      </div>

      {/* ── Trading Parameters ── */}
      <div style={stagger(4)} className="mb-6">
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-5">
            <Sliders className="w-5 h-5 text-accent" />
            <h3 className="text-sm font-semibold text-text-primary">
              Trading Parameters
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Risk Per Trade */}
            <div>
              <label className="text-xs text-text-secondary mb-1.5 block font-medium">
                Risk Per Trade (%)
              </label>
              <input
                type="number"
                step="0.1"
                min="0.1"
                max="10"
                value={params.riskPercent}
                onChange={(e) =>
                  setParams((p) => ({
                    ...p,
                    riskPercent: parseFloat(e.target.value) || 0,
                  }))
                }
                className="w-full bg-surface border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary font-tabular focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition-all"
              />
              <p className="mt-1 text-[10px] text-text-muted">
                Max capital risked per trade: {params.riskPercent}%
              </p>
            </div>

            {/* Max Positions */}
            <div>
              <label className="text-xs text-text-secondary mb-1.5 block font-medium">
                Max Open Positions
              </label>
              <input
                type="number"
                min="1"
                max="20"
                value={params.maxPositions}
                onChange={(e) =>
                  setParams((p) => ({
                    ...p,
                    maxPositions: parseInt(e.target.value) || 1,
                  }))
                }
                className="w-full bg-surface border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary font-tabular focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition-all"
              />
              <p className="mt-1 text-[10px] text-text-muted">
                Simultaneous open positions limit
              </p>
            </div>

            {/* Signal Threshold Slider */}
            <div>
              <label className="text-xs text-text-secondary mb-1.5 block font-medium">
                Signal Threshold
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={params.signalThreshold}
                  onChange={(e) =>
                    setParams((p) => ({
                      ...p,
                      signalThreshold: parseInt(e.target.value),
                    }))
                  }
                  className="flex-1 h-2 bg-surface rounded-full appearance-none cursor-pointer accent-accent"
                />
                <span className="text-sm font-bold font-tabular text-accent w-10 text-right">
                  {params.signalThreshold}
                </span>
              </div>
              <div className="flex justify-between mt-1">
                <span className="text-[10px] text-text-muted">Conservative</span>
                <span className="text-[10px] text-text-muted">Aggressive</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Telegram Integration ── */}
      <div style={stagger(5)} className="mb-6">
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-5">
            <MessageCircle className="w-5 h-5 text-info" />
            <h3 className="text-sm font-semibold text-text-primary">
              Telegram Notifications
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <PasswordInput
              label="Bot Token"
              placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
              value={telegram.botToken}
              onChange={(val) =>
                setTelegram((prev) => ({ ...prev, botToken: val }))
              }
            />
            <div>
              <label className="text-xs text-text-secondary mb-1.5 block font-medium">
                Chat ID
              </label>
              <input
                type="text"
                value={telegram.chatId}
                onChange={(e) =>
                  setTelegram((prev) => ({ ...prev, chatId: e.target.value }))
                }
                placeholder="-1001234567890"
                className="w-full bg-surface border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary font-mono placeholder:text-text-muted focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition-all"
              />
            </div>
          </div>

          <p className="mt-4 text-[10px] text-text-muted flex items-center gap-1">
            <Info className="w-3 h-3" />
            Receive real-time signal alerts, trade confirmations, and daily PnL
            summaries on Telegram.
          </p>
        </div>
      </div>

      {/* ── Save Button ── */}
      <div style={stagger(6)} className="flex justify-end">
        <button
          onClick={handleSave}
          className="flex items-center gap-2 px-8 py-3 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-semibold transition-all shadow-lg shadow-accent/20 hover:shadow-accent/40 hover:scale-[1.02] active:scale-[0.98]"
        >
          <Save className="w-4 h-4" />
          Save Settings
        </button>
      </div>

      {/* ── Modals & Toasts ── */}
      {showLiveModal && (
        <LiveModeModal
          onConfirm={handleConfirmLive}
          onCancel={() => setShowLiveModal(false)}
        />
      )}

      {showToast && (
        <Toast message={toastMsg} onClose={() => setShowToast(false)} />
      )}
    </div>
  );
}
