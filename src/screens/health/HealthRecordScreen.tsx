import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, FlatList,
  ActivityIndicator, Alert, Modal, TextInput, ScrollView,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Colors } from '../../constants/Colors';
import { healthAPI } from '../../services/api';
import { HealthLog, VaccinationRecord, RootStackParamList } from '../../types';
import { useChildStore } from '../../store/childStore';

type NavProp = NativeStackNavigationProp<RootStackParamList>;
type RoutePropType = RouteProp<RootStackParamList, 'HealthRecord'>;

const LOG_TYPES = [
  { key: 'fever', label: '발열', icon: 'thermometer-outline' as const, color: '#E17055', unit: '°C', placeholder: '예: 38.5' },
  { key: 'meal', label: '식사', icon: 'restaurant-outline' as const, color: '#00B894', unit: '', placeholder: '예: 이유식 100g' },
  { key: 'sleep', label: '수면', icon: 'moon-outline' as const, color: '#6C5CE7', unit: '', placeholder: '예: 90분' },
  { key: 'breastfeed', label: '모유수유', icon: 'nutrition-outline' as const, color: '#FD79A8', unit: 'ml', placeholder: '예: 150' },
  { key: 'formula', label: '분유', icon: 'cafe-outline' as const, color: '#FDCB6E', unit: 'ml', placeholder: '예: 150' },
] as const;

type LogTypeKey = typeof LOG_TYPES[number]['key'];

