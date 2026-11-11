/** Utilitas GPS peramban. Butuh HTTPS atau localhost dan izin lokasi dari pengguna. */
export interface GpsFix {
  lat: number;
  lng: number;
  accuracy: number; // meter (radius 68%)
  simulated?: boolean;
}

const MSG: Record<number, string> = {
  1: "Izin lokasi ditolak. Izinkan lokasi di peramban, atau tunjuk kebun di peta.",
  2: "Posisi tidak tersedia. Coba di tempat lebih terbuka.",
  3: "GPS terlalu lama merespons.",
};

export function watchFix(onFix: (f: GpsFix) => void, onError: (msg: string) => void): () => void {
  if (!("geolocation" in navigator)) {
    onError("Perangkat ini tidak punya GPS atau peramban tidak mengizinkan lokasi.");
    return () => undefined;
  }
  const id = navigator.geolocation.watchPosition(
    (p) => onFix({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }),
    (e) => onError(MSG[e.code] ?? e.message),
    { enableHighAccuracy: true, maximumAge: 0, timeout: 25000 },
  );
  return () => navigator.geolocation.clearWatch(id);
}

export function getFix(timeoutMs = 15000): Promise<GpsFix> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) return reject(new Error("GPS tidak tersedia di perangkat ini."));
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }),
      (e) => reject(new Error(MSG[e.code] ?? e.message)),
      { enableHighAccuracy: true, maximumAge: 0, timeout: timeoutMs },
    );
  });
}

/** Rata-rata berbobot (1/akurasi²) dari bacaan yang akurasinya tidak lebih dari 1,5x bacaan terbaik. */
export function averageFix(samples: GpsFix[]): GpsFix | null {
  if (!samples.length) return null;
  const best = Math.min(...samples.map((s) => s.accuracy));
  const good = samples.filter((s) => s.accuracy <= best * 1.5);
  let w = 0;
  let lat = 0;
  let lng = 0;
  for (const s of good) {
    const k = 1 / Math.max(s.accuracy, 1) ** 2;
    w += k;
    lat += s.lat * k;
    lng += s.lng * k;
  }
  // akurasi rata-rata membaik kira-kira sebanding akar jumlah bacaan (tidak lebih baik dari 2 m)
  return { lat: lat / w, lng: lng / w, accuracy: Math.max(2, best / Math.sqrt(good.length)) };
}

/** Jarak meter antara dua titik (haversine). */
export function distanceM(a: [number, number], b: [number, number]): number {
  const R = 6371008.8;
  const toR = (d: number) => (d * Math.PI) / 180;
  const dLat = toR(b[0] - a[0]);
  const dLng = toR(b[1] - a[1]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toR(a[0])) * Math.cos(toR(b[0])) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
