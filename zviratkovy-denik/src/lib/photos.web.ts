/**
 * Web (PWA) photo storage: picked photos are downscaled on a canvas and kept
 * in IndexedDB as JPEG data URIs. Entries then reference them via `idb://key`.
 * (localStorage is far too small for photos; IndexedDB survives restarts and
 * is retained for home-screen web apps.)
 */

export const IDB_SCHEME = 'idb://';

const DB_NAME = 'zuzanky-denik-photos';
const STORE = 'photos';
const MAX_DIMENSION = 1400;
const JPEG_QUALITY = 0.82;

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withStore<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const req = fn(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(req.result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

async function downscaleToDataUri(sourceUri: string): Promise<string> {
  const img = new Image();
  img.src = sourceUri;
  await img.decode();
  const scale = Math.min(1, MAX_DIMENSION / Math.max(img.naturalWidth, img.naturalHeight));
  const w = Math.max(1, Math.round(img.naturalWidth * scale));
  const h = Math.max(1, Math.round(img.naturalHeight * scale));
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('canvas 2d context unavailable');
  ctx.drawImage(img, 0, 0, w, h);
  return canvas.toDataURL('image/jpeg', JPEG_QUALITY);
}

export async function persistPhoto(sourceUri: string, entryId: string): Promise<string> {
  try {
    const dataUri = await downscaleToDataUri(sourceUri);
    const key = `${entryId}-${Date.now()}`;
    await withStore('readwrite', (s) => s.put(dataUri, key));
    return IDB_SCHEME + key;
  } catch (e) {
    console.warn('persistPhoto (web) failed — falling back to the original uri', e);
    return sourceUri;
  }
}

export function deletePhotoFile(uri?: string): void {
  if (!uri || !uri.startsWith(IDB_SCHEME)) return;
  const key = uri.slice(IDB_SCHEME.length);
  withStore('readwrite', (s) => s.delete(key)).catch((e) => console.warn('deletePhotoFile (web) failed', e));
}

/** idb:// → stored data uri; anything else passes through. */
export async function resolvePhotoUri(uri: string): Promise<string> {
  if (!uri.startsWith(IDB_SCHEME)) return uri;
  try {
    const stored = await withStore<string | undefined>('readonly', (s) => s.get(uri.slice(IDB_SCHEME.length)));
    return stored ?? uri;
  } catch (e) {
    console.warn('resolvePhotoUri (web) failed', e);
    return uri;
  }
}
