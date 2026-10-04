import type { HistoryEntry } from "./research.ts";

const DATABASE = "idx-insight-history";
const STORE = "entries";

function openHistory(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB is unavailable"));
      return;
    }
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) {
        request.result.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Could not open research history"));
  });
}

export async function listHistory(): Promise<HistoryEntry[]> {
  const db = await openHistory();
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction(STORE, "readonly").objectStore(STORE).getAll();
      request.onsuccess = () => resolve((request.result as HistoryEntry[])
        .filter(entry => !!entry && typeof entry.id === "string" && typeof entry.query === "string" && !!entry.response)
        .sort((a, b) => b.askedAt.localeCompare(a.askedAt)));
      request.onerror = () => reject(request.error ?? new Error("Could not read research history"));
    });
  } finally {
    db.close();
  }
}

export async function saveHistory(entry: HistoryEntry): Promise<void> {
  const db = await openHistory();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE, "readwrite");
      transaction.objectStore(STORE).put(entry);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error ?? new Error("Could not save research history"));
      transaction.onabort = () => reject(transaction.error ?? new Error("Could not save research history"));
    });
  } finally {
    db.close();
  }
}

export async function clearHistory(): Promise<void> {
  const db = await openHistory();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE, "readwrite");
      transaction.objectStore(STORE).clear();
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error ?? new Error("Could not clear research history"));
      transaction.onabort = () => reject(transaction.error ?? new Error("Could not clear research history"));
    });
  } finally {
    db.close();
  }
}
