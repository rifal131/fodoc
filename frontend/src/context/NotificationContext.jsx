import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { NewPhotoToast } from "@/components/NewPhotoToast";

const POLL_MS = 20000;
const NotifCtx = createContext({ items: [], unread: 0, reload: () => {} });

// Polls notifications for mahasiswa and pops a toast for each newly-arrived one
export function NotificationProvider({ children }) {
  const { user } = useAuth();
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const seen = useRef(null);
  const active = user && user.role === "mahasiswa";

  const reload = useCallback(async () => {
    if (typeof document !== "undefined" && document.hidden) return;
    try {
      const { data } = await api.get("/me/notifications");
      setItems(data);
      if (seen.current === null) {
        seen.current = new Set(data.map((n) => n.id));
        return;
      }
      data.filter((n) => !n.read && !seen.current.has(n.id)).reverse().forEach((n) => {
        seen.current.add(n.id);
        toast.custom((t) => <NewPhotoToast n={n} onOpen={() => { toast.dismiss(t); nav("/gallery"); }} onClose={() => toast.dismiss(t)} />,
          { duration: 10000, id: `notif-${n.id}` });
      });
    } catch {}
  }, [nav]);

  useEffect(() => {
    seen.current = null;
    setItems([]);
    if (!active) return;
    reload();
    const t = setInterval(reload, POLL_MS);
    return () => clearInterval(t);
  }, [active, reload]);

  const unread = items.filter((n) => !n.read).length;
  return <NotifCtx.Provider value={{ items, unread, reload }}>{children}</NotifCtx.Provider>;
}

export const useNotifications = () => useContext(NotifCtx);
