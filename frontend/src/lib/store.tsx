import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Meta } from "./types";

function readLocal<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
function writeLocal(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable */
  }
}

interface AppState {
  meta: Meta | undefined;
  profileId: number | null;
  setProfileId: (id: number) => void;
  compare: number[];
  toggleCompare: (id: number) => void;
  clearCompare: () => void;
}

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const metaQ = useQuery({
    queryKey: ["meta"],
    queryFn: api.meta,
    refetchInterval: (q) => (q.state.data && !q.state.data.ready ? 2000 : false),
  });
  const [profileId, setProfileIdState] = useState<number | null>(() => readLocal("az.profile", null));
  const [compare, setCompare] = useState<number[]>(() => readLocal("az.compare", []));

  useEffect(() => {
    if (metaQ.data && metaQ.data.profiles.length) {
      const valid = metaQ.data.profiles.some((p) => p.id === profileId);
      if (!valid) setProfileIdState(null);
    }
  }, [metaQ.data, profileId]);

  const setProfileId = useCallback((id: number) => {
    setProfileIdState(id);
    writeLocal("az.profile", id);
  }, []);
  const toggleCompare = useCallback((id: number) => {
    setCompare((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id].slice(-4);
      writeLocal("az.compare", next);
      return next;
    });
  }, []);
  const clearCompare = useCallback(() => {
    setCompare([]);
    writeLocal("az.compare", []);
  }, []);

  const value = useMemo(
    () => ({ meta: metaQ.data, profileId, setProfileId, compare, toggleCompare, clearCompare }),
    [metaQ.data, profileId, setProfileId, compare, toggleCompare, clearCompare],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside provider");
  return v;
}

export function useProfile() {
  const { meta, profileId } = useApp();
  return meta?.profiles.find((p) => p.id === profileId) ?? null;
}

export { readLocal, writeLocal };
