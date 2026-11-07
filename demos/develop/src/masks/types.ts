import type { Dev } from '../../../../demo/src/engine/settings';

export type Vec = [number, number];
export type Op = 'add' | 'subtract' | 'intersect';
export interface Shape { kind: string; [key: string]: unknown }
export interface Component { shape: Shape; op: Op; invert?: boolean }
export interface Mask { id: number; name: string; visible?: boolean; components: Component[]; adjust: Record<string, number>; invert?: boolean }

export const BITMAP_KINDS = new Set(['subject', 'sky', 'background']);

export function masksOf(dev: Dev): Mask[] {
  return Array.isArray(dev.masks) ? (dev.masks as Mask[]) : [];
}

export function liveMasks(dev: Dev): Mask[] {
  return masksOf(dev).filter((m) => m.visible !== false && Array.isArray(m.components) && m.components.length > 0);
}

export const hasAdjust = (m: Mask): boolean => Object.entries(m.adjust ?? {}).some(([k, v]) => k !== 'amount' && v !== 0);
