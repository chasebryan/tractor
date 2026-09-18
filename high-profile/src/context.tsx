import { createContext, useContext } from "react";
export const Context = createContext<{
  inspect: (id: string, version?: number) => void;
  notify: (message: string) => void;
}>({ inspect: () => {}, notify: () => {} });
export const useActions = () => useContext(Context);
