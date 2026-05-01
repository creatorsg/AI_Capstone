// Android 에뮬레이터: http://10.0.2.2:8000
// iOS 시뮬레이터: http://localhost:8000
// 실제 기기(Expo Go): http://<컴퓨터의 로컬 IP>:8000
export const API_BASE_URL = 'http://192.168.123.109:8000';

export const HOSPITAL_CATEGORIES = [
  { key: '소아청소년과', label: '소아청소년과' },
  { key: '야간소아과', label: '야간소아과' },
  { key: '예방접종병원', label: '예방접종' },
  { key: '아이돌봄센터', label: '아이돌봄' },
] as const;

export const EXAMPLE_QUESTIONS = [
  '생후 6개월 아기 발달이 궁금해요',
  '아이가 열이 날 때 어떻게 해야 하나요?',
  '예방접종 일정 알려주세요',
  '아이돌봄 서비스 신청 방법이 궁금해요',
  '이유식은 언제부터 시작하나요?',
];
