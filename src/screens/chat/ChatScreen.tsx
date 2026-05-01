import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, FlatList,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert, Pressable,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../constants/Colors';
import { useChildStore } from '../../store/childStore';
import { chatAPI } from '../../services/api';
import { ChatMessage, Child } from '../../types';
import { EXAMPLE_QUESTIONS } from '../../constants/Config';
import { differenceInMonths, parseISO } from '../../utils/dateUtils';

export default function ChatScreen() {
  const { children, selectedChild, selectChild, fetchChildren } = useChildStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [showChildPicker, setShowChildPicker] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    fetchChildren();
  }, []);

  const resetChat = useCallback(() => {
    setMessages([]);
    setSessionId(null);
  }, []);

  useEffect(() => {
    resetChat();
  }, [selectedChild?.id]);

  const sendMessage = async (text: string) => {
    if (!selectedChild) {
      Alert.alert('아이 선택', '대화할 아이를 먼저 선택해주세요.');
      setShowChildPicker(true);
      return;
    }
    const trimmed = text.trim();
    if (!trimmed) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setSending(true);

    try {
      const { data } = await chatAPI.send(selectedChild.id, trimmed, sessionId);
      setSessionId(data.session_id);

      const aiMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.message,
        is_emergency: data.is_emergency,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      const detailMsg = Array.isArray(detail)
        ? detail.map((e: any) => e.msg).join(', ')
        : detail;
      const content = detailMsg
        ? `오류 (${status}): ${detailMsg}`
        : err?.message === 'Network Error'
        ? '서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.'
        : `죄송합니다. 답변을 가져오는 데 실패했습니다. (${status ?? err?.message})`;
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setSending(false);
      setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
    }
  };

  const ageLabel = selectedChild
    ? (() => {
        const months = differenceInMonths(new Date(), parseISO(selectedChild.birth_date));
        return months < 12 ? `${months}개월` : `${Math.floor(months / 12)}세 ${months % 12}개월`;
      })()
    : '';

  const renderMessage = ({ item }: { item: ChatMessage }) => (
    <View style={[styles.messageRow, item.role === 'user' ? styles.userRow : styles.aiRow]}>
      {item.role === 'assistant' && (
        <View style={styles.avatar}>
          <Ionicons name="happy" size={18} color={Colors.primary} />
        </View>
      )}
      <View style={[
        styles.bubble,
        item.role === 'user' ? styles.userBubble : styles.aiBubble,
        item.is_emergency && styles.emergencyBubble,
      ]}>
        {item.is_emergency && (
          <View style={styles.emergencyTag}>
            <Ionicons name="warning" size={14} color={Colors.emergency} />
            <Text style={styles.emergencyTagText}>응급 상황 주의</Text>
          </View>
        )}
        <Text style={[
          styles.bubbleText,
          item.role === 'user' ? styles.userBubbleText : styles.aiBubbleText,
          item.is_emergency && styles.emergencyText,
        ]}>
          {item.content}
        </Text>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* 헤더 */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.headerTitle}>아이톡 챗봇</Text>
          {selectedChild && (
            <Text style={styles.headerSub}>{selectedChild.name} · {ageLabel}</Text>
          )}
        </View>
        <View style={styles.headerRight}>
          <TouchableOpacity style={styles.headerBtn} onPress={() => setShowChildPicker(true)}>
            <Ionicons name="people-outline" size={22} color={Colors.primary} />
          </TouchableOpacity>
          <TouchableOpacity style={styles.headerBtn} onPress={resetChat}>
            <Ionicons name="refresh-outline" size={22} color={Colors.primary} />
          </TouchableOpacity>
        </View>
      </View>

      {/* 아이 선택 패널 */}
      {showChildPicker && (
        <View style={styles.childPicker}>
          <View style={styles.childPickerHeader}>
            <Text style={styles.childPickerTitle}>대화할 아이 선택</Text>
            <TouchableOpacity onPress={() => setShowChildPicker(false)}>
              <Ionicons name="close" size={22} color={Colors.textSecondary} />
            </TouchableOpacity>
          </View>
          {children.length === 0 ? (
            <Text style={styles.noChildText}>등록된 아이가 없습니다. 마이페이지에서 추가해주세요.</Text>
          ) : (
            children.map((child) => (
              <TouchableOpacity
                key={child.id}
                style={[styles.childItem, selectedChild?.id === child.id && styles.childItemActive]}
                onPress={() => { selectChild(child); setShowChildPicker(false); }}
              >
                <View style={styles.childIcon}>
                  <Text style={styles.childIconText}>{child.gender === '남' ? '👦' : child.gender === '여' ? '👧' : '👶'}</Text>
                </View>
                <View>
                  <Text style={styles.childName}>{child.name}</Text>
                  <Text style={styles.childBirth}>{child.birth_date}</Text>
                </View>
                {selectedChild?.id === child.id && (
                  <Ionicons name="checkmark-circle" size={20} color={Colors.primary} style={{ marginLeft: 'auto' }} />
                )}
              </TouchableOpacity>
            ))
          )}
        </View>
      )}

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={0}
      >
        {/* 메시지 목록 */}
        {messages.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="chatbubbles-outline" size={56} color={Colors.primaryLight} />
            <Text style={styles.emptyTitle}>
              {selectedChild ? `${selectedChild.name}에 대해 물어보세요` : '아이를 선택하고 질문해보세요'}
            </Text>
            <Text style={styles.emptySubtitle}>육아, 건강, 발달, 복지 등 무엇이든 물어보세요</Text>
            <View style={styles.exampleList}>
              {EXAMPLE_QUESTIONS.slice(0, 4).map((q, i) => (
                <TouchableOpacity key={i} style={styles.exampleItem} onPress={() => sendMessage(q)}>
                  <Ionicons name="chatbubble-outline" size={14} color={Colors.primary} />
                  <Text style={styles.exampleText}>{q}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        ) : (
          <FlatList
            ref={flatListRef}
            data={messages}
            keyExtractor={(item) => item.id}
            renderItem={renderMessage}
            contentContainerStyle={styles.messageList}
            onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
          />
        )}

        {/* 입력창 */}
        <View style={styles.inputBar}>
          <View style={styles.inputContainer}>
            <TextInput
              style={styles.textInput}
              placeholder="메시지를 입력하세요..."
              placeholderTextColor={Colors.textTertiary}
              value={input}
              onChangeText={setInput}
              multiline
              maxLength={500}
            />
            <TouchableOpacity
              style={[styles.sendButton, (!input.trim() || sending) && styles.sendButtonDisabled]}
              onPress={() => sendMessage(input)}
              disabled={!input.trim() || sending}
            >
              {sending ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <Ionicons name="send" size={18} color="#fff" />
              )}
            </TouchableOpacity>
          </View>
        </View>
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
  headerLeft: {},
  headerTitle: { fontSize: 18, fontWeight: '700', color: Colors.text },
  headerSub: { fontSize: 12, color: Colors.primary, marginTop: 2, fontWeight: '600' },
  headerRight: { flexDirection: 'row', gap: 4 },
  headerBtn: { padding: 8 },
  childPicker: {
    backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border,
    paddingHorizontal: 16, paddingBottom: 12,
  },
  childPickerHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 12 },
  childPickerTitle: { fontSize: 15, fontWeight: '700', color: Colors.text },
  noChildText: { color: Colors.textSecondary, fontSize: 14, paddingBottom: 8 },
  childItem: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    padding: 12, borderRadius: 12, marginBottom: 8,
    backgroundColor: Colors.surfaceVariant,
  },
  childItemActive: { backgroundColor: Colors.primaryLight + '30', borderWidth: 1.5, borderColor: Colors.primary },
  childIcon: { width: 40, height: 40, borderRadius: 20, backgroundColor: Colors.accentLight, justifyContent: 'center', alignItems: 'center' },
  childIconText: { fontSize: 20 },
  childName: { fontSize: 15, fontWeight: '700', color: Colors.text },
  childBirth: { fontSize: 12, color: Colors.textSecondary },
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: Colors.text, marginTop: 16, textAlign: 'center' },
  emptySubtitle: { fontSize: 14, color: Colors.textSecondary, marginTop: 8, textAlign: 'center' },
  exampleList: { width: '100%', marginTop: 24, gap: 8 },
  exampleItem: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: Colors.surface, borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: Colors.border,
  },
  exampleText: { fontSize: 14, color: Colors.text, flex: 1 },
  messageList: { paddingHorizontal: 16, paddingVertical: 12, gap: 12 },
  messageRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 8 },
  userRow: { justifyContent: 'flex-end' },
  aiRow: { justifyContent: 'flex-start' },
  avatar: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: Colors.surfaceVariant, justifyContent: 'center', alignItems: 'center',
  },
  bubble: { maxWidth: '78%', borderRadius: 18, padding: 14 },
  userBubble: { backgroundColor: Colors.userBubble, borderBottomRightRadius: 4 },
  aiBubble: { backgroundColor: Colors.aiBubble, borderBottomLeftRadius: 4 },
  emergencyBubble: { backgroundColor: Colors.emergencyLight, borderWidth: 1.5, borderColor: Colors.emergency },
  emergencyTag: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 6 },
  emergencyTagText: { fontSize: 12, fontWeight: '700', color: Colors.emergency },
  bubbleText: { fontSize: 15, lineHeight: 22 },
  userBubbleText: { color: Colors.userBubbleText },
  aiBubbleText: { color: Colors.aiBubbleText },
  emergencyText: { color: Colors.emergency },
  inputBar: { paddingHorizontal: 16, paddingVertical: 12, backgroundColor: Colors.surface, borderTopWidth: 1, borderTopColor: Colors.border },
  inputContainer: { flexDirection: 'row', alignItems: 'flex-end', gap: 10 },
  textInput: {
    flex: 1, backgroundColor: Colors.surfaceVariant,
    borderRadius: 24, paddingHorizontal: 16, paddingVertical: 12,
    fontSize: 15, color: Colors.text, maxHeight: 120,
    borderWidth: 1.5, borderColor: Colors.border,
  },
  sendButton: {
    width: 46, height: 46, borderRadius: 23,
    backgroundColor: Colors.primary, justifyContent: 'center', alignItems: 'center',
    shadowColor: Colors.primary, shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4, shadowRadius: 8, elevation: 4,
  },
  sendButtonDisabled: { backgroundColor: Colors.textTertiary, shadowOpacity: 0 },
});
