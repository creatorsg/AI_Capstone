import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, FlatList,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert,
  ScrollView, Animated, Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../constants/Colors';
import { useChildStore } from '../../store/childStore';
import { chatAPI } from '../../services/api';
import { ChatMessage, Child, ChatHistoryItem, SessionHistory } from '../../types';
import { EXAMPLE_QUESTIONS } from '../../constants/Config';
import { differenceInMonths, parseISO } from '../../utils/dateUtils';

const SIDEBAR_WIDTH = Dimensions.get('window').width * 0.82;

export default function ChatScreen() {
  const { children, selectedChild, selectChild, fetchChildren } = useChildStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [showChildPicker, setShowChildPicker] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historyItems, setHistoryItems] = useState<ChatHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [resumeLoading, setResumeLoading] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  // 사이드바 애니메이션
  const sidebarAnim = useRef(new Animated.Value(-SIDEBAR_WIDTH)).current;
  const overlayAnim = useRef(new Animated.Value(0)).current;

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
        needs_more_context: data.needs_more_context,
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

  const openHistory = async () => {
    if (!selectedChild) {
      Alert.alert('아이 선택', '대화할 아이를 먼저 선택해주세요.');
      setShowChildPicker(true);
      return;
    }
    setShowHistory(true);
    setHistoryLoading(true);
    Animated.parallel([
      Animated.spring(sidebarAnim, {
        toValue: 0,
        useNativeDriver: true,
        damping: 20,
        stiffness: 180,
        mass: 1,
      }),
      Animated.timing(overlayAnim, {
        toValue: 1,
        duration: 220,
        useNativeDriver: true,
      }),
    ]).start();
    try {
      const { data } = await chatAPI.history(selectedChild.id, 30);
      setHistoryItems(Array.isArray(data) ? data : []);
    } catch {
      Alert.alert('오류', '채팅 기록을 불러오지 못했습니다.');
    } finally {
      setHistoryLoading(false);
    }
  };

  const closeHistory = () => {
    Animated.parallel([
      Animated.timing(sidebarAnim, {
        toValue: -SIDEBAR_WIDTH,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(overlayAnim, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start(() => setShowHistory(false));
  };

  const resumeSession = async (targetSessionId: string) => {
    setResumeLoading(true);
    try {
      const { data }: { data: SessionHistory } = await chatAPI.sessionHistory(targetSessionId);
      const loaded: ChatMessage[] = [];
      for (const turn of data.turns) {
        if (turn.question) {
          loaded.push({ id: `h-q-${turn.id}`, role: 'user', content: turn.question });
        }
        if (turn.answer) {
          loaded.push({ id: `h-a-${turn.id}`, role: 'assistant', content: turn.answer });
        }
      }
      setMessages(loaded);
      setSessionId(targetSessionId);
      closeHistory();
    } catch {
      Alert.alert('오류', '대화 기록을 불러오지 못했습니다.');
    } finally {
      setResumeLoading(false);
    }
  };

  const groupedSessions = (() => {
    const seen = new Set<string>();
    return historyItems.filter((item) => {
      if (seen.has(item.session_id)) return false;
      seen.add(item.session_id);
      return true;
    });
  })();

  const formatHistoryDate = (isoStr: string) => {
    const d = new Date(isoStr);
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  const ageLabel = selectedChild
    ? (() => {
        const months = differenceInMonths(new Date(), parseISO(selectedChild.birth_date));
        return months < 12 ? `${months}개월` : `${Math.floor(months / 12)}세 ${months % 12}개월`;
      })()
    : '';

  const genderEmoji = (child: Child) =>
    child.gender === 'male' ? '👦' : child.gender === 'female' ? '👧' : '👶';

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
        {item.needs_more_context && (
          <View style={styles.contextTag}>
            <Ionicons name="chatbubble-ellipses-outline" size={12} color={Colors.primary} />
            <Text style={styles.contextTagText}>추가 정보 확인 중</Text>
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
      {/* 헤더와 메시지 영역을 KeyboardAvoidingView로 감싸서 키보드 이슈 방지 */}
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        {/* 헤더 */}
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <Text style={styles.headerTitle}>아이톡 챗봇</Text>
            {selectedChild && (
              <Text style={styles.headerSub}>{selectedChild.name} · {ageLabel}</Text>
            )}
          </View>
          <View style={styles.headerRight}>
            <TouchableOpacity style={styles.headerBtn} onPress={openHistory}>
              <Ionicons name="time-outline" size={22} color={Colors.primary} />
            </TouchableOpacity>
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
                    <Text style={styles.childIconText}>{genderEmoji(child)}</Text>
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

        {/* 메시지 목록 */}
        {messages.length === 0 ? (
          <ScrollView
            style={styles.flex}
            contentContainerStyle={styles.emptyContainer}
            keyboardShouldPersistTaps="handled"
          >
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
          </ScrollView>
        ) : (
          <FlatList
            ref={flatListRef}
            data={messages}
            keyExtractor={(item) => item.id}
            renderItem={renderMessage}
            contentContainerStyle={styles.messageList}
            onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
            keyboardShouldPersistTaps="handled"
          />
        )}

        {/* 전송 중 로딩 표시 */}
        {sending && (
          <View style={styles.typingRow}>
            <View style={styles.avatar}>
              <Ionicons name="happy" size={18} color={Colors.primary} />
            </View>
            <View style={styles.typingBubble}>
              <ActivityIndicator size="small" color={Colors.primary} />
              <Text style={styles.typingText}>답변을 생성하고 있습니다...</Text>
            </View>
          </View>
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

      {/* 왼쪽 슬라이드 채팅 기록 사이드바 */}
      {showHistory && (
        <View style={StyleSheet.absoluteFill} pointerEvents="box-none">
          {/* 배경 오버레이 */}
          <Animated.View
            style={[StyleSheet.absoluteFill, styles.sidebarBackdrop, { opacity: overlayAnim }]}
            pointerEvents="auto"
          >
            <TouchableOpacity style={StyleSheet.absoluteFill} onPress={closeHistory} activeOpacity={1} />
          </Animated.View>

          {/* 사이드바 패널 */}
          <Animated.View
            style={[styles.sidebar, { transform: [{ translateX: sidebarAnim }] }]}
            pointerEvents="auto"
          >
            <SafeAreaView style={styles.sidebarInner} edges={['top', 'bottom']}>
              {/* 사이드바 헤더 */}
              <View style={styles.sidebarHeader}>
                <Text style={styles.sidebarTitle}>채팅 기록</Text>
                <TouchableOpacity style={styles.sidebarCloseBtn} onPress={closeHistory}>
                  <Ionicons name="close" size={22} color={Colors.text} />
                </TouchableOpacity>
              </View>

              {/* 현재 선택된 아이 표시 */}
              {selectedChild && (
                <View style={styles.sidebarChildBadge}>
                  <Ionicons name="person-circle-outline" size={16} color={Colors.primary} />
                  <Text style={styles.sidebarChildName}>{selectedChild.name}의 대화</Text>
                </View>
              )}

              {/* 기록 목록 */}
              {historyLoading ? (
                <View style={styles.sidebarLoading}>
                  <ActivityIndicator size="large" color={Colors.primary} />
                  <Text style={styles.sidebarLoadingText}>불러오는 중...</Text>
                </View>
              ) : groupedSessions.length === 0 ? (
                <View style={styles.sidebarEmpty}>
                  <Ionicons name="chatbubbles-outline" size={44} color={Colors.primaryLight} />
                  <Text style={styles.sidebarEmptyText}>채팅 기록이 없습니다</Text>
                </View>
              ) : (
                <ScrollView contentContainerStyle={styles.sidebarList} showsVerticalScrollIndicator={false}>
                  {groupedSessions.map((item) => (
                    <TouchableOpacity
                      key={item.session_id}
                      style={[
                        styles.sidebarCard,
                        sessionId === item.session_id && styles.sidebarCardActive,
                      ]}
                      onPress={() => resumeSession(item.session_id)}
                      disabled={resumeLoading}
                      activeOpacity={0.75}
                    >
                      <View style={styles.sidebarCardRow}>
                        <Ionicons
                          name="chatbubble-outline"
                          size={14}
                          color={sessionId === item.session_id ? Colors.primary : Colors.textSecondary}
                        />
                        <Text style={styles.sidebarDate}>{formatHistoryDate(item.created_at)}</Text>
                        {sessionId === item.session_id && (
                          <View style={styles.currentBadge}>
                            <Text style={styles.currentBadgeText}>현재</Text>
                          </View>
                        )}
                      </View>
                      <Text style={styles.sidebarQuestion} numberOfLines={2}>{item.question}</Text>
                      <Text style={styles.sidebarAnswer} numberOfLines={1}>{item.answer}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              )}

              {/* 새 대화 버튼 */}
              <TouchableOpacity
                style={styles.newChatButton}
                onPress={() => { resetChat(); closeHistory(); }}
              >
                <Ionicons name="add-circle-outline" size={18} color="#fff" />
                <Text style={styles.newChatButtonText}>새 대화 시작</Text>
              </TouchableOpacity>
            </SafeAreaView>
          </Animated.View>
        </View>
      )}
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
  emptyContainer: { flexGrow: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
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
  contextTag: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 6 },
  contextTagText: { fontSize: 11, fontWeight: '600', color: Colors.primary },
  bubbleText: { fontSize: 15, lineHeight: 22 },
  userBubbleText: { color: Colors.userBubbleText },
  aiBubbleText: { color: Colors.aiBubbleText },
  emergencyText: { color: Colors.emergency },
  typingRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 8 },
  typingBubble: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: Colors.aiBubble, borderRadius: 18, padding: 12 },
  typingText: { fontSize: 13, color: Colors.textSecondary },
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
  // 사이드바
  sidebarBackdrop: { backgroundColor: 'rgba(0,0,0,0.45)' },
  sidebar: {
    position: 'absolute', top: 0, left: 0, bottom: 0,
    width: SIDEBAR_WIDTH,
    backgroundColor: Colors.surface,
    shadowColor: '#000', shadowOffset: { width: 4, height: 0 },
    shadowOpacity: 0.18, shadowRadius: 16, elevation: 12,
  },
  sidebarInner: { flex: 1 },
  sidebarHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  sidebarTitle: { fontSize: 18, fontWeight: '800', color: Colors.text },
  sidebarCloseBtn: { padding: 4 },
  sidebarChildBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 20, paddingVertical: 10,
    backgroundColor: Colors.primaryLight + '20',
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  sidebarChildName: { fontSize: 13, color: Colors.primary, fontWeight: '700' },
  sidebarLoading: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  sidebarLoadingText: { color: Colors.textSecondary, fontSize: 14 },
  sidebarEmpty: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12, paddingHorizontal: 24 },
  sidebarEmptyText: { fontSize: 14, color: Colors.textSecondary, fontWeight: '600', textAlign: 'center' },
  sidebarList: { padding: 12, gap: 8, paddingBottom: 16 },
  sidebarCard: {
    backgroundColor: Colors.surfaceVariant, borderRadius: 14, padding: 14,
    borderWidth: 1, borderColor: Colors.border,
  },
  sidebarCardActive: {
    backgroundColor: Colors.primaryLight + '20',
    borderColor: Colors.primary,
  },
  sidebarCardRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  sidebarDate: { fontSize: 11, color: Colors.textTertiary, fontWeight: '600', flex: 1 },
  currentBadge: { backgroundColor: Colors.primary, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  currentBadgeText: { fontSize: 10, color: '#fff', fontWeight: '700' },
  sidebarQuestion: { fontSize: 13, fontWeight: '700', color: Colors.text, marginBottom: 4, lineHeight: 18 },
  sidebarAnswer: { fontSize: 12, color: Colors.textSecondary, lineHeight: 17 },
  newChatButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    margin: 16, backgroundColor: Colors.primary, borderRadius: 14, paddingVertical: 14,
    shadowColor: Colors.primary, shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.35, shadowRadius: 8, elevation: 4,
  },
  newChatButtonText: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
