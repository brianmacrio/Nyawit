import { useEffect, useRef, useState } from "react";
import jsQR from "jsqr";
import { Notice } from "./ui";

/** Pemindai QR dari kamera (laptop/ponsel). Diproses lokal di browser, tidak ada gambar yang dikirim. */
export function QrScanner({ onResult, onClose }: { onResult: (text: string) => void; onClose: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let raf = 0;
    let stopped = false;
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });

    const tick = () => {
      const v = videoRef.current;
      if (stopped || !v || !ctx) return;
      if (v.readyState === v.HAVE_ENOUGH_DATA) {
        // diperkecil ke lebar 480 px: cukup untuk QR, hemat CPU/baterai
        const scale = Math.min(1, 480 / v.videoWidth);
        canvas.width = v.videoWidth * scale;
        canvas.height = v.videoHeight * scale;
        ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
        const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const code = jsQR(img.data, img.width, img.height, { inversionAttempts: "dontInvert" });
        if (code?.data) {
          stopped = true;
          onResult(code.data);
          return;
        }
      }
      raf = requestAnimationFrame(tick);
    };

    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: "environment" }, audio: false })
      .then((s) => {
        stream = s;
        if (videoRef.current) {
          videoRef.current.srcObject = s;
          videoRef.current.play().catch(() => undefined);
        }
        raf = requestAnimationFrame(tick);
      })
      .catch(() => setErr("Kamera tidak bisa dibuka. Izinkan akses kamera di browser, atau ketik kode paspor."));
    if (!navigator.mediaDevices) setErr("Browser ini tidak mendukung kamera. Ketik kode paspor.");

    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [onResult]);

  return (
    <div className="scanner" style={{ display: "grid", gap: 8 }}>
      {err ? <Notice kind="warn">{err}</Notice> : <video ref={videoRef} muted playsInline aria-label="Pratinjau kamera" />}
      <button className="btn btn-quiet" onClick={onClose}>Tutup kamera</button>
    </div>
  );
}
