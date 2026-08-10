import { Directory, File, Paths } from 'expo-file-system';

/**
 * Picked photos are copied into the app's document directory so they survive
 * app restarts (picker uris point into a temporary cache). We store the
 * resulting `file://` uri in the entry.
 */

function photosDir(): Directory {
  return new Directory(Paths.document, 'photos');
}

export async function persistPhoto(sourceUri: string, entryId: string): Promise<string> {
  try {
    const dir = photosDir();
    if (!dir.exists) dir.create({ intermediates: true });
    const cleanPath = sourceUri.split('?')[0] ?? '';
    const extMatch = /\.(jpe?g|png|gif|webp|heic|heif)$/i.exec(cleanPath);
    const ext = extMatch ? extMatch[1].toLowerCase() : 'jpg';
    // Unique name per save so an edited entry never collides with a cached image.
    const dest = new File(dir, `${entryId}-${Date.now()}.${ext}`);
    if (dest.exists) dest.delete();
    await new File(sourceUri).copy(dest);
    return dest.uri;
  } catch (e) {
    console.warn('persistPhoto failed — falling back to the original uri', e);
    return sourceUri;
  }
}

export function deletePhotoFile(uri?: string): void {
  if (!uri) return;
  try {
    const f = new File(uri);
    if (f.exists) f.delete();
  } catch (e) {
    console.warn('deletePhotoFile failed', e);
  }
}

/** Web (see photos.web.ts) stores photos in IndexedDB behind idb:// uris — on
 * native the file uri is already directly renderable. */
export const IDB_SCHEME = 'idb://';

export async function resolvePhotoUri(uri: string): Promise<string> {
  return uri;
}
