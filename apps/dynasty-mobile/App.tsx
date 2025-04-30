import React, { useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { registerRootComponent } from 'expo';
// import { registerForPush } from './lib/notifications';
// import Dashboard from './screens/Dashboard';
// import Trades from './screens/Trades';

// TODO: Implement real notifications and screens. Placeholder components below.
const Dashboard = () => <></>;
const Trades = () => <></>;

import { Ionicons } from '@expo/vector-icons';

const Tab = createBottomTabNavigator();

function App() {
  // useEffect(() => {
  //   registerForPush();
  // }, []);

  return (
    <NavigationContainer>
      <Tab.Navigator>
        <Tab.Screen name="Dashboard" component={Dashboard} options={{
          tabBarIcon: ({ color, size }) => <Ionicons name="ios-pie-chart" size={size} color={color} />,
        }} />
        <Tab.Screen name="Trades" component={Trades} options={{
          tabBarIcon: ({ color, size }) => <Ionicons name="ios-list" size={size} color={color} />,
        }} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

registerRootComponent(App);
export default App;
