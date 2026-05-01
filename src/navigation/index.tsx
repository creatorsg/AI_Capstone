import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { ActivityIndicator, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useAuthStore } from '../store/authStore';
import { Colors } from '../constants/Colors';
import { RootStackParamList, AuthStackParamList, MainTabParamList } from '../types';

import LoginScreen from '../screens/auth/LoginScreen';
import SignupScreen from '../screens/auth/SignupScreen';
import ChatScreen from '../screens/chat/ChatScreen';
import HospitalsScreen from '../screens/hospitals/HospitalsScreen';
import WelfareScreen from '../screens/welfare/WelfareScreen';
import MyPageScreen from '../screens/mypage/MyPageScreen';
import ChildManagementScreen from '../screens/mypage/ChildManagementScreen';
import AddChildScreen from '../screens/mypage/AddChildScreen';

const RootStack = createNativeStackNavigator<RootStackParamList>();
const AuthStack = createNativeStackNavigator<AuthStackParamList>();
const Tab = createBottomTabNavigator<MainTabParamList>();

function AuthNavigator() {
  return (
    <AuthStack.Navigator screenOptions={{ headerShown: false }}>
      <AuthStack.Screen name="Login" component={LoginScreen} />
      <AuthStack.Screen name="Signup" component={SignupScreen} />
    </AuthStack.Navigator>
  );
}

function MainTabs() {
  const insets = useSafeAreaInsets();

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused, color, size }) => {
          const icons: Record<string, keyof typeof Ionicons.glyphMap> = {
            Chat: focused ? 'chatbubbles' : 'chatbubbles-outline',
            Hospitals: focused ? 'medical' : 'medical-outline',
            Welfare: focused ? 'document-text' : 'document-text-outline',
            MyPage: focused ? 'person' : 'person-outline',
          };
          return <Ionicons name={icons[route.name]} size={size} color={color} />;
        },
        tabBarActiveTintColor: Colors.tabBarActive,
        tabBarInactiveTintColor: Colors.tabBarInactive,
        tabBarStyle: {
          backgroundColor: Colors.tabBar,
          borderTopColor: Colors.border,
          height: 60 + insets.bottom,
          paddingBottom: 8 + insets.bottom,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
        headerShown: false,
      })}
    >
      <Tab.Screen name="Chat" component={ChatScreen} options={{ tabBarLabel: '챗봇' }} />
      <Tab.Screen name="Hospitals" component={HospitalsScreen} options={{ tabBarLabel: '병원 찾기' }} />
      <Tab.Screen name="Welfare" component={WelfareScreen} options={{ tabBarLabel: '복지정책' }} />
      <Tab.Screen name="MyPage" component={MyPageScreen} options={{ tabBarLabel: '마이페이지' }} />
    </Tab.Navigator>
  );
}

export default function AppNavigator() {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.background }}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <RootStack.Navigator screenOptions={{ headerShown: false }}>
        {isAuthenticated ? (
          <>
            <RootStack.Screen name="Main" component={MainTabs} />
            <RootStack.Screen
              name="ChildManagement"
              component={ChildManagementScreen}
              options={{ presentation: 'modal', headerShown: false }}
            />
            <RootStack.Screen
              name="AddChild"
              component={AddChildScreen}
              options={{ presentation: 'modal', headerShown: false }}
            />
          </>
        ) : (
          <RootStack.Screen name="Auth" component={AuthNavigator} />
        )}
      </RootStack.Navigator>
    </NavigationContainer>
  );
}
