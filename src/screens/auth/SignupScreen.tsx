import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../constants/Colors';
import { useAuthStore } from '../../store/authStore';
import { AuthStackParamList } from '../../types';

type Props = {
  navigation: NativeStackNavigationProp<AuthStackParamList, 'Signup'>;
};

export default function SignupScreen({ navigation }: Props) {
  const [email, setEmail] = useState('');
  const [nickname, setNickname] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const signup = useAuthStore((s) => s.signup);

  const handleSignup = async () => {
    if (!email.trim() || !nickname.trim() || !password || !confirmPassword) {
      Alert.alert('입력 오류', '모든 항목을 입력해주세요.');
      return;
    }
    if (password !== confirmPassword) {
      Alert.alert('비밀번호 오류', '비밀번호가 일치하지 않습니다.');
      return;
    }
    if (password.length < 8) {
      Alert.alert('비밀번호 오류', '비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    setLoading(true);
    try {
      await signup(email.trim(), password, nickname.trim());
      Alert.alert('가입 완료', '회원가입이 완료되었습니다. 로그인해주세요.', [
        { text: '확인', onPress: () => navigation.navigate('Login') },
      ]);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || '회원가입에 실패했습니다.';
      Alert.alert('가입 실패', msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <TouchableOpacity style={styles.backButton} onPress={() => navigation.goBack()}>
            <Ionicons name="chevron-back" size={24} color={Colors.text} />
          </TouchableOpacity>

          <View style={styles.header}>
            <Text style={styles.title}>회원가입</Text>
            <Text style={styles.subtitle}>육아 도우미 아이톡에 오신 것을 환영해요</Text>
          </View>

          <View style={styles.card}>
            {[
              { label: '이메일', icon: 'mail-outline' as const, value: email, setter: setEmail, placeholder: '이메일을 입력하세요', keyboard: 'email-address' as const, autoCapitalize: 'none' as const },
              { label: '닉네임', icon: 'person-outline' as const, value: nickname, setter: setNickname, placeholder: '닉네임을 입력하세요', keyboard: 'default' as const, autoCapitalize: 'none' as const },
            ].map((field) => (
              <View style={styles.inputGroup} key={field.label}>
                <Text style={styles.label}>{field.label}</Text>
                <View style={styles.inputWrapper}>
                  <Ionicons name={field.icon} size={18} color={Colors.textSecondary} style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder={field.placeholder}
                    placeholderTextColor={Colors.textTertiary}
                    value={field.value}
                    onChangeText={field.setter}
                    keyboardType={field.keyboard}
                    autoCapitalize={field.autoCapitalize}
                    autoCorrect={false}
                  />
                </View>
              </View>
            ))}

            <View style={styles.inputGroup}>
              <Text style={styles.label}>비밀번호</Text>
              <View style={styles.inputWrapper}>
                <Ionicons name="lock-closed-outline" size={18} color={Colors.textSecondary} style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  placeholder="8자 이상 입력하세요"
                  placeholderTextColor={Colors.textTertiary}
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry={!showPw}
                />
                <TouchableOpacity onPress={() => setShowPw(!showPw)} style={styles.eyeButton}>
                  <Ionicons name={showPw ? 'eye-off-outline' : 'eye-outline'} size={18} color={Colors.textSecondary} />
                </TouchableOpacity>
              </View>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>비밀번호 확인</Text>
              <View style={[styles.inputWrapper, confirmPassword && confirmPassword !== password && { borderColor: Colors.error }]}>
                <Ionicons name="lock-closed-outline" size={18} color={Colors.textSecondary} style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  placeholder="비밀번호를 다시 입력하세요"
                  placeholderTextColor={Colors.textTertiary}
                  value={confirmPassword}
                  onChangeText={setConfirmPassword}
                  secureTextEntry={!showPw}
                />
              </View>
              {confirmPassword && confirmPassword !== password && (
                <Text style={styles.errorText}>비밀번호가 일치하지 않습니다</Text>
              )}
            </View>

            <TouchableOpacity style={styles.button} onPress={handleSignup} disabled={loading}>
              {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>가입하기</Text>}
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  keyboardView: { flex: 1 },
  scroll: { flexGrow: 1, padding: 24 },
  backButton: { marginBottom: 16, width: 40 },
  header: { marginBottom: 28 },
  title: { fontSize: 28, fontWeight: '800', color: Colors.text },
  subtitle: { fontSize: 14, color: Colors.textSecondary, marginTop: 6 },
  card: {
    backgroundColor: Colors.surface, borderRadius: 24, padding: 24,
    shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 1, shadowRadius: 24, elevation: 8,
  },
  inputGroup: { marginBottom: 16 },
  label: { fontSize: 13, fontWeight: '600', color: Colors.textSecondary, marginBottom: 8 },
  inputWrapper: {
    flexDirection: 'row', alignItems: 'center',
    borderWidth: 1.5, borderColor: Colors.border,
    borderRadius: 14, backgroundColor: Colors.surfaceVariant,
    paddingHorizontal: 14, height: 52,
  },
  inputIcon: { marginRight: 10 },
  input: { flex: 1, fontSize: 15, color: Colors.text },
  eyeButton: { padding: 4 },
  errorText: { color: Colors.error, fontSize: 12, marginTop: 4 },
  button: {
    backgroundColor: Colors.primary, borderRadius: 14, height: 52,
    justifyContent: 'center', alignItems: 'center', marginTop: 8,
    shadowColor: Colors.primary, shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4, shadowRadius: 12, elevation: 6,
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
});
