import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, KeyboardAvoidingView, Platform, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Colors } from '../../constants/Colors';
import { useChildStore } from '../../store/childStore';
import { RootStackParamList } from '../../types';

type NavProp = NativeStackNavigationProp<RootStackParamList>;
type RoutePropType = RouteProp<RootStackParamList, 'AddChild'>;

export default function AddChildScreen() {
  const navigation = useNavigation<NavProp>();
  const route = useRoute<RoutePropType>();
  const childId = route.params?.childId;
  const isEdit = !!childId;

  const { children, addChild, updateChild } = useChildStore();
  const existing = isEdit ? children.find((c) => c.id === childId) : null;

  const [name, setName] = useState(existing?.name || '');
  const [birthDate, setBirthDate] = useState(existing?.birth_date || '');
  const [gender, setGender] = useState<'남' | '여' | null>(
    existing?.gender === 'male' ? '남' : existing?.gender === 'female' ? '여' : null
  );
  const [allergiesInput, setAllergiesInput] = useState(existing?.allergies.join(', ') || '');
  const [conditionsInput, setConditionsInput] = useState(existing?.conditions.join(', ') || '');
  const [notes, setNotes] = useState(existing?.notes || '');
  const [loading, setLoading] = useState(false);

  const validateDate = (val: string) => /^\d{4}-\d{2}-\d{2}$/.test(val);

  const handleSave = async () => {
    if (!name.trim()) { Alert.alert('입력 오류', '이름을 입력해주세요.'); return; }
    if (!birthDate.trim() || !validateDate(birthDate)) {
      Alert.alert('입력 오류', '생년월일을 YYYY-MM-DD 형식으로 입력해주세요.\n예: 2023-03-15');
      return;
    }
    const birthDateObj = new Date(birthDate);
    if (birthDateObj > new Date()) {
      Alert.alert('입력 오류', '생년월일은 오늘 이전이어야 합니다.');
      return;
    }

    const data = {
      name: name.trim(),
      birth_date: birthDate,
      gender: gender === '남' ? 'male' : gender === '여' ? 'female' : null,
      allergies: allergiesInput.split(',').map((s) => s.trim()).filter(Boolean),
      conditions: conditionsInput.split(',').map((s) => s.trim()).filter(Boolean),
      notes: notes.trim(),
    };

    setLoading(true);
    try {
      if (isEdit && childId) {
        await updateChild(childId, data);
        Alert.alert('완료', '아이 정보가 수정되었습니다.', [{ text: '확인', onPress: () => navigation.goBack() }]);
      } else {
        await addChild(data as any);
        Alert.alert('완료', '아이가 등록되었습니다.', [{ text: '확인', onPress: () => navigation.goBack() }]);
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const msg = Array.isArray(detail)
        ? detail.map((e: any) => e.msg).join('\n')
        : (detail || (isEdit ? '수정에 실패했습니다.' : '등록에 실패했습니다.'));
      Alert.alert('오류', msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.closeBtn} onPress={() => navigation.goBack()}>
          <Ionicons name="close" size={24} color={Colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{isEdit ? '아이 정보 수정' : '아이 등록'}</Text>
        <View style={{ width: 40 }} />
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.card}>
            {/* 이름 */}
            <View style={styles.field}>
              <Text style={styles.label}>이름 <Text style={styles.required}>*</Text></Text>
              <TextInput
                style={styles.input}
                placeholder="아이 이름"
                placeholderTextColor={Colors.textTertiary}
                value={name}
                onChangeText={setName}
              />
            </View>

            {/* 생년월일 */}
            <View style={styles.field}>
              <Text style={styles.label}>생년월일 <Text style={styles.required}>*</Text></Text>
              <TextInput
                style={styles.input}
                placeholder="YYYY-MM-DD (예: 2023-03-15)"
                placeholderTextColor={Colors.textTertiary}
                value={birthDate}
                onChangeText={setBirthDate}
                keyboardType="numeric"
                maxLength={10}
              />
            </View>

            {/* 성별 */}
            <View style={styles.field}>
              <Text style={styles.label}>성별</Text>
              <View style={styles.genderRow}>
                {[{ label: '남아', value: '남' as const, emoji: '👦' }, { label: '여아', value: '여' as const, emoji: '👧' }].map((g) => (
                  <TouchableOpacity
                    key={g.value}
                    style={[styles.genderBtn, gender === g.value && styles.genderBtnActive]}
                    onPress={() => setGender(gender === g.value ? null : g.value)}
                  >
                    <Text style={styles.genderEmoji}>{g.emoji}</Text>
                    <Text style={[styles.genderText, gender === g.value && styles.genderTextActive]}>
                      {g.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* 알레르기 */}
            <View style={styles.field}>
              <Text style={styles.label}>알레르기</Text>
              <Text style={styles.hint}>쉼표로 구분해서 입력 (예: 달걀, 우유, 견과류)</Text>
              <TextInput
                style={styles.input}
                placeholder="알레르기 없음"
                placeholderTextColor={Colors.textTertiary}
                value={allergiesInput}
                onChangeText={setAllergiesInput}
              />
            </View>

            {/* 기저질환 */}
            <View style={styles.field}>
              <Text style={styles.label}>기저질환</Text>
              <Text style={styles.hint}>쉼표로 구분해서 입력</Text>
              <TextInput
                style={styles.input}
                placeholder="기저질환 없음"
                placeholderTextColor={Colors.textTertiary}
                value={conditionsInput}
                onChangeText={setConditionsInput}
              />
            </View>

            {/* 특이사항 */}
            <View style={styles.field}>
              <Text style={styles.label}>특이사항</Text>
              <TextInput
                style={[styles.input, styles.textarea]}
                placeholder="아이에 대해 더 알려주세요"
                placeholderTextColor={Colors.textTertiary}
                value={notes}
                onChangeText={setNotes}
                multiline
                numberOfLines={3}
                textAlignVertical="top"
              />
            </View>
          </View>

          <TouchableOpacity style={styles.saveButton} onPress={handleSave} disabled={loading}>
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Ionicons name={isEdit ? 'checkmark-circle' : 'add-circle'} size={20} color="#fff" />
                <Text style={styles.saveButtonText}>{isEdit ? '수정 완료' : '등록하기'}</Text>
              </>
            )}
          </TouchableOpacity>

          <View style={{ height: 40 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  flex: { flex: 1 },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  closeBtn: { width: 40, height: 40, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '700', color: Colors.text },
  scroll: { padding: 16 },
  card: {
    backgroundColor: Colors.surface, borderRadius: 20, padding: 20,
    shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 4 }, shadowOpacity: 1, shadowRadius: 16, elevation: 6,
    marginBottom: 16,
  },
  field: { marginBottom: 20 },
  label: { fontSize: 14, fontWeight: '700', color: Colors.text, marginBottom: 8 },
  required: { color: Colors.error },
  hint: { fontSize: 12, color: Colors.textSecondary, marginBottom: 6 },
  input: {
    borderWidth: 1.5, borderColor: Colors.border, borderRadius: 12,
    paddingHorizontal: 14, paddingVertical: 12,
    fontSize: 15, color: Colors.text, backgroundColor: Colors.surfaceVariant,
  },
  textarea: { height: 90, paddingTop: 12 },
  genderRow: { flexDirection: 'row', gap: 12 },
  genderBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    borderWidth: 1.5, borderColor: Colors.border, borderRadius: 12, padding: 14,
    backgroundColor: Colors.surfaceVariant,
  },
  genderBtnActive: { borderColor: Colors.primary, backgroundColor: Colors.primary + '15' },
  genderEmoji: { fontSize: 22 },
  genderText: { fontSize: 15, fontWeight: '600', color: Colors.textSecondary },
  genderTextActive: { color: Colors.primary },
  saveButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: Colors.primary, borderRadius: 16, padding: 16,
    shadowColor: Colors.primary, shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.4, shadowRadius: 12, elevation: 6,
  },
  saveButtonText: { color: '#fff', fontSize: 17, fontWeight: '700' },
});
