export interface CollectionRow { id: number; name: string; kind: string }

class CatalogState {
  tree = { catalog: { name: 'formlit demo', path: '', total: 0 }, folders: [], collections: [] as CollectionRow[], keywords: [], labelNames: {} as Record<string, string> };
  listen(): () => void { return () => undefined; }
  labelName(label: string): string { return label.charAt(0).toUpperCase() + label.slice(1); }
}

export const catalog = new CatalogState();
