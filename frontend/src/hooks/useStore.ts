import { useState, useEffect } from "react";
import { Telemetry, Mission, ActiveEvent } from "./useWebSocket";

type Listener<T> = (value: T) => void;

export class Store<T> {
  private state: T;
  private listeners = new Set<Listener<T>>();

  constructor(initialState: T) {
    this.state = initialState;
  }

  getState(): T {
    return this.state;
  }

  setState(newState: T | ((prev: T) => T)) {
    const nextState = typeof newState === "function" 
      ? (newState as Function)(this.state) 
      : newState;
    
    if (nextState !== this.state) {
      this.state = nextState;
      this.listeners.forEach((listener) => listener(nextState));
    }
  }

  subscribe(listener: Listener<T>) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }
}

export const telemetryStore = new Store<Telemetry | null>(null);
export const missionStore = new Store<Mission | null>(null);
export const activeEventsStore = new Store<ActiveEvent[]>([]);
export const eventsStore = new Store<string[]>([]);
export const statusStore = new Store<"connecting" | "connected" | "disconnected">("disconnected");
export const missionSuccessStore = new Store<any | null>(null);
export const missionFailureStore = new Store<any | null>(null);

export function useStore<T>(store: Store<T>): T;
export function useStore<T, SelectorOutput>(
  store: Store<T>,
  selector: (state: T) => SelectorOutput
): SelectorOutput;
export function useStore<T, SelectorOutput>(
  store: Store<T>,
  selector?: (state: T) => SelectorOutput
) {
  const [slice, setSlice] = useState(() => 
    selector ? selector(store.getState()) : store.getState()
  );

  useEffect(() => {
    return store.subscribe((nextState) => {
      const nextSlice = selector ? selector(nextState) : nextState;
      setSlice((prevSlice) => {
        if (nextSlice === prevSlice) return prevSlice;
        // Simple shallow equality check for objects/arrays to prevent unnecessary re-renders
        if (typeof nextSlice === "object" && typeof prevSlice === "object" && nextSlice !== null && prevSlice !== null) {
          const keysA = Object.keys(nextSlice as object);
          const keysB = Object.keys(prevSlice as object);
          if (keysA.length === keysB.length && keysA.every(key => (nextSlice as any)[key] === (prevSlice as any)[key])) {
            return prevSlice;
          }
        }
        return nextSlice;
      });
    });
  }, [store, selector]);

  return slice;
}

export const resetAllStores = () => {
  telemetryStore.setState(null);
  missionStore.setState(null);
  activeEventsStore.setState([]);
  eventsStore.setState([]);
  missionSuccessStore.setState(null);
  missionFailureStore.setState(null);
};
