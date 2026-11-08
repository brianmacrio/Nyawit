import { lazy, Suspense, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { BookOpenText, Factory, Home, Map as MapIcon, Scale } from "lucide-react";
import { api } from "./lib/api";
import { Emblem, Spinner } from "./components/ui";
import Beranda from "./pages/Beranda";

// halaman peta dimuat terpisah (Leaflet) agar halaman lain lebih ringan
const PetaKebun = lazy(() => import("./pages/PetaKebun"));
const Pengepul = lazy(() => import("./pages/Pengepul"));
const Pabrik = lazy(() => import("./pages/Pabrik"));
const Transparansi = lazy(() => import("./pages/Transparansi"));

const NAV = [
  { to: "/", label: "Beranda", Icon: Home, end: true },
  { to: "/peta", label: "Peta kebun", Icon: MapIcon },
  { to: "/pengepul", label: "Pengepul", Icon: Scale },
  { to: "/pabrik", label: "Pabrik", Icon: Factory },
  { to: "/transparansi", label: "Cara kerja AI", Icon: BookOpenText },
];

export default function App() {
  const [mode, setMode] = useState<string | null>(null);
  useEffect(() => {
    api.meta().then((m) => setMode(m.satellite_mode)).catch(() => setMode(null));
  }, []);

  return (
    <div className="shell">
      <nav className="rail" aria-label="Menu utama">
        <NavLink to="/" className="brand" aria-label="PasporKebun, beranda">
          <Emblem />
        </NavLink>
        {NAV.map(({ to, label, Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav ${isActive ? "active" : ""}`}>
            <Icon size={22} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
        <div className="spacer" />
        {mode && <div className="mode">{mode === "live" ? "Satelit live" : "Mode demo"}</div>}
      </nav>
      <main className="main">
        <Suspense fallback={<div className="page"><Spinner label="Memuat…" /></div>}>
          <Routes>
            <Route path="/" element={<Beranda />} />
            <Route path="/peta" element={<PetaKebun />} />
            <Route path="/pengepul" element={<Pengepul />} />
            <Route path="/pabrik" element={<Pabrik />} />
            <Route path="/transparansi" element={<Transparansi />} />
            <Route path="*" element={<div className="page"><h1>Halaman tidak ditemukan</h1></div>} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}
