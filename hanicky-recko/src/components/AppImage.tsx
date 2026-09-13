import { Image, type ImageProps } from 'expo-image';
import React, { useEffect, useState } from 'react';

import { IDB_SCHEME, resolvePhotoUri } from '@/lib/photos';

/**
 * Image that understands our photo uris on every platform: plain file/data
 * uris render directly, `idb://` uris (web photo storage) resolve first.
 */
export function AppImage({ uri, ...props }: Omit<ImageProps, 'source'> & { uri?: string }) {
  const needsResolve = !!uri && uri.startsWith(IDB_SCHEME);
  const [resolved, setResolved] = useState<string | undefined>(needsResolve ? undefined : uri);

  useEffect(() => {
    let alive = true;
    if (!uri) {
      setResolved(undefined);
      return;
    }
    if (!uri.startsWith(IDB_SCHEME)) {
      setResolved(uri);
      return;
    }
    setResolved(undefined);
    resolvePhotoUri(uri).then((u) => {
      if (alive) setResolved(u);
    });
    return () => {
      alive = false;
    };
  }, [uri]);

  return <Image {...props} source={resolved ? { uri: resolved } : undefined} />;
}
