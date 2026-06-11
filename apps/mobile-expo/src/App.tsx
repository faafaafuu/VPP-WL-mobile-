import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, SafeAreaView, StyleSheet, Text, View } from "react-native";

import { BackendApiClient } from "./api/backendClient";
import { ConfigRepository, ConfigState } from "./config/configRepository";
import { SecureTokenStore } from "./storage/secureStore";
import { VpnController } from "./vpn/VpnController";
import { VpnStatus } from "./vpn/VpnRouterNative";

const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8080";

export default function App() {
  const repository = useMemo(
    () => new ConfigRepository(new BackendApiClient(apiBaseUrl), new SecureTokenStore()),
    []
  );
  const controller = useMemo(() => new VpnController(repository), [repository]);
  const [status, setStatus] = useState<VpnStatus>("disconnected");
  const [configState, setConfigState] = useState<ConfigState>({ kind: "idle" });

  useEffect(() => {
    controller.status().then(setStatus).catch(() => setStatus("error"));
  }, [controller]);

  async function toggleVpn() {
    if (status === "connected" || status === "connecting") {
      await controller.stop();
      setStatus("disconnected");
      return;
    }

    setStatus("connecting");
    const result = await controller.start();
    setConfigState(result.configState);
    setStatus(result.status);
  }

  const buttonLabel = status === "connected" || status === "connecting" ? "Отключить" : "Подключить";

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.title}>VPN Router</Text>
        <Text style={styles.subtitle}>RU-сайты напрямую, остальное через VPN</Text>
      </View>

      <View style={styles.statusPanel}>
        <Text style={styles.statusLabel}>Статус</Text>
        <Text style={styles.statusValue}>{status}</Text>
        {status === "connecting" ? <ActivityIndicator /> : null}
      </View>

      <Pressable style={styles.primaryButton} onPress={toggleVpn}>
        <Text style={styles.primaryButtonText}>{buttonLabel}</Text>
      </Pressable>

      <Text style={styles.detailText}>{describeConfigState(configState)}</Text>
    </SafeAreaView>
  );
}

function describeConfigState(state: ConfigState): string {
  switch (state.kind) {
    case "fresh":
      return "Конфиг обновлён с backend.";
    case "last-known-good":
      return "Backend недоступен, используется последний рабочий конфиг.";
    case "auth-required":
      return "Нужна авторизация или повторная покупка.";
    case "subscription-required":
      return "Подписка не активна.";
    case "error":
      return state.message;
    case "idle":
    default:
      return "Трафик не логируется. Токены и конфиги хранятся в защищённом хранилище.";
  }
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#f7f7f4",
    paddingHorizontal: 24,
    paddingVertical: 32,
    gap: 24
  },
  header: {
    gap: 8
  },
  title: {
    color: "#202124",
    fontSize: 32,
    fontWeight: "700"
  },
  subtitle: {
    color: "#555b60",
    fontSize: 16,
    lineHeight: 22
  },
  statusPanel: {
    backgroundColor: "#ffffff",
    borderColor: "#deded8",
    borderRadius: 8,
    borderWidth: 1,
    padding: 18,
    gap: 8
  },
  statusLabel: {
    color: "#6b7075",
    fontSize: 13,
    textTransform: "uppercase"
  },
  statusValue: {
    color: "#202124",
    fontSize: 24,
    fontWeight: "600"
  },
  primaryButton: {
    alignItems: "center",
    backgroundColor: "#1b6f5f",
    borderRadius: 8,
    minHeight: 52,
    justifyContent: "center"
  },
  primaryButtonText: {
    color: "#ffffff",
    fontSize: 17,
    fontWeight: "700"
  },
  detailText: {
    color: "#555b60",
    fontSize: 14,
    lineHeight: 20
  }
});
