import { useState, useEffect, useCallback, useRef } from 'react';
import wsManager from '../services/websocket';
import useMarketStore from '../stores/marketStore';
import usePortfolioStore from '../stores/portfolioStore';
import useSignalStore from '../stores/signalStore';

/**
 * useWebSocket
 *
 * Custom hook that manages WebSocket lifecycle and routes
 * incoming messages to the appropriate Zustand stores.
 *
 * @param {Object} options
 * @param {boolean} options.autoConnect — connect on mount (default: true)
 * @param {string[]} options.channels — channels to subscribe to
 * @param {Function} options.onMessage — optional callback for all messages
 * @param {Function} options.onStatusChange — optional callback for status changes
 *
 * @returns {{ isConnected, status, lastMessage, sendMessage, connect, disconnect, metrics }}
 */
export default function useWebSocket(options = {}) {
  const {
    autoConnect = true,
    channels = [],
    onMessage: onMessageCallback,
    onStatusChange: onStatusChangeCallback,
  } = options;

  const [isConnected, setIsConnected] = useState(wsManager.isConnected);
  const [status, setStatus] = useState(wsManager.status);
  const [lastMessage, setLastMessage] = useState(null);
  const cleanupRef = useRef([]);

  // ── Zustand actions ──────────────────────────────────────────────────
  const updatePrice = useMarketStore((s) => s.updatePrice);
  const updatePrices = useMarketStore((s) => s.updatePrices);
  const updateIndex = useMarketStore((s) => s.updateIndex);
  const setRegime = useMarketStore((s) => s.setRegime);
  const setVix = useMarketStore((s) => s.setVix);
  const setMarketStatus = useMarketStore((s) => s.setMarketStatus);
  const updatePosition = usePortfolioStore((s) => s.updatePosition);
  const addSignal = useSignalStore((s) => s.addSignal);
  const updateSignal = useSignalStore((s) => s.updateSignal);

  // ── Message Router ───────────────────────────────────────────────────
  useEffect(() => {
    const unsubscribers = [];

    // Price updates — single stock
    unsubscribers.push(
      wsManager.onMessage('price_update', (data) => {
        if (data.symbol && data.ltp !== undefined) {
          updatePrice(data.symbol, {
            ltp: data.ltp,
            change: data.change,
            changePercent: data.changePercent,
            bid: data.bid,
            ask: data.ask,
            volume: data.volume,
            high: data.high,
            low: data.low,
          });
        }
        setLastMessage({ type: 'price_update', data, timestamp: Date.now() });
      })
    );

    // Price updates — batch
    unsubscribers.push(
      wsManager.onMessage('price_batch', (data) => {
        if (data.prices && typeof data.prices === 'object') {
          updatePrices(data.prices);
        }
        setLastMessage({ type: 'price_batch', data, timestamp: Date.now() });
      })
    );

    // Index updates
    unsubscribers.push(
      wsManager.onMessage('index_update', (data) => {
        if (data.index) {
          updateIndex(data.index, {
            value: data.value,
            change: data.change,
            changePercent: data.changePercent,
            high: data.high,
            low: data.low,
          });
        }
        setLastMessage({ type: 'index_update', data, timestamp: Date.now() });
      })
    );

    // Market regime changes
    unsubscribers.push(
      wsManager.onMessage('regime_change', (data) => {
        if (data.regime) {
          setRegime(data.regime, data.confidence);
        }
        setLastMessage({ type: 'regime_change', data, timestamp: Date.now() });
      })
    );

    // VIX updates
    unsubscribers.push(
      wsManager.onMessage('vix_update', (data) => {
        if (data.market && data.value !== undefined) {
          setVix(data.market, data.value);
        }
        setLastMessage({ type: 'vix_update', data, timestamp: Date.now() });
      })
    );

    // Market status
    unsubscribers.push(
      wsManager.onMessage('market_status', (data) => {
        if (data.market) {
          setMarketStatus(data.market, data);
        }
        setLastMessage({ type: 'market_status', data, timestamp: Date.now() });
      })
    );

    // Position updates
    unsubscribers.push(
      wsManager.onMessage('position_update', (data) => {
        if (data.positionId) {
          updatePosition(data.positionId, data);
        }
        setLastMessage({ type: 'position_update', data, timestamp: Date.now() });
      })
    );

    // New signal
    unsubscribers.push(
      wsManager.onMessage('new_signal', (data) => {
        addSignal(data);
        setLastMessage({ type: 'new_signal', data, timestamp: Date.now() });
      })
    );

    // Signal update
    unsubscribers.push(
      wsManager.onMessage('signal_update', (data) => {
        if (data.signalId) {
          updateSignal(data.signalId, data);
        }
        setLastMessage({ type: 'signal_update', data, timestamp: Date.now() });
      })
    );

    // Optional catch-all callback
    if (onMessageCallback) {
      unsubscribers.push(
        wsManager.onAnyMessage((msg) => {
          onMessageCallback(msg);
        })
      );
    }

    cleanupRef.current = unsubscribers;

    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  }, [
    updatePrice,
    updatePrices,
    updateIndex,
    setRegime,
    setVix,
    setMarketStatus,
    updatePosition,
    addSignal,
    updateSignal,
    onMessageCallback,
  ]);

  // ── Status Tracking ──────────────────────────────────────────────────
  useEffect(() => {
    const unsub = wsManager.onStatusChange((newStatus) => {
      setStatus(newStatus);
      setIsConnected(newStatus === 'CONNECTED');
      onStatusChangeCallback?.(newStatus);
    });

    return unsub;
  }, [onStatusChangeCallback]);

  // ── Auto-connect & Cleanup ───────────────────────────────────────────
  useEffect(() => {
    if (autoConnect) {
      wsManager.connect();

      // Subscribe to channels after connection
      if (channels.length > 0) {
        const unsub = wsManager.onStatusChange((newStatus) => {
          if (newStatus === 'CONNECTED') {
            wsManager.subscribe(channels);
          }
        });

        // Subscribe immediately if already connected
        if (wsManager.isConnected) {
          wsManager.subscribe(channels);
        }

        return () => {
          unsub();
          wsManager.unsubscribe(channels);
        };
      }
    }

    return () => {
      // Only disconnect if this is the last consumer
      // In practice, the singleton stays alive across route changes
    };
  }, [autoConnect, channels.join(',')]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Exposed Methods ──────────────────────────────────────────────────
  const sendMessage = useCallback((data) => {
    return wsManager.send(data);
  }, []);

  const connect = useCallback(() => {
    wsManager.connect();
  }, []);

  const disconnect = useCallback(() => {
    wsManager.disconnect();
  }, []);

  return {
    isConnected,
    status,
    lastMessage,
    sendMessage,
    connect,
    disconnect,
    metrics: wsManager.metrics,
  };
}
