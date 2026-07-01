/**
 * WebSocket Manager
 * Handles connection, auto-reconnect with exponential backoff,
 * heartbeat pings, and message routing.
 */

const WS_STATES = {
  CONNECTING: 'CONNECTING',
  CONNECTED: 'CONNECTED',
  DISCONNECTED: 'DISCONNECTED',
  RECONNECTING: 'RECONNECTING',
  ERROR: 'ERROR',
};

class WebSocketManager {
  constructor(url = 'ws://localhost:8000/api/v1/ws/prices') {
    this.url = url;
    this.ws = null;
    this.status = WS_STATES.DISCONNECTED;

    // Reconnection
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 50;
    this.baseReconnectDelay = 1000; // 1s
    this.maxReconnectDelay = 8000;  // 8s
    this.reconnectTimer = null;

    // Heartbeat
    this.heartbeatInterval = null;
    this.heartbeatTimeout = null;
    this.heartbeatIntervalMs = 30000; // 30s
    this.heartbeatTimeoutMs = 10000;  // 10s wait for pong

    // Handlers
    this.messageHandlers = new Map();
    this.statusChangeHandlers = new Set();
    this.errorHandlers = new Set();

    // Metrics
    this.messageCount = 0;
    this.lastMessageTime = null;
    this.connectedAt = null;
    this.totalReconnects = 0;

    // Bind methods
    this._onOpen = this._onOpen.bind(this);
    this._onMessage = this._onMessage.bind(this);
    this._onClose = this._onClose.bind(this);
    this._onError = this._onError.bind(this);
  }