function formatDate(isoStr: string) {
  const d = new Date(isoStr);
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function todayStr() {
  const d = new Date();
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export default function HealthRecordScreen() {
  const navigation = useNavigation<NavProp>();
  const route = useRoute<RoutePropType>();
  const { childId } = route.params;
  const { children } = useChildStore();
  const child = children.find((c) => c.id === childId);

  const [activeTab, setActiveTab] = useState<'logs' | 'vaccines'>('logs');
  const [logs, setLogs] = useState<HealthLog[]>([]);
  const [vaccines, setVaccines] = useState<VaccinationRecord[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [loadingVaccines, setLoadingVaccines] = useState(false);
  const [selectedLogType, setSelectedLogType] = useState<LogTypeKey | 'all'>('all');

  // 건강기록 추가 모달
  const [logModalVisible, setLogModalVisible] = useState(false);
  const [newLogType, setNewLogType] = useState<LogTypeKey>('fever');
  const [newLogValue, setNewLogValue] = useState('');
  const [newLogNote, setNewLogNote] = useState('');
  const [savingLog, setSavingLog] = useState(false);

  // 예방접종 추가 모달
  const [vacModalVisible, setVacModalVisible] = useState(false);
  const [vaccineName, setVaccineName] = useState('');
  const [vaccinatedAt, setVaccinatedAt] = useState(todayStr());
  const [nextDue, setNextDue] = useState('');
  const [vaccineNote, setVaccineNote] = useState('');
  const [savingVac, setSavingVac] = useState(false);

  const fetchLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      const { data } = await healthAPI.getLogs(childId);
      setLogs(Array.isArray(data) ? data : []);
    } catch {
      Alert.alert('오류', '건강 기록을 불러오지 못했습니다.');
    } finally {
      setLoadingLogs(false);
    }
  }, [childId]);

  const fetchVaccines = useCallback(async () => {
    setLoadingVaccines(true);
    try {
      const { data } = await healthAPI.getVaccinations(childId);
      setVaccines(Array.isArray(data) ? data : []);
    } catch {
      Alert.alert('오류', '예방접종 기록을 불러오지 못했습니다.');
    } finally {
      setLoadingVaccines(false);
    }
  }, [childId]);

  useEffect(() => {
    fetchLogs();
    fetchVaccines();
  }, [fetchLogs, fetchVaccines]);

  const handleAddLog = async () => {
    if (!newLogValue.trim() && newLogType === 'fever') {
      Alert.alert('입력 오류', '체온을 입력해주세요.');
      return;
    }
    setSavingLog(true);
    try {
      await healthAPI.addLog({
        child_id: childId,
        log_type: newLogType,
        value: newLogValue.trim() || undefined,
        note: newLogNote.trim() || undefined,
      });
      setLogModalVisible(false);
      setNewLogValue('');
      setNewLogNote('');
      await fetchLogs();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      Alert.alert('오류', typeof detail === 'string' ? detail : '기록 저장에 실패했습니다.');
    } finally {
      setSavingLog(false);
    }
  };

  const handleAddVaccine = async () => {
    if (!vaccineName.trim()) {
      Alert.alert('입력 오류', '백신 이름을 입력해주세요.');
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(vaccinatedAt)) {
      Alert.alert('입력 오류', '접종일을 YYYY-MM-DD 형식으로 입력해주세요.');
      return;
    }
    setSavingVac(true);
    try {
      await healthAPI.addVaccination({
        child_id: childId,
        vaccine_name: vaccineName.trim(),
        vaccinated_at: vaccinatedAt,
        next_due: nextDue.trim() || undefined,
        note: vaccineNote.trim() || undefined,
      });
      setVacModalVisible(false);
      setVaccineName('');
      setNextDue('');
      setVaccineNote('');
      setVaccinatedAt(todayStr());
      await fetchVaccines();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      Alert.alert('오류', typeof detail === 'string' ? detail : '기록 저장에 실패했습니다.');
    } finally {
      setSavingVac(false);
    }
  };

  const getLogTypeInfo = (key: string) =>
    LOG_TYPES.find((t) => t.key === key) || LOG_TYPES[0];

  const filteredLogs = selectedLogType === 'all'
    ? logs
    : logs.filter((l) => l.log_type === selectedLogType);

  const renderLog = ({ item }: { item: HealthLog }) => {
    const typeInfo = getLogTypeInfo(item.log_type);
    return (
      <View style={styles.logCard}>
        <View style={[styles.logTypeIcon, { backgroundColor: typeInfo.color + '20' }]}>
          <Ionicons name={typeInfo.icon} size={22} color={typeInfo.color} />
        </View>
        <View style={styles.logContent}>
          <View style={styles.logHeader}>
            <Text style={[styles.logTypeBadge, { color: typeInfo.color }]}>{typeInfo.label}</Text>
            <Text style={styles.logTime}>{formatDate(item.recorded_at)}</Text>
          </View>
          {item.value && (
            <Text style={styles.logValue}>
              {item.value}{typeInfo.unit && !item.value.includes(typeInfo.unit) ? ` ${typeInfo.unit}` : ''}
            </Text>
          )}
          {item.note && <Text style={styles.logNote}>{item.note}</Text>}
        </View>
      </View>
    );
  };

  const renderVaccine = ({ item }: { item: VaccinationRecord }) => (
    <View style={styles.vaccineCard}>
      <View style={styles.vaccineIconBox}>
        <Ionicons name="shield-checkmark" size={22} color={Colors.success} />
      </View>
      <View style={styles.vaccineContent}>
        <Text style={styles.vaccineName}>{item.vaccine_name}</Text>
        {item.vaccinated_at && (
          <View style={styles.vaccineRow}>
            <Ionicons name="checkmark-circle-outline" size={14} color={Colors.success} />
            <Text style={styles.vaccineDate}>접종일: {item.vaccinated_at}</Text>
          </View>
        )}
        {item.next_due && (
          <View style={styles.vaccineRow}>
            <Ionicons name="calendar-outline" size={14} color={Colors.primary} />
            <Text style={styles.vaccineNextDue}>다음 예정: {item.next_due}</Text>
          </View>
        )}
        {item.note && <Text style={styles.vaccineNote}>{item.note}</Text>}
      </View>
    </View>
  );

  const currentLogTypeInfo = LOG_TYPES.find((t) => t.key === newLogType)!;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Ionicons name="chevron-back" size={24} color={Colors.text} />
        </TouchableOpacity>
        <View>
          <Text style={styles.headerTitle}>건강 기록</Text>
          {child && <Text style={styles.headerSub}>{child.name}</Text>}
        </View>
        <TouchableOpacity
          style={styles.addBtn}
          onPress={() => activeTab === 'logs' ? setLogModalVisible(true) : setVacModalVisible(true)}
        >
          <Ionicons name="add" size={24} color={Colors.primary} />
        </TouchableOpacity>
      </View>

      {/* 탭 */}
      <View style={styles.tabRow}>
        {[
          { key: 'logs', label: '건강 로그', icon: 'pulse-outline' as const },
          { key: 'vaccines', label: '예방접종', icon: 'shield-checkmark-outline' as const },
        ].map((tab) => (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tab, activeTab === tab.key && styles.tabActive]}
            onPress={() => setActiveTab(tab.key as 'logs' | 'vaccines')}
          >
            <Ionicons
              name={tab.icon}
              size={16}
              color={activeTab === tab.key ? Colors.primary : Colors.textSecondary}
            />
            <Text style={[styles.tabText, activeTab === tab.key && styles.tabTextActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* 건강 로그 탭 */}
      {activeTab === 'logs' && (
        <>
          {/* 타입 필터 */}
          <View style={styles.typeFilterContainer}>
            <FlatList
              horizontal
              data={[{ key: 'all', label: '전체', icon: 'list-outline' as const, color: Colors.textSecondary }, ...LOG_TYPES]}
              keyExtractor={(item) => item.key}
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.typeFilterRow}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[styles.typeFilterTab, selectedLogType === item.key && styles.typeFilterTabActive]}
                  onPress={() => setSelectedLogType(item.key as LogTypeKey | 'all')}
                >
                  <Text style={[styles.typeFilterText, selectedLogType === item.key && styles.typeFilterTextActive]}>
                    {item.label}
                  </Text>
                </TouchableOpacity>
              )}
            />
          </View>

          {loadingLogs ? (
            <View style={styles.loadingBox}>
              <ActivityIndicator size="large" color={Colors.primary} />
            </View>
          ) : filteredLogs.length === 0 ? (
            <View style={styles.emptyBox}>
              <Ionicons name="pulse-outline" size={48} color={Colors.primaryLight} />
              <Text style={styles.emptyTitle}>기록이 없습니다</Text>
              <Text style={styles.emptySubtitle}>우측 상단 + 버튼으로 추가하세요</Text>
            </View>
          ) : (
            <FlatList
              data={filteredLogs}
              keyExtractor={(item) => item.id.toString()}
              renderItem={renderLog}
              contentContainerStyle={styles.list}
              showsVerticalScrollIndicator={false}
              ListHeaderComponent={
                <Text style={styles.countText}>총 {filteredLogs.length}개</Text>
              }
            />
          )}
        </>
      )}

      {/* 예방접종 탭 */}
      {activeTab === 'vaccines' && (
        loadingVaccines ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator size="large" color={Colors.primary} />
          </View>
        ) : vaccines.length === 0 ? (
          <View style={styles.emptyBox}>
            <Ionicons name="shield-outline" size={48} color={Colors.primaryLight} />
            <Text style={styles.emptyTitle}>예방접종 기록이 없습니다</Text>
            <Text style={styles.emptySubtitle}>우측 상단 + 버튼으로 추가하세요</Text>
          </View>
        ) : (
          <FlatList
            data={vaccines}
            keyExtractor={(item) => item.id.toString()}
            renderItem={renderVaccine}
            contentContainerStyle={styles.list}
            showsVerticalScrollIndicator={false}
            ListHeaderComponent={
              <Text style={styles.countText}>총 {vaccines.length}개</Text>
            }
          />
        )
      )}

      {/* 건강기록 추가 모달 */}
      <Modal visible={logModalVisible} animationType="slide" transparent presentationStyle="overFullScreen">
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>건강 기록 추가</Text>
              <TouchableOpacity onPress={() => { setLogModalVisible(false); setNewLogValue(''); setNewLogNote(''); }}>
                <Ionicons name="close" size={24} color={Colors.text} />
              </TouchableOpacity>
            </View>

            <ScrollView keyboardShouldPersistTaps="handled">
              {/* 타입 선택 */}
              <Text style={styles.modalLabel}>기록 유형</Text>
              <View style={styles.logTypeGrid}>
                {LOG_TYPES.map((t) => (
                  <TouchableOpacity
                    key={t.key}
                    style={[styles.logTypeBtn, newLogType === t.key && { borderColor: t.color, backgroundColor: t.color + '15' }]}
                    onPress={() => setNewLogType(t.key)}
                  >
                    <Ionicons name={t.icon} size={20} color={newLogType === t.key ? t.color : Colors.textSecondary} />
                    <Text style={[styles.logTypeBtnText, newLogType === t.key && { color: t.color }]}>
                      {t.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* 값 입력 */}
              <Text style={styles.modalLabel}>
                측정값 {currentLogTypeInfo.unit ? `(${currentLogTypeInfo.unit})` : ''}
              </Text>
              <TextInput
                style={styles.modalInput}
                placeholder={currentLogTypeInfo.placeholder}
                placeholderTextColor={Colors.textTertiary}
                value={newLogValue}
                onChangeText={setNewLogValue}
                keyboardType={newLogType === 'fever' || newLogType === 'breastfeed' || newLogType === 'formula' ? 'decimal-pad' : 'default'}
              />

              {/* 메모 */}
              <Text style={styles.modalLabel}>메모 (선택)</Text>
              <TextInput
                style={[styles.modalInput, styles.modalTextarea]}
                placeholder="추가 메모를 입력하세요"
                placeholderTextColor={Colors.textTertiary}
                value={newLogNote}
                onChangeText={setNewLogNote}
                multiline
                numberOfLines={3}
                textAlignVertical="top"
              />

              <TouchableOpacity
                style={[styles.modalSaveBtn, { backgroundColor: currentLogTypeInfo.color }]}
                onPress={handleAddLog}
                disabled={savingLog}
              >
                {savingLog ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <>
                    <Ionicons name="checkmark-circle" size={20} color="#fff" />
                    <Text style={styles.modalSaveBtnText}>저장하기</Text>
                  </>
                )}
              </TouchableOpacity>
              <View style={{ height: 20 }} />
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* 예방접종 추가 모달 */}
      <Modal visible={vacModalVisible} animationType="slide" transparent presentationStyle="overFullScreen">
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>예방접종 기록 추가</Text>
              <TouchableOpacity onPress={() => {
                setVacModalVisible(false);
                setVaccineName(''); setNextDue(''); setVaccineNote('');
                setVaccinatedAt(todayStr());
              }}>
                <Ionicons name="close" size={24} color={Colors.text} />
              </TouchableOpacity>
            </View>
            <ScrollView keyboardShouldPersistTaps="handled">
              <Text style={styles.modalLabel}>백신 이름 <Text style={{ color: Colors.error }}>*</Text></Text>
              <TextInput
                style={styles.modalInput}
                placeholder="예: BCG, DTaP 1차, MMR"
                placeholderTextColor={Colors.textTertiary}
                value={vaccineName}
                onChangeText={setVaccineName}
              />

              <Text style={styles.modalLabel}>접종일 <Text style={{ color: Colors.error }}>*</Text></Text>
              <TextInput
                style={styles.modalInput}
                placeholder="YYYY-MM-DD"
                placeholderTextColor={Colors.textTertiary}
                value={vaccinatedAt}
                onChangeText={setVaccinatedAt}
                keyboardType="numeric"
                maxLength={10}
              />

              <Text style={styles.modalLabel}>다음 접종 예정일 (선택)</Text>
              <TextInput
                style={styles.modalInput}
                placeholder="YYYY-MM-DD"
                placeholderTextColor={Colors.textTertiary}
                value={nextDue}
                onChangeText={setNextDue}
                keyboardType="numeric"
                maxLength={10}
              />

              <Text style={styles.modalLabel}>메모 (선택)</Text>
              <TextInput
                style={[styles.modalInput, styles.modalTextarea]}
                placeholder="특이사항을 입력하세요"
                placeholderTextColor={Colors.textTertiary}
                value={vaccineNote}
                onChangeText={setVaccineNote}
                multiline
                numberOfLines={3}
                textAlignVertical="top"
              />

              <TouchableOpacity
                style={[styles.modalSaveBtn, { backgroundColor: Colors.success }]}
                onPress={handleAddVaccine}
                disabled={savingVac}
              >
                {savingVac ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <>
                    <Ionicons name="checkmark-circle" size={20} color="#fff" />
                    <Text style={styles.modalSaveBtnText}>저장하기</Text>
                  </>
                )}
              </TouchableOpacity>
              <View style={{ height: 20 }} />
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  backBtn: { width: 40, height: 40, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '700', color: Colors.text },
  headerSub: { fontSize: 12, color: Colors.primary, fontWeight: '600' },
  addBtn: { width: 40, height: 40, justifyContent: 'center', alignItems: 'center' },
  tabRow: {
    flexDirection: 'row', backgroundColor: Colors.surface,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  tab: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 12, borderBottomWidth: 2, borderBottomColor: 'transparent',
  },
  tabActive: { borderBottomColor: Colors.primary },
  tabText: { fontSize: 14, fontWeight: '600', color: Colors.textSecondary },
  tabTextActive: { color: Colors.primary },
  typeFilterContainer: { backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  typeFilterRow: { paddingHorizontal: 16, paddingVertical: 10, gap: 8 },
  typeFilterTab: {
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 20,
    backgroundColor: Colors.surfaceVariant, borderWidth: 1.5, borderColor: Colors.border,
  },
  typeFilterTabActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  typeFilterText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  typeFilterTextActive: { color: '#fff' },
  loadingBox: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyBox: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: Colors.text, marginTop: 14 },
  emptySubtitle: { fontSize: 13, color: Colors.textSecondary, marginTop: 6 },
  list: { padding: 16, gap: 12 },
  countText: { fontSize: 13, color: Colors.textSecondary, fontWeight: '600', marginBottom: 8 },
  logCard: {
    flexDirection: 'row', gap: 14, backgroundColor: Colors.surface, borderRadius: 16, padding: 16,
    shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 2 }, shadowOpacity: 1, shadowRadius: 8, elevation: 3,
  },
  logTypeIcon: { width: 44, height: 44, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  logContent: { flex: 1 },
  logHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  logTypeBadge: { fontSize: 12, fontWeight: '700' },
  logTime: { fontSize: 11, color: Colors.textTertiary },
  logValue: { fontSize: 16, fontWeight: '700', color: Colors.text },
  logNote: { fontSize: 13, color: Colors.textSecondary, marginTop: 4 },
  vaccineCard: {
    flexDirection: 'row', gap: 14, backgroundColor: Colors.surface, borderRadius: 16, padding: 16,
    shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 2 }, shadowOpacity: 1, shadowRadius: 8, elevation: 3,
  },
  vaccineIconBox: { width: 44, height: 44, borderRadius: 14, backgroundColor: Colors.success + '20', justifyContent: 'center', alignItems: 'center' },
  vaccineContent: { flex: 1 },
  vaccineName: { fontSize: 16, fontWeight: '700', color: Colors.text, marginBottom: 6 },
  vaccineRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  vaccineDate: { fontSize: 13, color: Colors.success, fontWeight: '600' },
  vaccineNextDue: { fontSize: 13, color: Colors.primary, fontWeight: '600' },
  vaccineNote: { fontSize: 13, color: Colors.textSecondary, marginTop: 6 },
  // 모달
  modalOverlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.5)' },
  modalSheet: {
    backgroundColor: Colors.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24,
    paddingHorizontal: 20, paddingTop: 20, maxHeight: '90%',
  },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: Colors.text },
  modalLabel: { fontSize: 14, fontWeight: '700', color: Colors.text, marginBottom: 8, marginTop: 16 },
  modalInput: {
    borderWidth: 1.5, borderColor: Colors.border, borderRadius: 12,
    paddingHorizontal: 14, paddingVertical: 12,
    fontSize: 15, color: Colors.text, backgroundColor: Colors.surfaceVariant,
  },
  modalTextarea: { height: 80, paddingTop: 12 },
  logTypeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  logTypeBtn: {
    width: '30%', alignItems: 'center', gap: 6, paddingVertical: 12,
    borderWidth: 1.5, borderColor: Colors.border, borderRadius: 14,
    backgroundColor: Colors.surfaceVariant,
  },
  logTypeBtnText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  modalSaveBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    borderRadius: 16, padding: 16, marginTop: 24,
  },
  modalSaveBtnText: { color: '#fff', fontSize: 17, fontWeight: '700' },
});
