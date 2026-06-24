import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  StatusBar,
  View
} from "react-native";

import { BackendApiClient } from "./api/backendClient";
import { AuthRepository, AuthState } from "./auth/AuthRepository";
import { ConfigRepository, ConfigState } from "./config/configRepository";
import { NodeRepository, NodesState } from "./nodes/NodeRepository";
import { SecureTokenStore } from "./storage/secureStore";
import { VersionRepository, VersionState } from "./version/VersionRepository";
import { VpnController } from "./vpn/VpnController";
import { VpnStatus } from "./vpn/VpnRouterNative";

const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8080";
const privacyUrl = process.env.EXPO_PUBLIC_PRIVACY_URL ?? "https://example.com/privacy";
const termsUrl = process.env.EXPO_PUBLIC_TERMS_URL ?? "https://example.com/terms";

export default function App() {
  const apiClient = useMemo(() => new BackendApiClient(apiBaseUrl), []);
  const tokenStore = useMemo(() => new SecureTokenStore(), []);
  const authRepository = useMemo(() => new AuthRepository(apiClient, tokenStore), [apiClient, tokenStore]);
  const configRepository = useMemo(() => new ConfigRepository(apiClient, tokenStore), [apiClient, tokenStore]);
  const nodeRepository = useMemo(() => new NodeRepository(apiClient, tokenStore), [apiClient, tokenStore]);
  const versionRepository = useMemo(() => new VersionRepository(apiClient), [apiClient]);
  const controller = useMemo(() => new VpnController(configRepository), [configRepository]);
  const [status, setStatus] = useState<VpnStatus>("disconnected");
  const [configState, setConfigState] = useState<ConfigState>({ kind: "idle" });
  const [authState, setAuthState] = useState<AuthState>({ kind: "idle" });
  const [nodesState, setNodesState] = useState<NodesState>({ kind: "idle" });
  const [versionState, setVersionState] = useState<VersionState>({ kind: "idle" });
  const [deviceId, setDeviceId] = useState("device-1");
  const [receipt, setReceipt] = useState("demo");
  const [showAccountTools, setShowAccountTools] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  useEffect(() => {
    controller.status().then(setStatus).catch(() => setStatus("error"));
  }, [controller]);

  async function toggleVpn() {
    if (status === "connected" || status === "connecting") {
      try {
        await controller.stop();
        setStatus("disconnected");
      } catch (error) {
        setStatus("error");
        setConfigState({
          kind: "error",
          message: error instanceof Error ? error.message : "Unable to stop VPN"
        });
      }
      return;
    }

    setStatus("connecting");
    try {
      const result = await controller.start();
      setConfigState(result.configState);
      setStatus(result.status);
    } catch (error) {
      setConfigState({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to start VPN"
      });
      setStatus("error");
    }
  }

  async function activateSandboxSubscription() {
    setAuthState({ kind: "activating" });
    const result = await authRepository.activateSandboxReceipt(deviceId, receipt);
    setAuthState(result);
    if (result.kind === "active") {
      setConfigState({ kind: "idle" });
    }
  }

  async function createYooKassaPayment() {
    setAuthState({ kind: "activating" });
    const result = await authRepository.createYooKassaPayment(deviceId);
    setAuthState(result);
    if (result.kind === "payment-created") {
      setReceipt(result.paymentId);
      Linking.openURL(result.confirmationUrl).catch(() => undefined);
    }
  }

  async function activateYooKassaPayment() {
    setAuthState({ kind: "activating" });
    const result = await authRepository.activateYooKassaPayment(deviceId, receipt);
    setAuthState(result);
    if (result.kind === "active") {
      setConfigState({ kind: "idle" });
    }
  }

  async function initUser() {
    setAuthState({ kind: "initializing" });
    setAuthState(await authRepository.initDevice(deviceId));
  }

  async function checkSubscription() {
    setAuthState({ kind: "checking" });
    setAuthState(await authRepository.loadCurrentSubscription());
  }

  async function exportAccountData() {
    setAuthState({ kind: "exporting" });
    setAuthState(await authRepository.exportAccountData());
  }

  function confirmDeleteAccount() {
    Alert.alert("Удалить аккаунт", "Токен и последний рабочий конфиг будут очищены на устройстве.", [
      { text: "Отмена", style: "cancel" },
      {
        text: "Удалить",
        style: "destructive",
        onPress: async () => {
          setAuthState({ kind: "deleting" });
          const result = await authRepository.deleteAccount();
          setAuthState(result);
          if (result.kind === "deleted") {
            setConfigState({ kind: "idle" });
            setStatus("disconnected");
          }
        }
      }
    ]);
  }

  async function refreshNodes() {
    setNodesState({ kind: "loading" });
    setNodesState(await nodeRepository.loadNodes());
  }

  async function refreshVersion() {
    setVersionState({ kind: "loading" });
    setVersionState(await versionRepository.loadVersion());
  }

  const isConnected = status === "connected";
  const isConnecting = status === "connecting";
  const buttonLabel = isConnected || isConnecting ? "Disconnect" : "Connect";
  const statusLabel = isConnected ? "Protected" : isConnecting ? "Connecting" : status === "error" ? "Needs attention" : "Ready";
  const connectionHint = isConnected
    ? "Split routing is active. RU services stay direct."
    : isConnecting
      ? "Fetching config and preparing secure tunnel."
      : "Tap once and VPN Router will choose the route automatically.";

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" backgroundColor="#F6F7F9" />
      <ScrollView contentContainerStyle={styles.screen}>
        <View style={styles.header}>
          <Text style={styles.title}>VPN Router</Text>
          <Text style={styles.subtitle}>RU-сайты напрямую, остальное через VPN</Text>
        </View>

        <View style={styles.connectionPanel}>
          <View style={styles.statusRow}>
            <View style={[styles.statusDot, isConnected ? styles.statusDotActive : isConnecting ? styles.statusDotBusy : null]} />
            <View style={styles.statusCopy}>
              <Text style={styles.statusLabel}>Status</Text>
              <Text style={styles.statusValue}>{statusLabel}</Text>
            </View>
            {isConnecting ? <ActivityIndicator color="#1F7A5C" /> : null}
          </View>

          <Pressable
            accessibilityRole="button"
            accessibilityLabel={buttonLabel}
            disabled={isConnecting}
            onPress={toggleVpn}
            style={({ pressed }) => [
              styles.powerButton,
              isConnected ? styles.powerButtonActive : null,
              isConnecting ? styles.powerButtonDisabled : null,
              pressed ? styles.pressed : null
            ]}
          >
            <Text style={styles.powerButtonText}>{buttonLabel}</Text>
          </Pressable>

          <Text style={styles.connectionHint}>{connectionHint}</Text>
          <Text style={styles.configState}>{describeConfigState(configState)}</Text>
        </View>

        <View style={styles.routePanel}>
          <Text style={styles.panelTitle}>Smart routing</Text>
          <View style={styles.routeGrid}>
            <View style={styles.routeItem}>
              <Text style={styles.routeLabel}>Direct</Text>
              <Text style={styles.routeValue}>.ru, банки, госы</Text>
            </View>
            <View style={styles.routeItem}>
              <Text style={styles.routeLabel}>VPN</Text>
              <Text style={styles.routeValue}>Telegram, YouTube, OpenAI</Text>
            </View>
          </View>
        </View>

        <View style={styles.panel}>
          <View style={styles.panelHeader}>
            <View>
              <Text style={styles.panelTitle}>Subscription</Text>
              <Text style={styles.detailText}>{describeAuthState(authState)}</Text>
            </View>
          </View>
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
          <View style={styles.buttonGrid}>
            <Pressable
              disabled={authState.kind === "initializing"}
              onPress={initUser}
              style={[styles.outlineButton, styles.gridButton, authState.kind === "initializing" ? styles.disabledButton : null]}
            >
              <Text style={styles.outlineButtonText}>
                {authState.kind === "initializing" ? "Creating..." : "Create user"}
              </Text>
            </Pressable>
            <Pressable
              disabled={authState.kind === "activating"}
              onPress={activateSandboxSubscription}
              style={[styles.secondaryButton, styles.gridButton, authState.kind === "activating" ? styles.disabledButton : null]}
            >
              <Text style={styles.secondaryButtonText}>
                {authState.kind === "activating" ? "Checking..." : "Sandbox"}
              </Text>
            </Pressable>
          </View>
          <Pressable
            disabled={authState.kind === "activating"}
            onPress={createYooKassaPayment}
            style={[styles.secondaryButton, authState.kind === "activating" ? styles.disabledButton : null]}
          >
            <Text style={styles.secondaryButtonText}>
              {authState.kind === "activating" ? "Creating..." : "Pay with YooKassa"}
            </Text>
          </Pressable>
          <View style={styles.linkRow}>
            <Pressable style={styles.linkButton} onPress={() => Linking.openURL(privacyUrl)}>
              <Text style={styles.linkButtonText}>Privacy</Text>
            </Pressable>
            <Pressable style={styles.linkButton} onPress={() => Linking.openURL(termsUrl)}>
              <Text style={styles.linkButtonText}>Terms</Text>
            </Pressable>
          </View>
          <Pressable
            onPress={() => setShowAccountTools((value) => !value)}
            style={styles.textButton}
          >
            <Text style={styles.textButtonText}>{showAccountTools ? "Hide account tools" : "Account tools"}</Text>
          </Pressable>
          {showAccountTools ? (
            <View style={styles.accountTools}>
              <View style={styles.buttonGrid}>
                <Pressable
                  disabled={authState.kind === "activating"}
                  onPress={activateYooKassaPayment}
                  style={[styles.outlineButton, styles.gridButton, authState.kind === "activating" ? styles.disabledButton : null]}
                >
                  <Text style={styles.outlineButtonText}>
                    {authState.kind === "activating" ? "Checking..." : "Confirm pay"}
                  </Text>
                </Pressable>
                <Pressable
                  disabled={authState.kind === "checking"}
                  onPress={checkSubscription}
                  style={[styles.outlineButton, styles.gridButton, authState.kind === "checking" ? styles.disabledButton : null]}
                >
                  <Text style={styles.outlineButtonText}>
                    {authState.kind === "checking" ? "Checking..." : "Check plan"}
                  </Text>
                </Pressable>
              </View>
              <View style={styles.buttonGrid}>
                <Pressable
                  disabled={authState.kind === "exporting"}
                  onPress={exportAccountData}
                  style={[styles.outlineButton, styles.gridButton, authState.kind === "exporting" ? styles.disabledButton : null]}
                >
                  <Text style={styles.outlineButtonText}>
                    {authState.kind === "exporting" ? "Exporting..." : "Export data"}
                  </Text>
                </Pressable>
                <Pressable
                  disabled={authState.kind === "deleting"}
                  onPress={confirmDeleteAccount}
                  style={[styles.dangerButton, styles.gridButton, authState.kind === "deleting" ? styles.disabledButton : null]}
                >
                  <Text style={styles.dangerButtonText}>
                    {authState.kind === "deleting" ? "Deleting..." : "Delete"}
                  </Text>
                </Pressable>
              </View>
              {authState.kind === "exported" ? (
                <Text style={styles.exportText} selectable>
                  {authState.exportedJson}
                </Text>
              ) : null}
            </View>
          ) : null}
        </View>

        <View style={styles.panel}>
          <Pressable onPress={() => setShowDiagnostics((value) => !value)} style={styles.panelToggle}>
            <Text style={styles.panelTitle}>Diagnostics</Text>
            <Text style={styles.textButtonText}>{showDiagnostics ? "Hide" : "Show"}</Text>
          </Pressable>
          {showDiagnostics ? (
            <View style={styles.accountTools}>
              <Pressable
                disabled={nodesState.kind === "loading"}
                onPress={refreshNodes}
                style={[styles.secondaryButton, nodesState.kind === "loading" ? styles.disabledButton : null]}
              >
                <Text style={styles.secondaryButtonText}>
                  {nodesState.kind === "loading" ? "Updating..." : "Refresh nodes"}
                </Text>
              </Pressable>
              {renderNodes(nodesState)}
              <Pressable
                disabled={versionState.kind === "loading"}
                onPress={refreshVersion}
                style={[styles.outlineButton, versionState.kind === "loading" ? styles.disabledButton : null]}
              >
                <Text style={styles.outlineButtonText}>
                  {versionState.kind === "loading" ? "Checking..." : "Check API version"}
                </Text>
              </Pressable>
              {renderVersion(versionState)}
            </View>
          ) : (
            <Text style={styles.detailText}>Hidden during daily use.</Text>
          )}
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
    case "initialized":
      return `Пользователь создан: ${state.userId}.`;
    case "activating":
      return "Проверяем receipt через backend.";
    case "payment-created":
      return `Платёж ЮKassa создан: ${state.paymentId}. После оплаты подтвердите платёж.`;
    case "exporting":
      return "Готовим экспорт аккаунта.";
    case "exported":
      return "Данные аккаунта экспортированы.";
    case "deleting":
      return "Удаляем аккаунт.";
    case "deleted":
      return "Аккаунт удалён, локальные токены очищены.";
    case "initializing":
      return "Создаём или ищем пользователя по Device ID.";
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

function renderVersion(state: VersionState) {
  switch (state.kind) {
    case "ready":
      return (
        <Text style={styles.detailText}>
          API {state.version.api_version} · config {state.version.config_format} v{state.version.config_version} · min app{" "}
          {state.version.min_client_version}
        </Text>
      );
    case "loading":
      return <Text style={styles.detailText}>Проверяем совместимость backend.</Text>;
    case "error":
      return <Text style={styles.detailText}>{state.message}</Text>;
    case "idle":
    default:
      return <Text style={styles.detailText}>Проверка версии нужна перед rollout и QA.</Text>;
  }
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#F6F7F9"
  },
  screen: {
    backgroundColor: "#F6F7F9",
    flexGrow: 1,
    gap: 16,
    paddingBottom: 28,
    paddingHorizontal: 20,
    paddingTop: 28
  },
  header: {
    gap: 6,
    paddingHorizontal: 2
  },
  title: {
    color: "#151A22",
    fontSize: 34,
    fontWeight: "800"
  },
  subtitle: {
    color: "#5E6673",
    fontSize: 16,
    lineHeight: 22,
    maxWidth: 320
  },
  connectionPanel: {
    backgroundColor: "#FFFFFF",
    borderColor: "#E1E6EC",
    borderRadius: 18,
    borderWidth: 1,
    gap: 18,
    padding: 20
  },
  statusRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: 12
  },
  statusDot: {
    backgroundColor: "#B7C0CC",
    borderRadius: 7,
    height: 14,
    width: 14
  },
  statusDotActive: {
    backgroundColor: "#1F7A5C"
  },
  statusDotBusy: {
    backgroundColor: "#D78B22"
  },
  statusCopy: {
    flex: 1,
    gap: 2
  },
  statusLabel: {
    color: "#6A7381",
    fontSize: 13,
    fontWeight: "700",
    textTransform: "uppercase"
  },
  statusValue: {
    color: "#151A22",
    fontSize: 26,
    fontWeight: "800"
  },
  powerButton: {
    alignItems: "center",
    backgroundColor: "#151A22",
    borderRadius: 16,
    minHeight: 62,
    justifyContent: "center"
  },
  powerButtonActive: {
    backgroundColor: "#1F7A5C"
  },
  powerButtonDisabled: {
    opacity: 0.68
  },
  powerButtonText: {
    color: "#FFFFFF",
    fontSize: 19,
    fontWeight: "800"
  },
  pressed: {
    opacity: 0.84
  },
  connectionHint: {
    color: "#384150",
    fontSize: 15,
    lineHeight: 21
  },
  configState: {
    color: "#667080",
    fontSize: 13,
    lineHeight: 19
  },
  routePanel: {
    backgroundColor: "#FFFFFF",
    borderColor: "#E1E6EC",
    borderRadius: 18,
    borderWidth: 1,
    gap: 12,
    padding: 16
  },
  routeGrid: {
    flexDirection: "row",
    gap: 10
  },
  routeItem: {
    backgroundColor: "#F6F7F9",
    borderColor: "#E5EAF0",
    borderRadius: 12,
    borderWidth: 1,
    flex: 1,
    gap: 5,
    minHeight: 78,
    padding: 12
  },
  routeLabel: {
    color: "#1F7A5C",
    fontSize: 13,
    fontWeight: "800",
    textTransform: "uppercase"
  },
  routeValue: {
    color: "#151A22",
    fontSize: 14,
    fontWeight: "700",
    lineHeight: 19
  },
  panel: {
    backgroundColor: "#FFFFFF",
    borderColor: "#E1E6EC",
    borderRadius: 18,
    borderWidth: 1,
    gap: 12,
    padding: 16
  },
  panelHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: 12,
    justifyContent: "space-between"
  },
  panelToggle: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 34
  },
  panelTitle: {
    color: "#151A22",
    fontSize: 18,
    fontWeight: "800"
  },
  input: {
    backgroundColor: "#F8FAFC",
    borderColor: "#D9E0E8",
    borderRadius: 12,
    borderWidth: 1,
    color: "#151A22",
    fontSize: 16,
    minHeight: 48,
    paddingHorizontal: 14
  },
  linkRow: {
    flexDirection: "row",
    gap: 10
  },
  linkButton: {
    alignItems: "center",
    borderColor: "#B8C5D3",
    borderRadius: 12,
    borderWidth: 1,
    flex: 1,
    minHeight: 44,
    justifyContent: "center"
  },
  linkButtonText: {
    color: "#384150",
    fontSize: 15,
    fontWeight: "800"
  },
  buttonGrid: {
    flexDirection: "row",
    gap: 10
  },
  gridButton: {
    flex: 1
  },
  textButton: {
    alignItems: "center",
    minHeight: 38,
    justifyContent: "center"
  },
  textButtonText: {
    color: "#1F5F96",
    fontSize: 15,
    fontWeight: "800"
  },
  secondaryButton: {
    alignItems: "center",
    backgroundColor: "#1F7A5C",
    borderRadius: 12,
    minHeight: 48,
    justifyContent: "center"
  },
  disabledButton: {
    opacity: 0.55
  },
  secondaryButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "800"
  },
  outlineButton: {
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderColor: "#B8C5D3",
    borderRadius: 12,
    borderWidth: 1,
    minHeight: 48,
    justifyContent: "center"
  },
  outlineButtonText: {
    color: "#151A22",
    fontSize: 15,
    fontWeight: "800"
  },
  dangerButton: {
    alignItems: "center",
    backgroundColor: "#B3261E",
    borderRadius: 12,
    minHeight: 48,
    justifyContent: "center"
  },
  dangerButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "800"
  },
  accountTools: {
    gap: 12
  },
  exportText: {
    backgroundColor: "#F8FAFC",
    borderColor: "#D9E0E8",
    borderRadius: 12,
    borderWidth: 1,
    color: "#151A22",
    fontFamily: "monospace",
    fontSize: 12,
    lineHeight: 18,
    padding: 12
  },
  nodeList: {
    gap: 10
  },
  nodeRow: {
    borderColor: "#E1E6EC",
    borderRadius: 12,
    borderWidth: 1,
    gap: 4,
    padding: 12
  },
  nodeTitle: {
    color: "#151A22",
    fontSize: 15,
    fontWeight: "800"
  },
  detailText: {
    color: "#667080",
    fontSize: 14,
    lineHeight: 20
  }
});
