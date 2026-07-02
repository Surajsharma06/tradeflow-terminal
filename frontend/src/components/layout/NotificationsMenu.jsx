import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bell, Zap, Shield, Info, CheckCheck } from 'lucide-react';
import useNotificationStore from '../../stores/notificationStore';

const TYPE_ICON = {
  signal: { icon: Zap,    cls: 'text-accent bg-accent-subtle' },
  risk:   { icon: Shield, cls: 'text-warning bg-warning-subtle' },
  system: { icon: Info,   cls: 'text-text-secondary bg-surface-hover' },
};

function timeAgo(ts) {
  const mins = Math.floor((Date.now() - ts) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function NotificationItem({ notif, isRead, onRead }) {
  const { icon: Icon, cls } = TYPE_ICON[notif.type] ?? TYPE_ICON.system;
  return (
    <button
      onClick={() => onRead(notif.id)}
      className={`w-full flex items-start gap-3 px-3 py-2.5 text-left transition-colors hover:bg-surface-hover cursor-pointer ${
        isRead ? 'opacity-60' : ''
      }`}
    >
      <span className={`flex items-center justify-center w-7 h-7 rounded-md flex-shrink-0 mt-0.5 ${cls}`}>
        <Icon size={13} />
      </span>
      <span className="flex flex-col gap-0.5 min-w-0">
        <span className="text-xs font-semibold text-text-primary leading-snug">{notif.title}</span>
        <span className="text-[11px] text-text-secondary leading-snug">{notif.body}</span>
        <span className="text-[10px] text-text-tertiary">{timeAgo(notif.time)}</span>
      </span>
      {!isRead && (
        <span className="ml-auto mt-1 w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" aria-hidden />
      )}
    </button>
  );
}

export default function NotificationsMenu({ open, onClose, anchorRef }) {
  const menuRef = useRef(null);
  const { notifications, readIds, markRead, markAllRead } = useNotificationStore();
  const unread = notifications.filter((n) => !readIds.includes(n.id)).length;

  // Close on outside click + Escape
  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (
        menuRef.current && !menuRef.current.contains(e.target) &&
        anchorRef?.current && !anchorRef.current.contains(e.target)
      ) onClose();
    };
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose, anchorRef]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={menuRef}
          role="menu"
          aria-label="Notifications"
          initial={{ opacity: 0, y: -6, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -6, scale: 0.98 }}
          transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
          className="absolute right-0 top-full mt-2 w-[320px] max-w-[calc(100vw-24px)] rounded-xl border border-border bg-surface-elevated shadow-elevated z-[70] overflow-hidden"
        >
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-border/60">
            <div className="flex items-center gap-2">
              <Bell size={13} className="text-text-secondary" />
              <span className="text-xs font-bold text-text-primary uppercase tracking-wider">Notifications</span>
              {unread > 0 && (
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-accent text-white">{unread}</span>
              )}
            </div>
            {unread > 0 && (
              <button
                onClick={markAllRead}
                className="flex items-center gap-1 text-[10px] font-semibold text-accent hover:text-accent-hover transition-colors cursor-pointer"
              >
                <CheckCheck size={12} /> Mark all read
              </button>
            )}
          </div>

          <div className="max-h-[340px] overflow-y-auto divide-y divide-border/40">
            {notifications.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-10 text-text-tertiary">
                <Bell size={20} />
                <span className="text-xs">No notifications yet</span>
              </div>
            ) : (
              notifications.map((n) => (
                <NotificationItem
                  key={n.id}
                  notif={n}
                  isRead={readIds.includes(n.id)}
                  onRead={markRead}
                />
              ))
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
