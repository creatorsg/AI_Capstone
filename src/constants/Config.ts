export const API_BASE_URL = 'http://52.65.57.123:8000';

export const HOSPITAL_CATEGORIES = [
  { key: '소아청소년과', label: '소아청소년과' },
  { key: '야간소아과', label: '야간소아과' },
  { key: '예방접종병원', label: '예방접종' },
  { key: '아이돌봄센터', label: '아이돌봄' },
  { key: '약국', label: '약국' },
] as const;

export const EXAMPLE_QUESTIONS = [
  '생후 6개월 아기 발달이 궁금해요',
  '아이가 열이 날 때 어떻게 해야 하나요?',
  '예방접종 일정 알려주세요',
  '아이돌봄 서비스 신청 방법이 궁금해요',
  '이유식은 언제부터 시작하나요?',
];
