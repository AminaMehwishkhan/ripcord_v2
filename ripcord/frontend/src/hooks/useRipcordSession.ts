import { useCallback, useEffect, useRef, useState } from "react";
import type { CompareState, SessionState } from "../types";

type ServerMessage =
  | { type: "state"; state: SessionState }
  | ({ type: "compare" } & CompareState)
  | { type: "error"; message: string }
  | { type: "system"; message: string };

const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/session`;
const MAX_BACKOFF_MS = 10000;

export function useRipcordSession() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalClose = useRef(false);
  const connectRef = useRef<() => void>(() => {});

  const [connected, setConnected] = useState(false);
  const [wsReconnecting, setWsReconnecting] = useState(false);
  const [state, setState] = useState<SessionState | null>(null);
  const [compare, setCompare] = useState<CompareState | null>(null);
  const [systemMessage, setSystemMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= 1) return;
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setConnected(true);
      setWsReconnecting(false);
      reconnectAttempt.current = 0;
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      if (intentionalClose.current) return;
      // Browser <-> backend link dropped (not the AssemblyAI link, which the
      // backend itself retries). Reconnect with capped exponential backoff
      // rather than leaving the user staring at a dead dashboard.
      setWsReconnecting(true);
      const delay = Math.min(500 * 2 ** reconnectAttempt.current, MAX_BACKOFF_MS);
      reconnectAttempt.current += 1;
      reconnectTimer.current = setTimeout(() => connectRef.current(), delay);
    };

    ws.onerror = () => {
      // onclose fires right after in browsers; let that path own reconnect.
    };

    ws.onmessage = (evt) => {
      try {
        const msg: ServerMessage = JSON.parse(evt.data);
        if (msg.type === "state") {
          setState(msg.state);
          setErrorMessage(null);
        } else if (msg.type === "compare") {
          setCompare({ truth: msg.truth, scenario_id: msg.scenario_id, a: msg.a, b: msg.b });
          setErrorMessage(null);
        } else if (msg.type === "error") {
          setErrorMessage(msg.message);
        } else if (msg.type === "system") {
          setSystemMessage(msg.message);
        }
      } catch {
        // ignore malformed frames
      }
    };
    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    intentionalClose.current = false;
    connect();
    return () => {
      intentionalClose.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }, []);

  const sendAudio = useCallback((chunk: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(chunk);
    }
  }, []);

  return {
    connected,
    wsReconnecting,
    state,
    compare,
    systemMessage,
    errorMessage,
    send,
    sendAudio,
    startSession: (ripcordEnabled: boolean, mockMode: boolean) =>
      send({ action: "start_session", ripcord_enabled: ripcordEnabled, mock_mode: mockMode }),
    toggleRipcord: (enabled: boolean) => send({ action: "toggle_ripcord", enabled }),
    runMockScenario: (scenarioId: number, ripcordEnabled: boolean) =>
      send({ action: "run_mock_scenario", scenario_id: scenarioId, ripcord_enabled: ripcordEnabled }),
    startRealStream: (ripcordEnabled: boolean) =>
      send({ action: "start_real_stream", ripcord_enabled: ripcordEnabled }),
    userResponse: (text: string) => send({ action: "user_response", text }),
    recordedReply: (kind: "yes" | "no") => send({ action: "recorded_reply", kind }),
    runCompare: (scenarioId: number) => send({ action: "run_compare", scenario_id: scenarioId }),
    reset: () => send({ action: "reset" }),
    stop: () => send({ action: "stop" }),
  };
}
