import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  FlatList, ActivityIndicator, Alert, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { Colors } from '../../constants/Colors';
import { hospitalsAPI } from '../../services/api';
import { Hospital } from '../../types';
import { HOSPITAL_CATEGORIES } from '../../constants/Config';

export default function HospitalsScreen() {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(false);
  const [locationLoading, setLocationLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>(HOSPITAL_CATEGORIES[0].key);
  const [hasLocation, setHasLocation] = useState(false);
  const [userLocation, setUserLocation] = useState<{ lat: number; lon: number } | null>(null);

  const fetchNearby = async (lat: number, lon: number, category: string) => {
    setLoading(true);
    try {
      const { data } = await hospitalsAPI.nearbyStatic(lat, lon, 5000, category);
      const list = Array.isArray(data) ? data : data.hospitals || data.results || [];
      setHospitals(list);
    } catch {
      Alert.alert('오류', '병원 정보를 가져오는 데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const requestLocation = async () => {
    setLocationLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('위치 권한', '병원 검색을 위해 위치 권한이 필요합니다.');
        return;
      }
      const location = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const { latitude, longitude } = location.coords;
      setUserLocation({ lat: latitude, lon: longitude });
      setHasLocation(true);
      fetchNearby(latitude, longitude, selectedCategory);
    } catch {
      Alert.alert('오류', '위치를 가져올 수 없습니다.');
    } finally {
      setLocationLoading(false);
    }
  };

  const handleCategoryChange = (category: string) => {
    setSelectedCategory(category);
    if (userLocation) {
      fetchNearby(userLocation.lat, userLocation.lon, category);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const { data } = await hospitalsAPI.search(searchQuery.trim());
      const list = Array.isArray(data) ? data : data.hospitals || data.results || [];
      setHospitals(list);
    } catch {
      Alert.alert('오류', '검색에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const getDistance = (hospital: Hospital) => {
    const d = hospital.distance;
    if (!d) return null;
    const meters = typeof d === 'string' ? parseFloat(d) : d;
    if (isNaN(meters)) return null;
    return meters >= 1000 ? `${(meters / 1000).toFixed(1)}km` : `${Math.round(meters)}m`;
  };

  const getAddress = (h: Hospital) => h.address || h.road_address || '주소 정보 없음';
  const getTitle = (h: Hospital) => h.title || h.place_name || '병원';

  const renderHospital = ({ item }: { item: Hospital }) => (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={styles.cardIcon}>
          <Ionicons name="medical" size={20} color={Colors.primary} />
        </View>
        <View style={styles.cardInfo}>
          <Text style={styles.hospitalName} numberOfLines={1}>{getTitle(item)}</Text>
          {getDistance(item) && (
            <View style={styles.distanceBadge}>
              <Ionicons name="location" size={12} color={Colors.primary} />
              <Text style={styles.distanceText}>{getDistance(item)}</Text>
            </View>
          )}
        </View>
      </View>
      <Text style={styles.address} numberOfLines={2}>{getAddress(item)}</Text>
      {item.phone && (
        <TouchableOpacity
          style={styles.phoneRow}
          onPress={() => Linking.openURL(`tel:${item.phone}`)}
        >
          <Ionicons name="call-outline" size={14} color={Colors.primary} />
          <Text style={styles.phone}>{item.phone}</Text>
        </TouchableOpacity>
      )}
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>병원 찾기</Text>
        <Text style={styles.headerSub}>주변의 소아과 및 관련 시설을 찾아보세요</Text>
      </View>

      {/* 검색창 */}
      <View style={styles.searchContainer}>
        <View style={styles.searchBar}>
          <Ionicons name="search-outline" size={18} color={Colors.textSecondary} />
          <TextInput
            style={styles.searchInput}
            placeholder="병원명 또는 지역 검색"
            placeholderTextColor={Colors.textTertiary}
            value={searchQuery}
            onChangeText={setSearchQuery}
            onSubmitEditing={handleSearch}
            returnKeyType="search"
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => { setSearchQuery(''); }}>
              <Ionicons name="close-circle" size={18} color={Colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
        <TouchableOpacity style={styles.searchButton} onPress={handleSearch}>
          <Text style={styles.searchButtonText}>검색</Text>
        </TouchableOpacity>
      </View>

      {/* 카테고리 탭 */}
      <View style={styles.categoryRow}>
        {HOSPITAL_CATEGORIES.map((cat) => (
          <TouchableOpacity
            key={cat.key}
            style={[styles.categoryTab, selectedCategory === cat.key && styles.categoryTabActive]}
            onPress={() => handleCategoryChange(cat.key)}
          >
            <Text style={[styles.categoryText, selectedCategory === cat.key && styles.categoryTextActive]}>
              {cat.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* 내 위치 기반 검색 */}
      {!hasLocation && (
        <TouchableOpacity style={styles.locationButton} onPress={requestLocation} disabled={locationLoading}>
          {locationLoading ? (
            <ActivityIndicator size="small" color={Colors.primary} />
          ) : (
            <>
              <Ionicons name="location-outline" size={20} color={Colors.primary} />
              <Text style={styles.locationButtonText}>내 위치로 주변 병원 찾기</Text>
            </>
          )}
        </TouchableOpacity>
      )}

      {hasLocation && (
        <TouchableOpacity style={styles.refreshLocation} onPress={requestLocation}>
          <Ionicons name="refresh-outline" size={16} color={Colors.primary} />
          <Text style={styles.refreshLocationText}>위치 새로고침</Text>
        </TouchableOpacity>
      )}

      {/* 결과 목록 */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.loadingText}>병원 정보를 불러오고 있습니다...</Text>
        </View>
      ) : hospitals.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Ionicons name="medical-outline" size={56} color={Colors.primaryLight} />
          <Text style={styles.emptyTitle}>병원 정보가 없습니다</Text>
          <Text style={styles.emptySubtitle}>위치 기반 검색 또는 키워드 검색을 이용해보세요</Text>
        </View>
      ) : (
        <FlatList
          data={hospitals}
          keyExtractor={(_, i) => i.toString()}
          renderItem={renderHospital}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          ListHeaderComponent={
            <Text style={styles.resultCount}>총 {hospitals.length}개의 결과</Text>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 12, backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  headerTitle: { fontSize: 22, fontWeight: '800', color: Colors.text },
  headerSub: { fontSize: 13, color: Colors.textSecondary, marginTop: 4 },
  searchContainer: { flexDirection: 'row', gap: 10, paddingHorizontal: 16, paddingVertical: 12, backgroundColor: Colors.surface },
  searchBar: {
    flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: Colors.surfaceVariant, borderRadius: 12, paddingHorizontal: 14,
    borderWidth: 1.5, borderColor: Colors.border, height: 46,
  },
  searchInput: { flex: 1, fontSize: 14, color: Colors.text },
  searchButton: { backgroundColor: Colors.primary, borderRadius: 12, paddingHorizontal: 16, justifyContent: 'center' },
  searchButtonText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  categoryRow: { flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 10, gap: 8, backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  categoryTab: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 20, backgroundColor: Colors.surfaceVariant, borderWidth: 1.5, borderColor: Colors.border },
  categoryTabActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  categoryText: { fontSize: 12, fontWeight: '600', color: Colors.textSecondary },
  categoryTextActive: { color: '#fff' },
  locationButton: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    marginHorizontal: 16, marginVertical: 12, padding: 16,
    backgroundColor: Colors.surface, borderRadius: 16,
    borderWidth: 1.5, borderColor: Colors.primary, borderStyle: 'dashed',
    justifyContent: 'center',
  },
  locationButtonText: { fontSize: 15, fontWeight: '600', color: Colors.primary },
  refreshLocation: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingVertical: 8 },
  refreshLocationText: { fontSize: 13, color: Colors.primary, fontWeight: '600' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { color: Colors.textSecondary, fontSize: 14 },
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: Colors.text, marginTop: 16 },
  emptySubtitle: { fontSize: 14, color: Colors.textSecondary, marginTop: 8, textAlign: 'center' },
  list: { padding: 16, gap: 12 },
  resultCount: { fontSize: 13, color: Colors.textSecondary, marginBottom: 8, fontWeight: '600' },
  card: {
    backgroundColor: Colors.surface, borderRadius: 16, padding: 16,
    shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1, shadowRadius: 8, elevation: 3,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 8 },
  cardIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: Colors.surfaceVariant, justifyContent: 'center', alignItems: 'center' },
  cardInfo: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  hospitalName: { fontSize: 15, fontWeight: '700', color: Colors.text, flex: 1 },
  distanceBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: Colors.primaryLight + '30', borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3 },
  distanceText: { fontSize: 12, color: Colors.primary, fontWeight: '600' },
  address: { fontSize: 13, color: Colors.textSecondary, lineHeight: 18 },
  phoneRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 },
  phone: { fontSize: 13, color: Colors.primary, fontWeight: '600' },
});
