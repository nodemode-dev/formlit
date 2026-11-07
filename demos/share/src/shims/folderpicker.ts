export const MUSIC_FOLDER = 'Demo Music';

export function pickFolder(_title: string, _lead: string, _start = '', _okLabel = 'Choose'): Promise<string | null> {
  return Promise.resolve(MUSIC_FOLDER);
}

export function folderOf(path: string): string {
  const i = path.lastIndexOf('/');
  return i > 0 ? path.slice(0, i) : MUSIC_FOLDER;
}
