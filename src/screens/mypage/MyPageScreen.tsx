import React from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Alert, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { Colors } from '../../constants/Colors';
import { useAuthStore } from '../../store/authStore';
import { useChildStore } from '../../store/childStore';
import { RootStackParamList } from '../../types';
import { differenceInMonths, parseISO } from '../../utils/dateUtils';

type NavProp = NativeStackNavigationProp<RootStackParamList>;

export default function MyPageScreen() {
  const navigation = useNavigation<NavProp>();
  const { user, logout } = useAuthStore();
  const { children, selectedChild, selectChild } = useChildStore();

  const handleLogout = () => {
    Alert.alert('로그아웃', '정말 로그아웃 하시겠습니까?', [
      { text: '취소', style: 'cancel' },
      { text: '로그아웃', style: 'destructive', onPress: logout },
    ]);
  };

  const getAgeLabel = (birthDate: string) => {
    const months = differenceInMonths(new Date(), parseISO(birthDate));
    if (months < 12) return `${months}개월`;
    return `${Math.floor(months / 12)}세 ${months % 12}개월`;
  };

  const genderEmoji = (gender: string | null) =>
    gender === '남' ? '👦' : gender === '여' ? '👧' : '👶';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* 프로필 헤더 */}
        <View style={styles.profileCard}>
          <View style={styles.avatar}>
            <Ionicons name="person" size={36} color={Colors.primary} />
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.nickname}>{user?.nickname}님</Text>
            <Text style={styles.email}>{user?.email}</Text>
          </View>
        </View>

        {/* 아이 목록 */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>우리 아이</Text>
            <TouchableOpacity
              style={styles.addButton}
              onPress={() => navigation.navigate('ChildManagement')}
            >
              <Ionicons name="settings-outline" size={18} color={Colors.primary} />
              <Text style={styles.addButtonText}>관리</Text>
            </TouchableOpacity>
          </View>

          {children.length === 0 ? (
            <TouchableOpacity
              style={styles.addChildPrompt}
              onPress={() => navigation.navigate('ChildManagement')}
            >
              <Ionicons name="add-circle-outline" size={32} color={Colors.primary} />
              <Text style={styles.addChildText}>아이를 등록해보세요</Text>
              <Text style={styles.addChildSub}>아이 정보를 등록하면 맞춤형 육아 정보를 받을 수 있어요</Text>
            </TouchableOpacity>
          ) : (
            children.map((child) => (
              <TouchableOpacity
                key={child.id}
                style={[styles.childCard, selectedChild?.id === child.id && styles.childCardActive]}
                onPress={() => selectChild(child)}
              >
                <View style={styles.childEmoji}>
                  <Text style={styles.emojiText}>{genderEmoji(child.gender)}</Text>
                </View>
                <View style={styles.childDetails}>
                  <Text style={styles.childName}>{child.name}</Text>
                  <Text style={styles.childAge}>{getAgeLabel(child.birth_date)}</Text>
                  {(child.allergies.length > 0 || child.conditions.length > 0) && (
                    <View style={styles.tagRow}>
                      {child.allergies.slice(0, 2).map((a, i) => (
                        <View key={i} style={styles.tag}>
                          <Text style={styles.tagText}>알레르기: {a}</Text>
                        </View>
                      ))}
                      {child.conditions.slice(0, 2).map((c, i) => (
                        <View key={i} style={[styles.tag, styles.tagWarning]}>
                          <Text style={[styles.tagText, styles.tagTextWarning]}>{c}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                </View>
                {selectedChild?.id === child.id && (
                  <View style={styles.selectedBadge}>
                    <Ionicons name="checkmark-circle" size={24} color={Colors.primary} />
                  </View>
                )}
              </TouchableOpacity>
            ))
          )}
        </View>

        {/* 메뉴 */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>앱 정보</Text>
          <View style={styles.menuCard}>
            {[
              { icon: 'information-circle-outline' as const, label: '앱 버전', value: '1.0.0' },
              { icon: 'shield-checkmark-outline' as const, label: '개인정보처리방침', value: '' },
              { icon: 'document-text-outline' as const, label: '이용약관', value: '' },
            ].map((item, i) => (
              <View key={i} style={[styles.menuItem, i < 2 && styles.menuBorder]}>
                <Ionicons name={item.icon} size={20} color={Colors.textSecondary} />
                <Text style={styles.menuLabel}>{item.label}</Text>
                <Text style={styles.menuValue}>{item.value}</Text>
                {!item.value && <Ionicons name="chevron-forward" size={16} color={Colors.textTertiary} />}
              </View>
            ))}
          </View>
        </View>

        {/* 로그아웃 */}
        <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={20} color={Colors.error} />
          <Text style={styles.logoutText}>로그아웃</Text>
        </TouchableOpacity>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  profileCard: {
    flexDirection: 'row', alignItems: 'center', gap: 16,
    backgroundColor: Colors.primary, padding: 24,
    paddingTop: 20,
  },
  avatar: {
    width: 68, height: 68, borderRadius: 34,
    backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center',
  },
  profileInfo: {},
  nickname: { fontSize: 22, fontWeight: '800', color: '#fff' },
  email: { fontSize: 13, color: 'rgba(255,255,255,0.8)', marginTop: 4 },
  section: { margin: 16, marginBottom: 0 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 17, fontWeight: '700', color: Colors.text },
  addButton: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: Colors.surfaceVariant, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 10 },
  addButtonText: { fontSize: 13, color: Colors.primary, fontWeight: '600' },
  addChildPrompt: {
    alignItems: 'center', padding: 28, backgroundColor: Colors.surface,
    borderRadius: 16, borderWidth: 1.5, borderColor: Colors.border, borderStyle: 'dashed',
  },
  addChildText: { fontSize: 16, fontWeight: '700', color: Colors.text, marginTop: 10 },
  addChildSub: { fontSize: 13, color: Colors.textSecondary, marginTop: 6, textAlign: 'center' },
  childCard: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    backgroundColor: Colors.surface, borderRadius: 16, padding: 16, marginBottom: 10,
    shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 2 }, shadowOpacity: 1, shadowRadius: 8, elevation: 3,
  },
  childCardActive: { borderWidth: 2, borderColor: Colors.primary },
  childEmoji: { width: 52, height: 52, borderRadius: 26, backgroundColor: Colors.accentLight, justifyContent: 'center', alignItems: 'center' },
  emojiText: { fontSize: 28 },
  childDetails: { flex: 1 },
  childName: { fontSize: 17, fontWeight: '700', color: Colors.text },
  childAge: { fontSize: 13, color: Colors.primary, fontWeight: '600', marginTop: 2 },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 },
  tag: { backgroundColor: Colors.error + '15', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  tagWarning: { backgroundColor: Colors.warning + '30' },
  tagText: { fontSize: 11, color: Colors.error, fontWeight: '600' },
  tagTextWarning: { color: Colors.warning },
  selectedBadge: {},
  menuCard: { backgroundColor: Colors.surface, borderRadius: 16, overflow: 'hidden', shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 2 }, shadowOpacity: 1, shadowRadius: 8, elevation: 3 },
  menuItem: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16 },
  menuBorder: { borderBottomWidth: 1, borderBottomColor: Colors.border },
  menuLabel: { flex: 1, fontSize: 15, color: Colors.text },
  menuValue: { fontSize: 14, color: Colors.textSecondary },
  logoutButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    margin: 16, marginTop: 20, padding: 16,
    backgroundColor: Colors.surface, borderRadius: 16,
    borderWidth: 1.5, borderColor: Colors.error + '40',
  },
  logoutText: { fontSize: 16, fontWeight: '700', color: Colors.error },
});
