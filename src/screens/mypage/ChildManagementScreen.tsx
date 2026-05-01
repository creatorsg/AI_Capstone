import React, { useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, FlatList, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Colors } from '../../constants/Colors';
import { useChildStore } from '../../store/childStore';
import { Child, RootStackParamList } from '../../types';
import { differenceInMonths, parseISO } from '../../utils/dateUtils';

type NavProp = NativeStackNavigationProp<RootStackParamList>;

export default function ChildManagementScreen() {
  const navigation = useNavigation<NavProp>();
  const { children, fetchChildren, deleteChild } = useChildStore();

  useEffect(() => { fetchChildren(); }, []);

  const handleDelete = (child: Child) => {
    Alert.alert(
      '아이 삭제',
      `${child.name}의 정보를 삭제하시겠습니까?\n삭제된 정보는 복구할 수 없습니다.`,
      [
        { text: '취소', style: 'cancel' },
        {
          text: '삭제', style: 'destructive',
          onPress: async () => {
            try {
              await deleteChild(child.id);
            } catch {
              Alert.alert('오류', '삭제에 실패했습니다.');
            }
          },
        },
      ]
    );
  };

  const getAgeLabel = (birthDate: string) => {
    const months = differenceInMonths(new Date(), parseISO(birthDate));
    if (months < 12) return `${months}개월`;
    return `${Math.floor(months / 12)}세 ${months % 12}개월`;
  };

  const genderEmoji = (gender: string | null) =>
    gender === '남' ? '👦' : gender === '여' ? '👧' : '👶';

  const renderChild = ({ item }: { item: Child }) => (
    <View style={styles.childCard}>
      <View style={styles.emojiBox}>
        <Text style={styles.emojiText}>{genderEmoji(item.gender)}</Text>
      </View>
      <View style={styles.childInfo}>
        <Text style={styles.childName}>{item.name}</Text>
        <Text style={styles.childAge}>{getAgeLabel(item.birth_date)}</Text>
        <Text style={styles.childBirth}>{item.birth_date}</Text>
        {item.allergies.length > 0 && (
          <Text style={styles.detail} numberOfLines={1}>알레르기: {item.allergies.join(', ')}</Text>
        )}
        {item.conditions.length > 0 && (
          <Text style={styles.detail} numberOfLines={1}>기저질환: {item.conditions.join(', ')}</Text>
        )}
      </View>
      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.editBtn}
          onPress={() => navigation.navigate('AddChild', { childId: item.id })}
        >
          <Ionicons name="create-outline" size={18} color={Colors.primary} />
        </TouchableOpacity>
        <TouchableOpacity style={styles.deleteBtn} onPress={() => handleDelete(item)}>
          <Ionicons name="trash-outline" size={18} color={Colors.error} />
        </TouchableOpacity>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Ionicons name="close" size={24} color={Colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>아이 정보 관리</Text>
        <TouchableOpacity
          style={styles.addBtn}
          onPress={() => navigation.navigate('AddChild', {})}
        >
          <Ionicons name="add" size={24} color={Colors.primary} />
        </TouchableOpacity>
      </View>

      {children.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyEmoji}>👶</Text>
          <Text style={styles.emptyTitle}>등록된 아이가 없습니다</Text>
          <Text style={styles.emptySubtitle}>아이를 등록하면 맞춤형 육아 정보를 받을 수 있어요</Text>
          <TouchableOpacity
            style={styles.addFirstButton}
            onPress={() => navigation.navigate('AddChild', {})}
          >
            <Ionicons name="add-circle-outline" size={20} color="#fff" />
            <Text style={styles.addFirstButtonText}>첫 번째 아이 등록</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={children}
          keyExtractor={(item) => item.id.toString()}
          renderItem={renderChild}
          contentContainerStyle={styles.list}
          ListFooterComponent={
            <TouchableOpacity
              style={styles.addMoreButton}
              onPress={() => navigation.navigate('AddChild', {})}
            >
              <Ionicons name="add-circle-outline" size={20} color={Colors.primary} />
              <Text style={styles.addMoreText}>아이 추가하기</Text>
            </TouchableOpacity>
          }
        />
      )}
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
  addBtn: { width: 40, height: 40, justifyContent: 'center', alignItems: 'center' },
  list: { padding: 16, gap: 12 },
  childCard: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    backgroundColor: Colors.surface, borderRadius: 16, padding: 16,
    shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 2 }, shadowOpacity: 1, shadowRadius: 8, elevation: 3,
  },
  emojiBox: { width: 52, height: 52, borderRadius: 26, backgroundColor: Colors.accentLight, justifyContent: 'center', alignItems: 'center' },
  emojiText: { fontSize: 28 },
  childInfo: { flex: 1 },
  childName: { fontSize: 17, fontWeight: '700', color: Colors.text },
  childAge: { fontSize: 13, color: Colors.primary, fontWeight: '600', marginTop: 2 },
  childBirth: { fontSize: 12, color: Colors.textSecondary, marginTop: 2 },
  detail: { fontSize: 12, color: Colors.textSecondary, marginTop: 4 },
  actions: { gap: 8 },
  editBtn: { width: 36, height: 36, borderRadius: 10, backgroundColor: Colors.surfaceVariant, justifyContent: 'center', alignItems: 'center' },
  deleteBtn: { width: 36, height: 36, borderRadius: 10, backgroundColor: Colors.error + '15', justifyContent: 'center', alignItems: 'center' },
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  emptyEmoji: { fontSize: 64 },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: Colors.text, marginTop: 16 },
  emptySubtitle: { fontSize: 14, color: Colors.textSecondary, marginTop: 8, textAlign: 'center' },
  addFirstButton: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: Colors.primary, borderRadius: 16, paddingHorizontal: 24, paddingVertical: 14, marginTop: 24,
  },
  addFirstButtonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  addMoreButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    borderWidth: 1.5, borderColor: Colors.primary, borderStyle: 'dashed',
    borderRadius: 16, padding: 16, marginTop: 4,
  },
  addMoreText: { color: Colors.primary, fontSize: 15, fontWeight: '600' },
});
