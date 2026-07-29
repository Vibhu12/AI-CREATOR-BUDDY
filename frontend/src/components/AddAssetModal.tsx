import { useState, useMemo } from 'react';
import {
  Modal, View, Text, StyleSheet, Pressable, TextInput, ScrollView,
  ActivityIndicator, Platform, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors, spacing, radius, platformMeta } from '@/src/theme/tokens';
import { api } from '@/src/services/api';

const PLATFORMS = ['youtube', 'instagram', 'tiktok', 'course', 'newsletter', 'podcast', 'saas', 'affiliate', 'digital'];

type FieldErrors = {
  name?: string;
  revenue?: string;
  followers?: string;
};

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
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [serverErr, setServerErr] = useState<string | null>(null);

  const reset = () => {
    setName(''); setPlatform('youtube'); setCategory('');
    setRevenue(''); setFollowers('');
    setTouched({}); setServerErr(null);
  };

  const errors: FieldErrors = useMemo(() => {
    const e: FieldErrors = {};
    if (!name.trim()) e.name = 'Name is required';
    else if (name.trim().length < 2) e.name = 'At least 2 characters';
    else if (name.trim().length > 80) e.name = 'Max 80 characters';

    if (revenue.trim()) {
      const n = parseFloat(revenue);
      if (isNaN(n) || n < 0) e.revenue = 'Enter a positive number';
      else if (n > 10_000_000) e.revenue = 'Value too large';
    }

    if (followers.trim()) {
      const n = parseInt(followers, 10);
      if (isNaN(n) || n < 0) e.followers = 'Enter a positive number';
      else if (n > 1_000_000_000) e.followers = 'Value too large';
    }
    return e;
  }, [name, revenue, followers]);

  const canSubmit = Object.keys(errors).length === 0 && !busy;
  const shouldShow = (field: keyof FieldErrors) => touched[field] && !!errors[field];

  const markTouched = (field: keyof FieldErrors) =>
    setTouched(t => ({ ...t, [field]: true }));

  const submit = async () => {
    // Mark all as touched so any hidden errors surface
    setTouched({ name: true, revenue: true, followers: true });
    if (Object.keys(errors).length > 0) return;

    setBusy(true); setServerErr(null);
    try {
      const rev = parseFloat(revenue) || 0;
      await api.createAsset({
        name: name.trim(),
        platform,
        category: category.trim() || 'General',
        revenue_mtd: rev,
        profit_mtd: rev * 0.75,
        followers: parseInt(followers, 10) || 0,
        ai_score: 70,
        trend: [65, 67, 68, 70, 71, 72, 70],
      });
      reset();
      onCreated();
      onClose();
    } catch {
      setServerErr('Failed to create — try again');
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

                <View style={styles.fieldRow}>
                  <Text style={styles.label}>NAME</Text>
                  <Text style={styles.required}>* required</Text>
                </View>
                <TextInput
                  value={name}
                  onChangeText={setName}
                  onBlur={() => markTouched('name')}
                  placeholder="e.g. My YouTube channel"
                  placeholderTextColor={colors.onSurfaceTertiary}
                  style={[styles.input, shouldShow('name') && styles.inputError]}
                  maxLength={80}
                  testID="asset-name-input"
                />
                {shouldShow('name') && (
                  <Text style={styles.fieldErr} testID="asset-name-error">
                    <Ionicons name="alert-circle" size={11} color={colors.error} /> {errors.name}
                  </Text>
                )}

                <Text style={styles.label}>CATEGORY</Text>
                <TextInput
                  value={category}
                  onChangeText={setCategory}
                  placeholder="e.g. Long-form video (optional)"
                  placeholderTextColor={colors.onSurfaceTertiary}
                  style={styles.input}
                  maxLength={60}
                  testID="asset-category-input"
                />

                <View style={styles.numRow}>
                  <View style={styles.numCol}>
                    <Text style={styles.label}>REVENUE MTD ($)</Text>
                    <TextInput
                      value={revenue}
                      onChangeText={(t) => setRevenue(t.replace(/[^0-9.]/g, ''))}
                      onBlur={() => markTouched('revenue')}
                      placeholder="0"
                      placeholderTextColor={colors.onSurfaceTertiary}
                      keyboardType="decimal-pad"
                      style={[styles.input, shouldShow('revenue') && styles.inputError]}
                      testID="asset-revenue-input"
                    />
                    {shouldShow('revenue') && (
                      <Text style={styles.fieldErr} testID="asset-revenue-error">
                        <Ionicons name="alert-circle" size={11} color={colors.error} /> {errors.revenue}
                      </Text>
                    )}
                  </View>
                  <View style={styles.numCol}>
                    <Text style={styles.label}>FOLLOWERS</Text>
                    <TextInput
                      value={followers}
                      onChangeText={(t) => setFollowers(t.replace(/[^0-9]/g, ''))}
                      onBlur={() => markTouched('followers')}
                      placeholder="0"
                      placeholderTextColor={colors.onSurfaceTertiary}
                      keyboardType="number-pad"
                      style={[styles.input, shouldShow('followers') && styles.inputError]}
                      testID="asset-followers-input"
                    />
                    {shouldShow('followers') && (
                      <Text style={styles.fieldErr} testID="asset-followers-error">
                        <Ionicons name="alert-circle" size={11} color={colors.error} /> {errors.followers}
                      </Text>
                    )}
                  </View>
                </View>

                {serverErr && (
                  <View style={styles.serverErrBox}>
                    <Ionicons name="warning" size={14} color={colors.error} />
                    <Text style={styles.serverErrText}>{serverErr}</Text>
                  </View>
                )}

                <Pressable
                  onPress={submit}
                  disabled={!canSubmit}
                  style={[styles.submitBtn, !canSubmit && styles.submitBtnDisabled]}
                  testID="asset-submit-btn"
                >
                  {busy
                    ? <ActivityIndicator color={colors.onBrandPrimary} />
                    : <>
                        <Ionicons
                          name="add-circle"
                          size={16}
                          color={canSubmit ? colors.onBrandPrimary : colors.onSurfaceTertiary}
                        />
                        <Text style={[styles.submitText, !canSubmit && { color: colors.onSurfaceTertiary }]}>
                          Add asset
                        </Text>
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
  fieldRow: {
    flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between',
    marginTop: spacing.md, marginBottom: spacing.sm,
  },
  required: { color: colors.brand, fontSize: 10, fontWeight: '600', letterSpacing: 0.4 },

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
    borderWidth: 1, borderColor: colors.border,
  },
  inputError: { borderColor: colors.error },
  fieldErr: { color: colors.error, fontSize: 11, marginTop: 4, marginLeft: 2, fontWeight: '500' },

  numRow: { flexDirection: 'row', gap: spacing.md },
  numCol: { flex: 1 },

  serverErrBox: {
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm,
    marginTop: spacing.md, padding: spacing.sm, borderRadius: radius.sm,
    backgroundColor: 'rgba(229,72,77,0.10)',
    borderWidth: StyleSheet.hairlineWidth, borderColor: 'rgba(229,72,77,0.3)',
  },
  serverErrText: { color: colors.error, fontSize: 12, flex: 1 },

  submitBtn: {
    marginTop: spacing.lg,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.sm,
    backgroundColor: colors.brand,
    borderRadius: radius.md, paddingVertical: 14,
  },
  submitBtnDisabled: { backgroundColor: colors.surfaceTertiary, opacity: 0.6 },
  submitText: { color: colors.onBrandPrimary, fontSize: 14, fontWeight: '700' },
});
