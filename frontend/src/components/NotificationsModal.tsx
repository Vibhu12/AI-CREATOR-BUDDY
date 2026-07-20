import { useEffect, useState, useCallback } from 'react';
import {
  Modal, View, Text, StyleSheet, Pressable, ScrollView,
  ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius } from '@/src/theme/tokens';
import { api } from '@/src/services/api';

const KIND_META: Record<string, { icon: any; color: string; bg: string }> = {
  viral:       { icon: 'flame',                color: colors.brand,    bg: colors.brandTertiary },
  opportunity: { icon: 'compass',              color: colors.success,  bg: 'rgba(69,201,122,0.12)' },
  insight:     { icon: 'sparkles',             color: '#7FB3FF',       bg: 'rgba(127,179,255,0.12)' },
  warning:     { icon: 'warning',              color: colors.warning,  bg: 'rgba(255,178,36,0.12)' },
  revenue:     { icon: 'cash',                 color: colors.success,  bg: 'rgba(69,201,122,0.12)' },
  streak:      { icon: 'trophy',               color: colors.brand,    bg: colors.brandTertiary },
};

function relativeTime(iso: string): string {
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function NotificationsModal({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const [items, setItems] = useState<any[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.notifications();
      setItems(r.items);
      setUnread(r.unread);
    } catch (e) { console.warn(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (visible) load(); }, [visible, load]);

  const markOne = async (id: string) => {
    setItems(prev => prev.map(i => i.id === id ? { ...i, read: true } : i));
    setUnread(u => Math.max(0, u - 1));
    try { await api.markNotification(id); } catch {}
  };

  const markAll = async () => {
    setItems(prev => prev.map(i => ({ ...i, read: true })));
    setUnread(0);
    try { await api.markAllNotifications(); } catch {}
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType={Platform.OS === 'ios' ? 'slide' : 'fade'}
      onRequestClose={onClose}
      testID="notifications-modal"
    >
      <View style={styles.overlay}>
        <Pressable style={styles.overlayTap} onPress={onClose} />
        <View style={styles.sheet}>
          <SafeAreaView edges={['bottom']}>
            <View style={styles.grabber} />
            <View style={styles.header}>
              <View>
                <Text style={styles.title}>Notifications</Text>
                <Text style={styles.sub}>{unread} unread</Text>
              </View>
              <View style={{ flexDirection: 'row', gap: spacing.sm }}>
                {unread > 0 && (
                  <Pressable onPress={markAll} style={styles.markAllBtn} testID="notifications-mark-all">
                    <Text style={styles.markAllText}>Mark all read</Text>
                  </Pressable>
                )}
                <Pressable onPress={onClose} style={styles.closeBtn} testID="notifications-close">
                  <Ionicons name="close" size={18} color={colors.onSurface} />
                </Pressable>
              </View>
            </View>

            {loading && items.length === 0
              ? <View style={styles.loading}><ActivityIndicator color={colors.brand} /></View>
              : (
                <ScrollView style={styles.list} contentContainerStyle={{ paddingBottom: spacing.md }}>
                  {items.length === 0 && (
                    <View style={styles.empty}>
                      <Ionicons name="notifications-off-outline" size={32} color={colors.onSurfaceTertiary} />
                      <Text style={styles.emptyText}>All caught up</Text>
                    </View>
                  )}
                  {items.map(n => {
                    const meta = KIND_META[n.kind] ?? KIND_META.insight;
                    return (
                      <Pressable
                        key={n.id}
                        onPress={() => markOne(n.id)}
                        style={[styles.row, !n.read && styles.rowUnread]}
                        testID={`notification-${n.id}`}
                      >
                        <View style={[styles.icon, { backgroundColor: meta.bg }]}>
                          <Ionicons name={meta.icon} size={16} color={meta.color} />
                        </View>
                        <View style={{ flex: 1 }}>
                          <View style={styles.rowHead}>
                            <Text style={styles.rowTitle} numberOfLines={1}>{n.title}</Text>
                            <Text style={styles.rowTime}>{relativeTime(n.at)}</Text>
                          </View>
                          <Text style={styles.rowBody} numberOfLines={2}>{n.body}</Text>
                        </View>
                        {!n.read && <View style={styles.unreadDot} />}
                      </Pressable>
                    );
                  })}
                </ScrollView>
              )
            }
          </SafeAreaView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  overlayTap: { flex: 1 },
  sheet: {
    backgroundColor: colors.surfaceSecondary,
    borderTopLeftRadius: 24, borderTopRightRadius: 24,
    maxHeight: '85%',
    borderTopWidth: StyleSheet.hairlineWidth, borderColor: colors.borderStrong,
  },
  grabber: {
    width: 36, height: 4, borderRadius: 2,
    backgroundColor: colors.surfaceTertiary,
    alignSelf: 'center', marginTop: spacing.sm,
  },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: spacing.lg, paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider,
  },
  title: { color: colors.onSurface, fontSize: 18, fontWeight: '600', letterSpacing: -0.3 },
  sub: { color: colors.onSurfaceTertiary, fontSize: 11, letterSpacing: 0.6, marginTop: 2, fontWeight: '600' },
  markAllBtn: { paddingHorizontal: 10, paddingVertical: 8, borderRadius: radius.pill, backgroundColor: colors.brandTertiary },
  markAllText: { color: colors.brand, fontSize: 11, fontWeight: '700' },
  closeBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: colors.surfaceTertiary,
    alignItems: 'center', justifyContent: 'center',
  },

  list: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm },
  loading: { paddingVertical: spacing.xxl, alignItems: 'center' },

  row: {
    flexDirection: 'row', alignItems: 'flex-start', gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider,
  },
  rowUnread: { backgroundColor: 'rgba(227,167,47,0.04)' },
  icon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  rowHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: spacing.sm },
  rowTitle: { color: colors.onSurface, fontSize: 13, fontWeight: '600', flex: 1 },
  rowTime: { color: colors.onSurfaceTertiary, fontSize: 10, fontWeight: '500' },
  rowBody: { color: colors.onSurfaceSecondary, fontSize: 12, marginTop: 4, lineHeight: 17 },
  unreadDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.brand, marginTop: 12 },

  empty: { alignItems: 'center', paddingVertical: spacing.xxxl, gap: spacing.sm },
  emptyText: { color: colors.onSurfaceTertiary, fontSize: 13 },
});
