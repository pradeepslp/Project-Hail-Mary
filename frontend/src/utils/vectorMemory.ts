import type { CMIMemoryEntry } from "../types/cmi";

const DB_NAME = "HAIL_MARY_CMI_MEMORY";
const DB_VERSION = 1;
const STORE_NAME = "memories";

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event: any) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };

    request.onsuccess = (event: any) => resolve(event.target.result);
    request.onerror = (event: any) => reject(event.target.error);
  });
}

// Stopwords list for local TF-IDF matcher
const STOPWORDS = new Set([
  "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "as", "at",
  "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can", "did", "do",
  "does", "doing", "don", "down", "during", "each", "few", "for", "from", "further", "had", "has", "have",
  "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into",
  "is", "it", "its", "itself", "just", "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off",
  "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
  "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
  "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
  "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why", "with", "you", "your",
  "yours", "yourself", "yourselves"
]);

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .split(/\s+/)
    .filter(word => word.length > 1 && !STOPWORDS.has(word));
}

function calculateTFIDFSimilarity(queryTokens: string[], docTokens: string[], allDocsTokens: string[][]): number {
  if (queryTokens.length === 0 || docTokens.length === 0) return 0;

  const vocab = new Set([...queryTokens, ...docTokens]);
  const docCount = allDocsTokens.length;

  const df: Record<string, number> = {};
  for (const term of vocab) {
    df[term] = 0;
    for (const tokens of allDocsTokens) {
      if (tokens.includes(term)) df[term]++;
    }
  }

  const idf: Record<string, number> = {};
  for (const term of vocab) {
    idf[term] = Math.log((docCount + 1) / (df[term] + 1)) + 1;
  }

  const queryVec: Record<string, number> = {};
  const docVec: Record<string, number> = {};

  for (const term of vocab) {
    const qCount = queryTokens.filter(t => t === term).length;
    queryVec[term] = (qCount / queryTokens.length) * idf[term];

    const dCount = docTokens.filter(t => t === term).length;
    docVec[term] = (dCount / docTokens.length) * idf[term];
  }

  let dotProduct = 0;
  let normQuery = 0;
  let normDoc = 0;

  for (const term of vocab) {
    dotProduct += queryVec[term] * docVec[term];
    normQuery += queryVec[term] * queryVec[term];
    normDoc += docVec[term] * docVec[term];
  }

  if (normQuery === 0 || normDoc === 0) return 0;
  return dotProduct / (Math.sqrt(normQuery) * Math.sqrt(normDoc));
}

async function fetchOpenAIEmbedding(text: string, apiKey: string): Promise<number[]> {
  const response = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`
    },
    body: JSON.stringify({
      input: text,
      model: "text-embedding-3-small"
    })
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`OpenAI Embedding API error: ${errText}`);
  }

  const data = await response.json();
  return data.data[0].embedding;
}

function calculateVectorSimilarity(vecA: number[], vecB: number[]): number {
  if (vecA.length !== vecB.length) return 0;

  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < vecA.length; i++) {
    dotProduct += vecA[i] * vecB[i];
    normA += vecA[i] * vecA[i];
    normB += vecB[i] * vecB[i];
  }

  if (normA === 0 || normB === 0) return 0;
  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

export const vectorMemory = {
  async getAllEntries(): Promise<CMIMemoryEntry[]> {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readonly");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  },

  async saveEntry(params: {
    text: string;
    type: CMIMemoryEntry["type"];
    metadata?: Record<string, any>;
    apiKey?: string;
  }): Promise<CMIMemoryEntry> {
    const id = `${params.type}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    let vector: number[] | undefined;

    if (params.apiKey && params.apiKey.startsWith("sk-")) {
      try {
        vector = await fetchOpenAIEmbedding(params.text, params.apiKey);
      } catch (err) {
        console.warn("[CMI VectorMemory] Cloud embedding failed, defaulting to local text indices:", err);
      }
    }

    const entry: CMIMemoryEntry = {
      id,
      text: params.text,
      type: params.type,
      timestamp: new Date().toISOString(),
      metadata: params.metadata,
      vector
    };

    const db = await openDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.put(entry);

      request.onsuccess = () => resolve(entry);
      request.onerror = () => reject(request.error);
    });
  },

  async searchEntries(params: {
    query: string;
    apiKey?: string;
    limit?: number;
  }): Promise<{ entry: CMIMemoryEntry; score: number }[]> {
    const limit = params.limit ?? 5;
    const entries = await this.getAllEntries();

    if (entries.length === 0) return [];

    let queryVector: number[] | undefined;
    if (params.apiKey && params.apiKey.startsWith("sk-")) {
      try {
        queryVector = await fetchOpenAIEmbedding(params.query, params.apiKey);
      } catch (err) {
        console.warn("[CMI VectorMemory] Cloud query embedding failed, using TF-IDF matching:", err);
      }
    }

    const scored: { entry: CMIMemoryEntry; score: number }[] = [];

    if (queryVector) {
      // Direct vector cosine similarity match
      for (const entry of entries) {
        if (entry.vector) {
          const score = calculateVectorSimilarity(queryVector, entry.vector);
          scored.push({ entry, score });
        } else {
          // TF-IDF fallback for entries created offline without vectors
          const score = calculateTFIDFSimilarity(
            tokenize(params.query),
            tokenize(entry.text),
            entries.map(e => tokenize(e.text))
          );
          scored.push({ entry, score: score * 0.9 }); // slightly discount local scores to differentiate
        }
      }
    } else {
      // Local keyword TF-IDF similarity match
      const queryTokens = tokenize(params.query);
      const docsTokens = entries.map(e => tokenize(e.text));

      for (let i = 0; i < entries.length; i++) {
        const entry = entries[i];
        const score = calculateTFIDFSimilarity(queryTokens, docsTokens[i], docsTokens);
        scored.push({ entry, score });
      }
    }

    // Sort by descending score
    return scored
      .filter(item => item.score > 0.05) // filter out noise
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);
  },

  async clear(): Promise<void> {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.clear();

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }
};
