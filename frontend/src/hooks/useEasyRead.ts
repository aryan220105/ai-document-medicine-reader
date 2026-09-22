import { useEffect, useState } from "react";

const KEY = "formsathi.easyRead";

export function useEasyRead() {
  const [easyRead, setEasyRead] = useState(() => localStorage.getItem(KEY) === "true");

  useEffect(() => {
    localStorage.setItem(KEY, String(easyRead));
    document.documentElement.classList.toggle("easy-read", easyRead);
  }, [easyRead]);

  return { easyRead, setEasyRead };
}
