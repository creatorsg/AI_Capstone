import { create } from 'zustand';
import { childrenAPI } from '../services/api';
import { Child } from '../types';

interface ChildState {
  children: Child[];
  selectedChild: Child | null;
  fetchChildren: () => Promise<void>;
  addChild: (data: Omit<Child, 'id'>) => Promise<void>;
  updateChild: (id: number, data: Partial<Child>) => Promise<void>;
  deleteChild: (id: number) => Promise<void>;
  selectChild: (child: Child) => void;
}

export const useChildStore = create<ChildState>((set, get) => ({
  children: [],
  selectedChild: null,

  fetchChildren: async () => {
    const { data } = await childrenAPI.list();
    set({ children: data });
    const { selectedChild, children } = get();
    if (!selectedChild && data.length > 0) {
      set({ selectedChild: data[0] });
    } else if (selectedChild) {
      const updated = data.find((c: Child) => c.id === selectedChild.id);
      if (updated) set({ selectedChild: updated });
    }
  },

  addChild: async (data) => {
    await childrenAPI.create(data);
    await get().fetchChildren();
  },

  updateChild: async (id, data) => {
    await childrenAPI.update(id, data);
    await get().fetchChildren();
  },

  deleteChild: async (id) => {
    await childrenAPI.delete(id);
    const { selectedChild } = get();
    if (selectedChild?.id === id) set({ selectedChild: null });
    await get().fetchChildren();
  },

  selectChild: (child) => set({ selectedChild: child }),
}));
