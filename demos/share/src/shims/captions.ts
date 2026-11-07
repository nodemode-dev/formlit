import type { Ctx } from '../../../../frontend/src/app';

export const fieldLabel = (f: string): string => f;

export function registerCaptions(_ctx: Ctx): void { return; }

export async function warnMissing(_ctx: Ctx, _ids: number[]): Promise<boolean> { return true; }