  // ── Connection ───────────────────────────────────────────────────────

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      console.log('[WS] Already connected or connecting');
      return;
    }

    this._setStatus(WS_STATES.CONNECTING);

    try {
      this.ws = new WebSocket(this.url);
      this.ws.onopen = this._onOpen;
      this.ws.onmessage = this._onMessage;
      this.ws.onclose = this._onClose;
      this.ws.onerror = this._onError;
    } catch (err) {
      console.error('[WS] Connection error:', err);
      this._setStatus(WS_STATES.ERROR);
      this._scheduleReconnect();
    }
  }

  disconnect() {
    this._clearTimers();
    this.reconnectAttempts = 0;

    if (this.ws) {
      // Prevent auto-reconnect on intentional close
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this._setStatus(WS_STATES.DISCONNECTED);
    console.log('[WS] Disconnected');
  }

  // ── Message Sending ──────────────────────────────────────────────────

  send(data) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('[WS] Cannot send — not connected');
      return false;
    }

    try {
      const payload = typeof data === 'string' ? data : JSON.stringify(data);
      this.ws.send(payload);
      return true;
    } catch (err) {
      console.error('[WS] Send error:', err);
      return false;
    }
  }

  subscribe(channels) {
    return this.send({ type: 'subscribe', channels });
  }

  unsubscribe(channels) {
    return this.send({ type: 'unsubscribe', channels });
  }

  // ── Handler Registration ─────────────────────────────────────────────

  /**
   * Register a message handler for a specific message type.
   * @param {string} type — message type to handle (e.g., 'price_update', 'signal')
   * @param {Function} handler — callback(data, rawMessage)
   * @returns {Function} — unsubscribe function
   */
  onMessage(type, handler) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type).add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(type);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.messageHandlers.delete(type);
        }
      }
    };
  }

  /**
   * Register a catch-all handler for all messages.
   * @param {Function} handler — callback(parsedMessage)
   * @returns {Function} — unsubscribe function
   */
  onAnyMessage(handler) {
    return this.onMessage('*', handler);
  }

  /**
   * Register a status change handler.
   * @param {Function} handler — callback(newStatus, oldStatus)
   * @returns {Function} — unsubscribe function
   */
  onStatusChange(handler) {
    this.statusChangeHandlers.add(handler);
    return () => this.statusChangeHandlers.delete(handler);
  }

  /**
   * Register an error handler.
   * @param {Function} handler — callback(error)
   * @returns {Function} — unsubscribe function
   */
  onError(handler) {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  // ── Internal Event Handlers ──────────────────────────────────────────

  _onOpen() {
    this.reconnectAttempts = 0;
    this.connectedAt = Date.now();
    this._setStatus(WS_STATES.CONNECTED);
    this._startHeartbeat();

    console.log(
      `%c[WS] ✓ Connected to ${this.url}`,
      'color: #34d399; font-weight: bold;'
    );
  }

  _onMessage(event) {
    this.messageCount++;
    this.lastMessageTime = Date.now();

    // Reset heartbeat timeout on any message
    this._resetHeartbeatTimeout();

    try {
      const message = JSON.parse(event.data);

      // Handle pong
      if (message.type === 'pong') {
        return;
      }

      // Route to type-specific handlers
      const type = message.type || message.event || 'unknown';
      const handlers = this.messageHandlers.get(type);
      if (handlers) {
        handlers.forEach((handler) => {
          try {
            handler(message.data || message, message);
          } catch (err) {
            console.error(`[WS] Handler error for "${type}":`, err);
          }
        });
      }

      // Route to catch-all handlers
      const catchAllHandlers = this.messageHandlers.get('*');
      if (catchAllHandlers) {
        catchAllHandlers.forEach((handler) => {
          try {
            handler(message);
          } catch (err) {
            console.error('[WS] Catch-all handler error:', err);
          }
        });
      }
    } catch {
      // Non-JSON message — treat as raw text
      const catchAllHandlers = this.messageHandlers.get('*');
      if (catchAllHandlers) {
        catchAllHandlers.forEach((handler) => handler({ raw: event.data }));
      }
    }
  }

  _onClose(event) {
    this._clearTimers();

    const wasConnected = this.status === WS_STATES.CONNECTED;
    const reason = event.reason || 'Unknown reason';
    const code = event.code;

    console.log(
      `%c[WS] ✗ Closed (code: ${code}, reason: ${reason})`,
      'color: #f87171; font-weight: bold;'
    );

    // Don't reconnect on normal closure or policy violations
    if (code === 1000 || code === 1008) {
      this._setStatus(WS_STATES.DISCONNECTED);
      return;
    }

    if (wasConnected) {
      this.totalReconnects++;
    }

    this._scheduleReconnect();
  }

  _onError(error) {
    console.error('[WS] Error:', error);
    this._setStatus(WS_STATES.ERROR);

    this.errorHandlers.forEach((handler) => {
      try {
        handler(error);
      } catch (err) {
        console.error('[WS] Error handler threw:', err);
      }
    });
  }

  // ── Reconnection ────────────────────────────────────────────────────

  _scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WS] Max reconnect attempts reached. Giving up.');
      this._setStatus(WS_STATES.DISCONNECTED);
      return;
    }

    this._setStatus(WS_STATES.RECONNECTING);

    // Exponential backoff: 1s, 2s, 4s, 8s, 8s, 8s...
    const delay = Math.min(
      this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts),
      this.maxReconnectDelay
    );

    this.reconnectAttempts++;

    console.log(
      `[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
    );

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  // ── Heartbeat ────────────────────────────────────────────────────────

  _startHeartbeat() {
    this._clearHeartbeat();

    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping', timestamp: Date.now() });

        // Set timeout — if no pong/message received, reconnect
        this.heartbeatTimeout = setTimeout(() => {
          console.warn('[WS] Heartbeat timeout — no response');
          this.ws?.close(4000, 'Heartbeat timeout');
        }, this.heartbeatTimeoutMs);
      }
    }, this.heartbeatIntervalMs);
  }

  _resetHeartbeatTimeout() {
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }

  _clearHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    this._resetHeartbeatTimeout();
  }

  // ── Utilities ────────────────────────────────────────────────────────

  _setStatus(newStatus) {
    const oldStatus = this.status;
    if (oldStatus === newStatus) return;

    this.status = newStatus;

    this.statusChangeHandlers.forEach((handler) => {
      try {
        handler(newStatus, oldStatus);
      } catch (err) {
        console.error('[WS] Status change handler error:', err);
      }
    });
  }

  _clearTimers() {
    this._clearHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  // ── Public Getters ───────────────────────────────────────────────────

  get isConnected() {
    return this.status === WS_STATES.CONNECTED;
  }

  get connectionDuration() {
    if (!this.connectedAt || this.status !== WS_STATES.CONNECTED) return 0;
    return Date.now() - this.connectedAt;
  }

  get metrics() {
    return {
      status: this.status,
      messageCount: this.messageCount,
      lastMessageTime: this.lastMessageTime,
      connectedAt: this.connectedAt,
      connectionDuration: this.connectionDuration,
      reconnectAttempts: this.reconnectAttempts,
      totalReconnects: this.totalReconnects,
    };
  }
}

// ── Singleton Instance ─────────────────────────────────────────────────
const wsManager = new WebSocketManager();

export { WebSocketManager, WS_STATES };
export default wsManager;
