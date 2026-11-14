import { lazy, Suspense, useEffect, useState } from "react";
import { Link, NavLink, Route, Routes } from "react-router-dom";
import { BookOpenText, ClipboardCheck, Factory, Home, LogIn, LogOut, Map as MapIcon, Scale } from "lucide-react";
import { api } from "./lib/api";
import { useAuth } from "./lib/auth";
import { Emblem, Spinner } from "./components/ui";
import { RoleGate } from "./components/RoleGate";
import Beranda from "./pages/Beranda";

// halaman berat (Leaflet, kamera) dimuat terpisah agar halaman lain lebih ringan
const PetaKebun = lazy(() => import("./pages/PetaKebun"));
const Pengepul = lazy(() => import("./pages/Pengepul"));
const Pabrik = lazy(() => import("./pages/Pabrik"));
const Verifikasi = lazy(() => import("./pages/Verifikasi"));
const Transparansi = lazy(() => import("./pages/Transparansi"));
const Masuk = lazy(() => import("./pages/Masuk"));
const CekPaspor = lazy(() => import("./pages/CekPaspor"));
const KartuPaspor = lazy(() => import("./pages/KartuPaspor"));

const NAV = [
  { to: "/", label: "Beranda", Icon: Home, end: true },
  { to: "/peta", label: "Peta kebun", Icon: MapIcon },
  { to: "/pengepul", label: "Pengepul", Icon: Scale },
  { to: "/pabrik", label: "Pabrik", Icon: Factory },
  { to: "/verifikasi", label: "Verifikasi", Icon: ClipboardCheck },
  { to: "/transparansi", label: "Cara kerja AI", Icon: BookOpenText },
];

export default function App() {
  const { user, logout } = useAuth();
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
        {user ? (
          <div className="who-am-i">
            <Link to="/masuk" className="role" title="Ganti peran">{user.role_label}</Link>
            <span className="name" title={user.name}>{user.name}</span>
            <button className="nav-btn" onClick={() => logout()} aria-label="Keluar">
              <LogOut size={18} aria-hidden="true" /> Keluar
            </button>
          </div>
        ) : (
          <NavLink to="/masuk" className={({ isActive }) => `nav ${isActive ? "active" : ""}`}>
            <LogIn size={22} aria-hidden="true" />
            Masuk
          </NavLink>
        )}
      </nav>
      <main className="main">
        <Suspense fallback={<div className="page"><Spinner label="Memuat…" /></div>}>
          <Routes>
            <Route path="/" element={<Beranda />} />
            <Route path="/peta" element={<RoleGate title="Peta kebun"><PetaKebun /></RoleGate>} />
            <Route path="/pengepul" element={<RoleGate title="Timbang & catat" roles={["pengepul"]}><Pengepul /></RoleGate>} />
            <Route path="/pabrik" element={<RoleGate title="Dasbor pabrik" roles={["pabrik", "verifikator"]}><Pabrik /></RoleGate>} />
            <Route
              path="/verifikasi"
              element={<RoleGate title="Verifikasi independen" roles={["verifikator", "koperasi", "pabrik"]}><Verifikasi /></RoleGate>}
            />
            <Route path="/transparansi" element={<Transparansi />} />
            <Route path="/masuk" element={<Masuk />} />
            <Route path="/cek" element={<CekPaspor />} />
            <Route path="/cek/:code" element={<CekPaspor />} />
            <Route path="/kartu/:id" element={<RoleGate title="Kartu paspor"><KartuPaspor /></RoleGate>} />
            <Route path="*" element={<div className="page"><h1>Halaman tidak ditemukan</h1></div>} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}
