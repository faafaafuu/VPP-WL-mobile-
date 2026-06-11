import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { BackendApiClient } from "./api/backendClient";
import { AuthRepository, AuthState } from "./auth/AuthRepository";
import { ConfigRepository, ConfigState } from "./config/configRepository";
import { NodeRepository, NodesState } from "./nodes/NodeRepository";
import { SecureTokenStore } from "./storage/secureStore";
import { VpnController } from "./vpn/VpnController";
import { VpnStatus } from "./vpn/VpnRouterNative";

const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8080";

export default function App() {
  const apiClient = useMemo(() => new BackendApiClient(apiBaseUrl), []);
  const tokenStore = useMemo(() => new SecureTokenStore(), []);
  const authRepository = useMemo(() => new AuthRepository(apiClient, tokenStore), [apiClient, tokenStore]);
  const configRepository = useMemo(() => new ConfigRepository(apiClient, tokenStore), [apiClient, tokenStore]);
  const nodeRepository = useMemo(() => new NodeRepository(apiClient, tokenStore), [apiClient, tokenStore]);
  const controller = useMemo(() => new VpnController(configRepository), [configRepository]);
  const [status, setStatus] = useState<VpnStatus>("disconnected");
  const [configState, setConfigState] = useState<ConfigState>({ kind: "idle" });
  const [authState, setAuthState] = useState<AuthState>({ kind: "idle" });
  const [nodesState, setNodesState] = useState<NodesState>({ kind: "idle" });
  const [deviceId, setDeviceId] = useState("device-1");
  const [receipt, setReceipt] = useState("demo");

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

  async function activateSandboxSubscription() {
    setAuthState({ kind: "activating" });
    const result = await authRepository.activateSandboxReceipt(deviceId, receipt);
    setAuthState(result);
    if (result.kind === "active") {
      setConfigState({ kind: "idle" });
    }
  }

  async function checkSubscription() {
    setAuthState({ kind: "checking" });
    setAuthState(await authRepository.loadCurrentSubscription());
  }

  async function refreshNodes() {
    setNodesState({ kind: "loading" });
    setNodesState(await nodeRepository.loadNodes());
  }

  const buttonLabel = status === "connected" || status === "connecting" ? "Отключить" : "Подключить";

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.screen}>
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

        <View style={styles.subscriptionPanel}>
          <Text style={styles.panelTitle}>Подписка</Text>
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            onChangeText={setDeviceId}
            placeholder="Device ID"
            style={styles.input}
            value={deviceId}
          />
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            onChangeText={setReceipt}
            placeholder="Sandbox receipt"
            secureTextEntry
            style={styles.input}
            value={receipt}
          />
        <Pressable
          disabled={authState.kind === "activating"}
          onPress={activateSandboxSubscription}
          style={[styles.secondaryButton, authState.kind === "activating" ? styles.disabledButton : null]}
        >
            <Text style={styles.secondaryButtonText}>
              {authState.kind === "activating" ? "Проверка..." : "Активировать sandbox"}
            </Text>
        </Pressable>
        <Pressable
          disabled={authState.kind === "checking"}
          onPress={checkSubscription}
          style={[styles.outlineButton, authState.kind === "checking" ? styles.disabledButton : null]}
        >
          <Text style={styles.outlineButtonText}>
            {authState.kind === "checking" ? "Проверка..." : "Проверить подписку"}
          </Text>
        </Pressable>
        <Text style={styles.detailText}>{describeAuthState(authState)}</Text>
      </View>

        <View style={styles.subscriptionPanel}>
          <Text style={styles.panelTitle}>Узлы</Text>
          <Pressable
            disabled={nodesState.kind === "loading"}
            onPress={refreshNodes}
            style={[styles.secondaryButton, nodesState.kind === "loading" ? styles.disabledButton : null]}
          >
            <Text style={styles.secondaryButtonText}>
              {nodesState.kind === "loading" ? "Обновление..." : "Обновить узлы"}
            </Text>
          </Pressable>
          {renderNodes(nodesState)}
        </View>
      </ScrollView>
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

function describeAuthState(state: AuthState): string {
  switch (state.kind) {
    case "active":
      return `Подписка активна до ${state.expiresAt}.`;
    case "activating":
      return "Проверяем receipt через backend.";
    case "checking":
      return "Проверяем сохранённый token.";
    case "auth-required":
      return "Нужна активация подписки.";
    case "subscription-required":
      return "Активная подписка не найдена.";
    case "error":
      return state.message;
    case "idle":
    default:
      return "Receipt не сохраняется на устройстве; сохраняется только access token.";
  }
}

function renderNodes(state: NodesState) {
  switch (state.kind) {
    case "ready":
      if (state.nodes.length === 0) {
        return <Text style={styles.detailText}>Нет доступных узлов.</Text>;
      }
      return (
        <View style={styles.nodeList}>
          {state.nodes.slice(0, 4).map((node) => (
            <View key={node.id} style={styles.nodeRow}>
              <Text style={styles.nodeTitle}>
                {node.region} · {node.protocol}
              </Text>
              <Text style={styles.detailText}>
                {node.provider} · {node.health} · score {node.score} · {node.latency_ms ?? "n/a"} ms
              </Text>
            </View>
          ))}
        </View>
      );
    case "loading":
      return <Text style={styles.detailText}>Загружаем список узлов.</Text>;
    case "auth-required":
      return <Text style={styles.detailText}>Сначала активируйте подписку.</Text>;
    case "error":
      return <Text style={styles.detailText}>{state.message}</Text>;
    case "idle":
    default:
      return <Text style={styles.detailText}>Список узлов нужен только для диагностики.</Text>;
  }
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#f7f7f4"
  },
  screen: {
    backgroundColor: "#f7f7f4",
    flexGrow: 1,
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
  subscriptionPanel: {
    backgroundColor: "#ffffff",
    borderColor: "#deded8",
    borderRadius: 8,
    borderWidth: 1,
    gap: 12,
    padding: 18
  },
  panelTitle: {
    color: "#202124",
    fontSize: 18,
    fontWeight: "700"
  },
  input: {
    borderColor: "#c9cbc7",
    borderRadius: 8,
    borderWidth: 1,
    color: "#202124",
    fontSize: 16,
    minHeight: 46,
    paddingHorizontal: 12
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
  secondaryButton: {
    alignItems: "center",
    backgroundColor: "#202124",
    borderRadius: 8,
    minHeight: 46,
    justifyContent: "center"
  },
  disabledButton: {
    opacity: 0.55
  },
  secondaryButtonText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "700"
  },
  outlineButton: {
    alignItems: "center",
    backgroundColor: "#ffffff",
    borderColor: "#202124",
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 46,
    justifyContent: "center"
  },
  outlineButtonText: {
    color: "#202124",
    fontSize: 15,
    fontWeight: "700"
  },
  nodeList: {
    gap: 10
  },
  nodeRow: {
    borderColor: "#e2e2dc",
    borderRadius: 8,
    borderWidth: 1,
    gap: 4,
    padding: 12
  },
  nodeTitle: {
    color: "#202124",
    fontSize: 15,
    fontWeight: "700"
  },
  detailText: {
    color: "#555b60",
    fontSize: 14,
    lineHeight: 20
  }
});
