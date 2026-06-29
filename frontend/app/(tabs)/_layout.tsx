import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { Platform, StyleSheet, View } from 'react-native';
import { colors } from '@/src/theme/tokens';

function TabBarBg() {
  return (
    <BlurView
      intensity={Platform.OS === 'ios' ? 60 : 90}
      tint="dark"
      style={StyleSheet.absoluteFill}
    >
      <View style={{ flex: 1, backgroundColor: 'rgba(5,5,5,0.78)' }} />
    </BlurView>
  );
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brand,
        tabBarInactiveTintColor: colors.onSurfaceSecondary,
        tabBarStyle: {
          position: 'absolute',
          borderTopColor: colors.border,
          borderTopWidth: StyleSheet.hairlineWidth,
          backgroundColor: 'transparent',
          height: 84,
          paddingTop: 10,
          paddingBottom: 24,
          elevation: 0,
        },
        tabBarBackground: () => <TabBarBg />,
        tabBarLabelStyle: { fontSize: 11, fontWeight: '500', marginTop: 2 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'sparkles' : 'sparkles-outline'} size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="portfolio"
        options={{
          title: 'Portfolio',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'apps' : 'apps-outline'} size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="coach"
        options={{
          title: 'AI Coach',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'flash' : 'flash-outline'} size={24} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="finance"
        options={{
          title: 'Finance',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'pulse' : 'pulse-outline'} size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={focused ? 'person-circle' : 'person-circle-outline'} size={24} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
