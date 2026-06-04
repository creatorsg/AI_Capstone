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
import { notesAPI } from '../../services/api';
import { ChildNote, NoteCategory, NoteSeverity, RootStackParamList } from '../../types';
import { useChildStore } from '../../store/childStore';

type NavProp = NativeStackNavigationProp<RootStackParamList>;
type RoutePropType = RouteProp<RootStackParamList, 'ChildNotes'>;

const CATEGORY_OPTIONS = [
  { key: 'all',      label: '전체',   icon: 'list-outline' as const,        color: Colors.textSecondary },
  { key: 'diary',    label: '일기',   icon: 'book-outline' as const,         color: '#6C5CE7' },
  { key: 'snack',    label: '간식',   icon: 'nutrition-outline' as const,    color: '#00B894' },
  { key: 'behavior', label: '행동발달', icon: 'happy-outline' as const,      color: '#0984E3' },
  { key: 'symptom',  label: '증상',   icon: 'thermometer-outline' as const,  color: '#E17055' },
] as const;

const SEVERITY_OPTIONS = [
  { key: 'mild',     label: '경미', color: '#FDCB6E' },
  { key: 'moderate', label: '보통', color: '#E17055' },
  { key: 'severe',   label: '심각', color: '#D63031' },
] as const;

function todayStr() {
  const d = new Date();
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function formatNoteDate(dateStr: string) {
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  return `${parts[0]}.${parts[1]}.${parts[2]}`;
}

export default function ChildNotesScreen() {
  const navigation = useNavigation<NavProp>();
  const route = useRoute<RoutePropType>();
  const { childId } = route.params;
  const { children } = useChildStore();
  const child = children.find((c) => c.id === childId);

  const [notes, setNotes] = useState<ChildNote[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<NoteCategory | 'all'>('all');

  const [modalVisible, setModalVisible] = useState(false);
  const [newCategory, setNewCategory] = useState<NoteCategory>('diary');
  const [newDate, setNewDate] = useState(todayStr());
  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newValue, setNewValue] = useState('');
  const [newUnit, setNewUnit] = useState('');
  const [newSeverity, setNewSeverity] = useState<NoteSeverity | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchNotes = useCallback(async () => {
    setLoading(true);
    try {
      const params = selectedCategory !== 'all' ? { category: selectedCategory } : {};
      const { data } = await notesAPI.list(childId, params);
      setNotes(Array.isArray(data) ? data : []);
    } catch {
      Alert.alert('오류', '노트를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, [childId, selectedCategory]);

  useEffect(() => {
    fetchNotes();
  }, [fetchNotes]);

  const resetForm = () => {
    setNewCategory('diary');
    setNewDate(todayStr());
    setNewTitle('');
    setNewContent('');
    setNewValue('');
    setNewUnit('');
    setNewSeverity(null);
  };

  const handleCreate = async () => {
    if (!newContent.trim()) {
      Alert.alert('입력 오류', '내용을 입력해주세요.');
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(newDate)) {
      Alert.alert('입력 오류', '날짜를 YYYY-MM-DD 형식으로 입력해주세요.');
      return;
    }
    setSaving(true);
    try {
      await notesAPI.create(childId, {
        category: newCategory,
        note_date: newDate,
        title: newTitle.trim() || undefined,
        content: newContent.trim(),
        value: newValue ? parseFloat(newValue) : undefined,
        unit: newUnit.trim() || undefined,
        severity: newSeverity || undefined,
      });
      setModalVisible(false);
      resetForm();
      await fetchNotes();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      Alert.alert('오류', typeof detail === 'string' ? detail : '저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = (noteId: number) => {
    Alert.alert('삭제', '이 노트를 삭제할까요?', [
      { text: '취소', style: 'cancel' },
      {
        text: '삭제',
        style: 'destructive',
        onPress: async () => {
          try {
            await notesAPI.delete(childId, noteId);
            setNotes((prev) => prev.filter((n) => n.id !== noteId));
          } catch {
            Alert.alert('오류', '삭제에 실패했습니다.');
          }
        },
      },
    ]);
  };

  const getCategoryInfo = (key: string) =>
    CATEGORY_OPTIONS.find((c) => c.key === key) || CATEGORY_OPTIONS[1];

  const getSeverityInfo = (key: string) =>
    SEVERITY_OPTIONS.find((s) => s.key === key);

  const renderNote = ({ item }: { item: ChildNote }) => {
    const catInfo = getCategoryInfo(item.category);
    const sevInfo = item.severity ? getSeverityInfo(item.severity) : null;
    return (
      <View style={styles.noteCard}>
        <View style={styles.noteHeader}>
          <View style={[styles.catBadge, { backgroundColor: catInfo.color + '20' }]}>
            <Ionicons name={catInfo.icon} size={13} color={catInfo.color} />
            <Text style={[styles.catBadgeText, { color: catInfo.color }]}>{catInfo.label}</Text>
          </View>
          <Text style={styles.noteDate}>{formatNoteDate(item.note_date)}</Text>
          <TouchableOpacity
            onPress={() => handleDelete(item.id)}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Ionicons name="trash-outline" size={16} color={Colors.textTertiary} />
          </TouchableOpacity>
        </View>
        {item.title && <Text style={styles.noteTitle}>{item.title}</Text>}
        <Text style={styles.noteContent}>{item.content}</Text>
        {item.value !== null && item.value !== undefined && (
          <Text style={styles.noteValue}>
            {item.value}{item.unit ? ` ${item.unit}` : ''}
          </Text>
        )}
        {sevInfo && (
          <View style={[styles.sevBadge, { backgroundColor: sevInfo.color + '20' }]}>
            <Text style={[styles.sevText, { color: sevInfo.color }]}>{sevInfo.label}</Text>
          </View>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Ionicons name="chevron-back" size={24} color={Colors.text} />
        </TouchableOpacity>
        <View>
          <Text style={styles.headerTitle}>육아 노트</Text>
          {child && <Text style={styles.headerSub}>{child.name}</Text>}
        </View>
        <TouchableOpacity style={styles.addBtn} onPress={() => setModalVisible(true)}>
          <Ionicons name="add" size={24} color={Colors.primary} />
        </TouchableOpacity>
      </View>

      {/* 카테고리 필터 */}
      <View style={styles.filterContainer}>
        <FlatList
          horizontal
          data={CATEGORY_OPTIONS}
          keyExtractor={(item) => item.key}
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
          renderItem={({ item: cat }) => (
            <TouchableOpacity
              style={[styles.filterTab, selectedCategory === cat.key && styles.filterTabActive]}
              onPress={() => setSelectedCategory(cat.key as NoteCategory | 'all')}
            >
              <Text style={[styles.filterText, selectedCategory === cat.key && styles.filterTextActive]}>
                {cat.label}
              </Text>
            </TouchableOpacity>
          )}
        />
      </View>

      {/* 노트 목록 */}
      {loading ? (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      ) : notes.length === 0 ? (
        <View style={styles.emptyBox}>
          <Ionicons name="book-outline" size={52} color={Colors.primaryLight} />
          <Text style={styles.emptyTitle}>노트가 없습니다</Text>
          <Text style={styles.emptySubtitle}>우측 상단 + 버튼으로 노트를 작성해보세요</Text>
        </View>
      ) : (
        <FlatList
          data={notes}
          keyExtractor={(item) => item.id.toString()}
          renderItem={renderNote}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          ListHeaderComponent={<Text style={styles.countText}>총 {notes.length}개</Text>}
        />
      )}

      {/* 노트 작성 모달 */}
      <Modal
        visible={modalVisible}
        animationType="slide"
        transparent
        presentationStyle="overFullScreen"
      >
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>노트 작성</Text>
              <TouchableOpacity onPress={() => { setModalVisible(false); resetForm(); }}>
                <Ionicons name="close" size={24} color={Colors.text} />
              </TouchableOpacity>
            </View>
            <ScrollView keyboardShouldPersistTaps="handled">
              {/* 카테고리 */}
              <Text style={styles.modalLabel}>
                카테고리 <Text style={{ color: Colors.error }}>*</Text>
              </Text>
              <View style={styles.catGrid}>
                {CATEGORY_OPTIONS.filter((c) => c.key !== 'all').map((cat) => (
                  <TouchableOpacity
                    key={cat.key}
                    style={[
                      styles.catBtn,
                      newCategory === cat.key && { borderColor: cat.color, backgroundColor: cat.color + '15' },
                    ]}
                    onPress={() => setNewCategory(cat.key as NoteCategory)}
                  >
                    <Ionicons
                      name={cat.icon}
                      size={18}
                      color={newCategory === cat.key ? cat.color : Colors.textSecondary}
                    />
                    <Text style={[
                      styles.catBtnText,
                      newCategory === cat.key && { color: cat.color },
                    ]}>
                      {cat.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* 날짜 */}
              <Text style={styles.modalLabel}>
                날짜 <Text style={{ color: Colors.error }}>*</Text>
              </Text>
              <TextInput
                style={styles.modalInput}
                placeholder="YYYY-MM-DD"
                placeholderTextColor={Colors.textTertiary}
                value={newDate}
                onChangeText={setNewDate}
                keyboardType="numeric"
                maxLength={10}
              />

              {/* 제목 */}
              <Text style={styles.modalLabel}>제목 (선택)</Text>
              <TextInput
                style={styles.modalInput}
                placeholder="제목을 입력하세요"
                placeholderTextColor={Colors.textTertiary}
                value={newTitle}
                onChangeText={setNewTitle}
              />

              {/* 내용 */}
              <Text style={styles.modalLabel}>
                내용 <Text style={{ color: Colors.error }}>*</Text>
              </Text>
              <TextInput
                style={[styles.modalInput, styles.modalTextarea]}
                placeholder="내용을 입력하세요"
                placeholderTextColor={Colors.textTertiary}
                value={newContent}
                onChangeText={setNewContent}
                multiline
                numberOfLines={4}
                textAlignVertical="top"
              />

              {/* 측정값 / 단위 */}
              <Text style={styles.modalLabel}>측정값 / 단위 (선택)</Text>
              <View style={styles.rowInput}>
                <TextInput
                  style={[styles.modalInput, { flex: 1 }]}
                  placeholder="예: 38.5"
                  placeholderTextColor={Colors.textTertiary}
                  value={newValue}
                  onChangeText={setNewValue}
                  keyboardType="decimal-pad"
                />
                <TextInput
                  style={[styles.modalInput, { flex: 1 }]}
                  placeholder="예: °C"
                  placeholderTextColor={Colors.textTertiary}
                  value={newUnit}
                  onChangeText={setNewUnit}
                />
              </View>

              {/* 심각도 (증상일 때만) */}
              {newCategory === 'symptom' && (
                <>
                  <Text style={styles.modalLabel}>심각도</Text>
                  <View style={styles.sevRow}>
                    {SEVERITY_OPTIONS.map((s) => (
                      <TouchableOpacity
                        key={s.key}
                        style={[
                          styles.sevBtn,
                          newSeverity === s.key && { borderColor: s.color, backgroundColor: s.color + '20' },
                        ]}
                        onPress={() => setNewSeverity(newSeverity === s.key ? null : s.key as NoteSeverity)}
                      >
                        <Text style={[
                          styles.sevBtnText,
                          newSeverity === s.key && { color: s.color, fontWeight: '700' },
                        ]}>
                          {s.label}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </>
              )}

              <TouchableOpacity
                style={styles.saveBtn}
                onPress={handleCreate}
                disabled={saving}
              >
                {saving ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <>
                    <Ionicons name="checkmark-circle" size={20} color="#fff" />
                    <Text style={styles.saveBtnText}>저장하기</Text>
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
  filterContainer: { backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  filterRow: { paddingHorizontal: 16, paddingVertical: 10, gap: 8 },
  filterTab: {
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 20,
    backgroundColor: Colors.surfaceVariant, borderWidth: 1.5, borderColor: Colors.border,
  },
  filterTabActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  filterText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  filterTextActive: { color: '#fff' },
  loadingBox: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyBox: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: Colors.text, marginTop: 14 },
  emptySubtitle: { fontSize: 13, color: Colors.textSecondary, marginTop: 6, textAlign: 'center' },
  list: { padding: 16, gap: 12 },
  countText: { fontSize: 13, color: Colors.textSecondary, fontWeight: '600', marginBottom: 8 },
  noteCard: {
    backgroundColor: Colors.surface, borderRadius: 16, padding: 16,
    shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 2 }, shadowOpacity: 1, shadowRadius: 8, elevation: 3,
  },
  noteHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  catBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3,
  },
  catBadgeText: { fontSize: 11, fontWeight: '700' },
  noteDate: { fontSize: 12, color: Colors.textTertiary, flex: 1 },
  noteTitle: { fontSize: 15, fontWeight: '700', color: Colors.text, marginBottom: 6 },
  noteContent: { fontSize: 14, color: Colors.textSecondary, lineHeight: 21 },
  noteValue: { fontSize: 15, fontWeight: '700', color: Colors.primary, marginTop: 6 },
  sevBadge: { alignSelf: 'flex-start', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3, marginTop: 8 },
  sevText: { fontSize: 11, fontWeight: '700' },
  modalOverlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.5)' },
  modalSheet: {
    backgroundColor: Colors.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24,
    paddingHorizontal: 20, paddingTop: 20, maxHeight: '92%',
  },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: Colors.text },
  modalLabel: { fontSize: 14, fontWeight: '700', color: Colors.text, marginBottom: 8, marginTop: 16 },
  modalInput: {
    borderWidth: 1.5, borderColor: Colors.border, borderRadius: 12,
    paddingHorizontal: 14, paddingVertical: 12,
    fontSize: 15, color: Colors.text, backgroundColor: Colors.surfaceVariant,
  },
  modalTextarea: { height: 100, paddingTop: 12 },
  catGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  catBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 14, paddingVertical: 10,
    borderWidth: 1.5, borderColor: Colors.border, borderRadius: 12,
    backgroundColor: Colors.surfaceVariant,
  },
  catBtnText: { fontSize: 13, fontWeight: '600', color: Colors.textSecondary },
  rowInput: { flexDirection: 'row', gap: 10 },
  sevRow: { flexDirection: 'row', gap: 10 },
  sevBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 10,
    borderWidth: 1.5, borderColor: Colors.border, borderRadius: 12,
    backgroundColor: Colors.surfaceVariant,
  },
  sevBtnText: { fontSize: 13, fontWeight: '600', color: Colors.textSecondary },
  saveBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: Colors.primary, borderRadius: 16, padding: 16, marginTop: 24,
  },
  saveBtnText: { color: '#fff', fontSize: 17, fontWeight: '700' },
});
