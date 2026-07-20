import { useState } from 'react';
import {
  Modal, View, Text, StyleSheet, Pressable, TextInput, ScrollView,
  ActivityIndicator, Platform, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, platformMeta } from '@/src/theme/tokens';
import { api } from '@/src/services/api';

const PLATFORMS = ['youtube', 'instagram', 'tiktok', 'course', 'newsletter', 'podcast', 'saas'];

export function AddAssetModal({
  visible,
  onClose,
  onCreated,
}: {
  visible: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState('');
  const [platform, setPlatform] = useState('youtube');
  const [category, setCategory] = useState('');
  const [revenue, setRevenue] = useState('');
  const [followers, setFollowers] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const reset = () => {
    setName(''); setPlatform('youtube'); setCategory('');
    setRevenue(''); setFollowers(''); setErr(null);
  };

  const submit = async () => {
    if (!name.trim()) { setErr('Give your asset a name'); return; }
    setBusy(true); setErr(null);
    try {
      await api.createAsset({
        name: name.trim(),
        platform,
        category: category.trim() || 'General',
        revenue_mtd: parseFloat(revenue) || 0,
        profit_mtd: (parseFloat(revenue) || 0) * 0.75,
        followers: parseInt(followers) || 0,
        ai_score: 70,
        trend: [65, 67, 68, 70, 71, 72, 70],
      });
      reset();
      onCreated();
      onClose();
    } catch {
      setErr('Failed to create — try again');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType={Platform.OS === 'ios' ? 'slide' : 'fade'}
      onRequestClose={onClose}
      testID="add-asset-modal"
    >
      <View style={styles.overlay}>
        <Pressable style={styles.overlayTap} onPress={onClose} />
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.sheetWrap}
        >
          <View style={styles.sheet}>
            <SafeAreaView edges={['bottom']}>
              <View style={styles.grabber} />
              <View style={styles.header}>
                <View>
                  <Text style={styles.kicker}>NEW ASSET</Text>
                  <Text style={styles.title}>Add a business asset</Text>
                </View>
                <Pressable onPress={onClose} style={styles.closeBtn} testID="add-asset-close">
                  <Ionicons name="close" size={18} color={colors.onSurface} />
                </Pressable>
              </View>

              <ScrollView
                style={styles.form}
                contentContainerStyle={{ paddingBottom: spacing.md }}
                keyboardShouldPersistTaps="handled"
              >
                <Text style={styles.label}>PLATFORM</Text>
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.chipsRow}
                >
                  {PLATFORMS.map(p => {
                    const meta = platformMeta[p] ?? { label: p, color: colors.brand };
                    const active = platform === p;
                    return (
                      <Pressable
                        key={p}
                        onPress={() => setPlatform(p)}
                        style={[
                          styles.chip,
                          active && { backgroundColor: `${meta.color}22`, borderColor: meta.color },
                        ]}
                        testID={`platform-chip-${p}`}
                      >
                        <Text style={[styles.chipText, active && { color: meta.color, fontWeight: '700' }]}>
                          {meta.label}
                        </Text>
                      </Pressable>
                    );
                  })}
                </ScrollView>

                <Text style={styles.label}>NAME</Text>
                <TextInput
                  value={name}
                  onChangeText={setName}
                  placeholder="My YouTube channel"
                  placeholderTextColor={colors.onSurfaceTertiary}
                  style={styles.input}
                  testID="asset-name-input"
                />

                <Text style={styles.label}>CATEGORY</Text>
                <TextInput
                  value={category}
                  onChangeText={setCategory}
                  placeholder="Long-form video"
                  placeholderTextColor={colors.onSurfaceTertiary}
                  style={styles.input}
                  testID="asset-category-input"
                />

                <View style={styles.numRow}>
                  <View style={styles.numCol}>
                    <Text style={styles.label}>REVENUE MTD ($)</Text>
                    <TextInput
                      value={revenue}
                      onChangeText={setRevenue}
                      placeholder="0"
                      placeholderTextColor={colors.onSurfaceTertiary}
                      keyboardType="numeric"
                      style={styles.input}
                      testID="asset-revenue-input"
                    />
                  </View>
                  <View style={styles.numCol}>
                    <Text style={styles.label}>FOLLOWERS</Text>
                    <TextInput
                      value={followers}
                      onChangeText={setFollowers}
                      placeholder="0"
                      placeholderTextColor={colors.onSurfaceTertiary}
                      keyboardType="numeric"
                      style={styles.input}
                      testID="asset-followers-input"
                    />
                  </View>
                </View>

                {err && <Text style={styles.err}>{err}</Text>}

                <Pressable
                  onPress={submit}
                  disabled={busy}
                  style={[styles.submitBtn, busy && { opacity: 0.6 }]}
                  testID="asset-submit-btn"
                >
                  {busy
                    ? <ActivityIndicator color={colors.onBrandPrimary} />
                    : <>
                        <Ionicons name="add-circle" size={16} color={colors.onBrandPrimary} />
                        <Text style={styles.submitText}>Add asset</Text>
                      </>
                  }
                </Pressable>
              </ScrollView>
            </SafeAreaView>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  overlayTap: { flex: 1 },
  sheetWrap: { width: '100%' },
  sheet: {
    backgroundColor: colors.surfaceSecondary,
    borderTopLeftRadius: 24, borderTopRightRadius: 24,
    borderTopWidth: StyleSheet.hairlineWidth, borderColor: colors.borderStrong,
    maxHeight: '90%',
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
  kicker: { color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1.4, fontWeight: '700' },
  title: { color: colors.onSurface, fontSize: 18, fontWeight: '600', marginTop: 2, letterSpacing: -0.3 },
  closeBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: colors.surfaceTertiary,
    alignItems: 'center', justifyContent: 'center',
  },

  form: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
  label: {
    color: colors.onSurfaceTertiary, fontSize: 10, letterSpacing: 1.2,
    fontWeight: '700', marginTop: spacing.md, marginBottom: spacing.sm,
  },

  chipsRow: { gap: spacing.sm, paddingRight: spacing.lg },
  chip: {
    paddingHorizontal: spacing.md, paddingVertical: 8, borderRadius: radius.pill,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
    backgroundColor: colors.surfaceTertiary,
    flexShrink: 0,
  },
  chipText: { color: colors.onSurfaceSecondary, fontSize: 12, fontWeight: '600' },

  input: {
    color: colors.onSurface, fontSize: 14,
    backgroundColor: colors.surfaceTertiary,
    borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: 12,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },

  numRow: { flexDirection: 'row', gap: spacing.md },
  numCol: { flex: 1 },

  err: { color: colors.error, fontSize: 12, marginTop: spacing.md },

  submitBtn: {
    marginTop: spacing.lg,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm,
    backgroundColor: colors.brand,
    borderRadius: radius.md, paddingVertical: 14,
  },
  submitText: { color: colors.onBrandPrimary, fontSize: 14, fontWeight: '700' },
});
