import type { Ctx } from '../app';

export interface ModuleHosts {
  left: HTMLElement;
  leftFoot: HTMLElement;
  stage: HTMLElement;
  toolbar: HTMLElement;
  right: HTMLElement;
  rightFoot: HTMLElement;
}

export interface LitModule {
  id: string;
  label: string;
  icon: string;
  key: string;
  order: number;
  mount(ctx: Ctx, hosts: ModuleHosts): void;
  activate?(): void;
  deactivate?(): void;
  onKey?(e: KeyboardEvent, combo: string): boolean;
}

const MODULES: LitModule[] = [];

export function registerModule(m: LitModule): void {
  if (MODULES.some((x) => x.id === m.id)) throw new Error(`module registered twice: ${m.id}`);
  MODULES.push(m);
  MODULES.sort((a, b) => a.order - b.order);
}

export function modules(): LitModule[] {
  return MODULES;
}

export function moduleById(id: string): LitModule | undefined {
  return MODULES.find((m) => m.id === id);
}
