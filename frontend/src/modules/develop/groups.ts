export const GROUPS: Array<[string, string]> = [
  ['whiteBalance', 'White Balance'], ['basicTone', 'Basic Tone'], ['presence', 'Presence'], ['toneCurve', 'Tone Curve'], ['colorMixer', 'Color Mixer'],
  ['pointColor', 'Point Color'], ['bwMix', 'B&W Mix'], ['treatment', 'Treatment'], ['colorGrading', 'Color Grading'], ['detail', 'Detail'],
  ['lensCorrections', 'Lens Corrections'], ['transform', 'Transform'], ['effects', 'Effects'], ['calibration', 'Calibration'], ['profile', 'Profile'],
  ['lensBlur', 'Lens Blur'], ['hdr', 'HDR'], ['reflections', 'Reflections'], ['masks', 'Masking'], ['spots', 'Healing'], ['redEye', 'Red Eye'], ['crop', 'Crop'],
];

export const DEFAULT_OFF = new Set(['masks', 'spots', 'redEye', 'crop']);
