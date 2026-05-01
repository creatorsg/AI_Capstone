import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  FlatList, ActivityIndicator, Alert, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../constants/Colors';
import { welfareAPI } from '../../services/api';
import { WelfarePolicy } from '../../types';
import { useChildStore } from '../../store/childStore';
import { differenceInMonths, parseISO } from '../../utils/dateUtils';

const FILTER_OPTIONS = [
  { label: '전체', value: 'all' },
  { label: '우리 아이 맞춤', value: 'child' },
];

export default function WelfareScreen() {
  const [policies, setPolicies] = useState<WelfarePolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const { selectedChild } = useChildStore();

  const childAgeMonths = selectedChild
    ? differenceInMonths(new Date(), parseISO(selectedChild.birth_date))
    : null;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      let data: WelfarePolicy[] = [];
      if (filter === 'child' && childAgeMonths !== null) {
        const res = await welfareAPI.byAge(childAgeMonths);
        data = Array.isArray(res.data) ? res.data : res.data.items || [];
      } else {
        const res = await welfareAPI.list(0, 50);
        data = Array.isArray(res.data) ? res.data : res.data.items || [];
      }
      setPolicies(data);
    } catch {
      Alert.alert('오류', '복지 정책 정보를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, [filter, childAgeMonths]);

  useEffect(() => { load(); }, [load]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) { load(); return; }
    setLoading(true);
    try {
      const res = await welfareAPI.search(searchQuery.trim());
      const data = Array.isArray(res.data) ? res.data : res.data.items || [];
      setPolicies(data);
    } catch {
      Alert.alert('오류', '검색에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const getAgeRange = (policy: WelfarePolicy) => {
    const min = policy.target_age_min_months;
    const max = policy.target_age_max_months;
    if (min === undefined && max === undefined) return null;
    const toLabel = (m: number) => m >= 12 ? `만 ${Math.floor(m / 12)}세` : `${m}개월`;
    if (min !== undefined && max !== undefined) return `${toLabel(min)} ~ ${toLabel(max)}`;
    if (max !== undefined) return `${toLabel(max)} 이하`;
    return null;
  };

  const renderPolicy = ({ item, index }: { item: WelfarePolicy; index: number }) => {
    const isExpanded = expandedId === index;
    const ageRange = getAgeRange(item);
    return (
      <TouchableOpacity
        style={styles.card}
        onPress={() => setExpandedId(isExpanded ? null : index)}
        activeOpacity={0.85}
      >
        <View style={styles.cardHeader}>
          <View style={styles.cardIcon}>
            <Ionicons name="shield-checkmark" size={20} color={Colors.accent} />
          </View>
          <View style={styles.cardMeta}>
            {item.department && <Text style={styles.department}>{item.department}</Text>}
            {ageRange && (
              <View style={styles.ageBadge}>
                <Ionicons name="time-outline" size={11} color={Colors.primary} />
                <Text style={styles.ageText}>{ageRange}</Text>
              </View>
            )}
          </View>
          <Ionicons
            name={isExpanded ? 'chevron-up' : 'chevron-down'}
            size={18} color={Colors.textSecondary}
          />
        </View>
        <Text style={styles.policyTitle}>{item.title}</Text>
        {isExpanded && (
          <>
            <Text style={styles.policyContent}>{item.content}</Text>
            {item.contact && (
              <View style={styles.infoRow}>
                <Ionicons name="call-outline" size={14} color={Colors.primary} />
                <Text style={styles.infoText}>{item.contact}</Text>
              </View>
            )}
            {item.url && (
              <TouchableOpacity style={styles.linkButton} onPress={() => Linking.openURL(item.url!)}>
                <Ionicons name="open-outline" size={14} color={Colors.primary} />
                <Text style={styles.linkText}>자세히 보기</Text>
              </TouchableOpacity>
            )}
          </>
        )}
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>복지 정책</Text>
        <Text style={styles.headerSub}>육아 관련 정부 지원 정책을 확인하세요</Text>
      </View>

      {/* 검색 */}
      <View style={styles.searchContainer}>
        <View style={styles.searchBar}>
          <Ionicons name="search-outline" size={18} color={Colors.textSecondary} />
          <TextInput
            style={styles.searchInput}
            placeholder="정책명 검색"
            placeholderTextColor={Colors.textTertiary}
            value={searchQuery}
            onChangeText={setSearchQuery}
            onSubmitEditing={handleSearch}
            returnKeyType="search"
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => { setSearchQuery(''); load(); }}>
              <Ionicons name="close-circle" size={18} color={Colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
        <TouchableOpacity style={styles.searchButton} onPress={handleSearch}>
          <Text style={styles.searchButtonText}>검색</Text>
        </TouchableOpacity>
      </View>

      {/* 필터 탭 */}
      <View style={styles.filterRow}>
        {FILTER_OPTIONS.map((opt) => (
          <TouchableOpacity
            key={opt.value}
            style={[styles.filterTab, filter === opt.value && styles.filterTabActive]}
            onPress={() => setFilter(opt.value)}
          >
            {opt.value === 'child' && (
              <Ionicons name="star" size={12} color={filter === opt.value ? '#fff' : Colors.textSecondary} />
            )}
            <Text style={[styles.filterText, filter === opt.value && styles.filterTextActive]}>
              {opt.label}
              {opt.value === 'child' && selectedChild ? ` (${selectedChild.name})` : ''}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.loadingText}>정책 정보를 불러오고 있습니다...</Text>
        </View>
      ) : policies.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Ionicons name="document-text-outline" size={56} color={Colors.primaryLight} />
          <Text style={styles.emptyTitle}>복지 정책 정보가 없습니다</Text>
          {filter === 'child' && !selectedChild && (
            <Text style={styles.emptySubtitle}>챗봇 탭에서 아이를 선택하면 맞춤 정책을 볼 수 있습니다</Text>
          )}
        </View>
      ) : (
        <FlatList
          data={policies}
          keyExtractor={(_, i) => i.toString()}
          renderItem={renderPolicy}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          ListHeaderComponent={
            <Text style={styles.resultCount}>총 {policies.length}개의 정책</Text>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 12, backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  headerTitle: { fontSize: 22, fontWeight: '800', color: Colors.text },
  headerSub: { fontSize: 13, color: Colors.textSecondary, marginTop: 4 },
  searchContainer: { flexDirection: 'row', gap: 10, paddingHorizontal: 16, paddingVertical: 12, backgroundColor: Colors.surface },
  searchBar: {
    flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: Colors.surfaceVariant, borderRadius: 12, paddingHorizontal: 14,
    borderWidth: 1.5, borderColor: Colors.border, height: 46,
  },
  searchInput: { flex: 1, fontSize: 14, color: Colors.text },
  searchButton: { backgroundColor: Colors.primary, borderRadius: 12, paddingHorizontal: 16, justifyContent: 'center' },
  searchButtonText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  filterRow: { flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 10, gap: 8, backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  filterTab: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, backgroundColor: Colors.surfaceVariant, borderWidth: 1.5, borderColor: Colors.border },
  filterTabActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  filterText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  filterTextActive: { color: '#fff' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { color: Colors.textSecondary, fontSize: 14 },
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: Colors.text, marginTop: 16 },
  emptySubtitle: { fontSize: 14, color: Colors.textSecondary, marginTop: 8, textAlign: 'center' },
  list: { padding: 16, gap: 12 },
  resultCount: { fontSize: 13, color: Colors.textSecondary, marginBottom: 8, fontWeight: '600' },
  card: {
    backgroundColor: Colors.surface, borderRadius: 16, padding: 16,
    shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1, shadowRadius: 8, elevation: 3,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  cardIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: Colors.accent + '20', justifyContent: 'center', alignItems: 'center' },
  cardMeta: { flex: 1, gap: 4 },
  department: { fontSize: 11, color: Colors.textSecondary, fontWeight: '600' },
  ageBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, alignSelf: 'flex-start', backgroundColor: Colors.primaryLight + '30', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 2 },
  ageText: { fontSize: 11, color: Colors.primary, fontWeight: '600' },
  policyTitle: { fontSize: 15, fontWeight: '700', color: Colors.text, lineHeight: 22 },
  policyContent: { fontSize: 14, color: Colors.textSecondary, lineHeight: 22, marginTop: 10 },
  infoRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10 },
  infoText: { fontSize: 13, color: Colors.primary },
  linkButton: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12, alignSelf: 'flex-start', backgroundColor: Colors.surfaceVariant, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8 },
  linkText: { fontSize: 13, color: Colors.primary, fontWeight: '600' },
});
