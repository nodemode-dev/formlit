export interface Place { name: string; lat: number; lon: number; z: number; kind: 'sea' | 'country' | 'city' | 'spot' }

const P = (kind: Place['kind'], z: number, name: string, lat: number, lon: number): Place => ({ name, lat, lon, z, kind });

export const PLACES: Place[] = [
  P('sea', 2, 'Atlantic Ocean', 0, -30), P('sea', 2, 'Pacific Ocean', 0, -150), P('sea', 2, 'Indian Ocean', -20, 80), P('sea', 2, 'Arctic Ocean', 82, 10),
  P('sea', 3, 'Mediterranean Sea', 35, 18), P('sea', 3, 'North Sea', 56, 3), P('sea', 4, 'Black Sea', 43.5, 34),
  P('country', 2, 'Canada', 56, -106), P('country', 2, 'United States', 39, -98), P('country', 2, 'Mexico', 23, -102), P('country', 2, 'Brazil', -10, -52),
  P('country', 2, 'Argentina', -36, -65), P('country', 2, 'Chile', -30, -71), P('country', 3, 'Peru', -9, -75), P('country', 3, 'Colombia', 4, -73),
  P('country', 3, 'Iceland', 65, -18), P('country', 3, 'Norway', 65, 13), P('country', 3, 'Sweden', 62, 15), P('country', 3, 'Finland', 64, 26),
  P('country', 3, 'United Kingdom', 54, -2), P('country', 4, 'Ireland', 53, -8), P('country', 3, 'France', 46.5, 2.5), P('country', 3, 'Spain', 40, -4),
  P('country', 4, 'Portugal', 39.5, -8), P('country', 3, 'Germany', 51, 10), P('country', 3, 'Italy', 42.5, 12.5), P('country', 4, 'Switzerland', 46.8, 8.2),
  P('country', 4, 'Austria', 47.5, 14), P('country', 5, 'Slovenia', 46.1, 14.8), P('country', 3, 'Greece', 39, 22), P('country', 3, 'Turkey', 39, 35),
  P('country', 4, 'Bulgaria', 42.7, 25.5), P('country', 3, 'Poland', 52, 19), P('country', 3, 'Ukraine', 49, 32), P('country', 2, 'Russia', 61, 100),
  P('country', 2, 'Kazakhstan', 48, 67), P('country', 2, 'China', 35, 103), P('country', 3, 'Mongolia', 47, 104), P('country', 2, 'India', 21, 78),
  P('country', 3, 'Japan', 36, 138), P('country', 3, 'Indonesia', -2, 118), P('country', 2, 'Australia', -25, 134), P('country', 3, 'New Zealand', -41, 173),
  P('country', 2, 'South Africa', -29, 24), P('country', 2, 'Egypt', 26, 30), P('country', 3, 'Morocco', 32, -6), P('country', 2, 'Nigeria', 9, 8),
  P('country', 3, 'Kenya', 0, 38), P('country', 3, 'Saudi Arabia', 24, 45), P('country', 3, 'Iran', 32, 53), P('country', 3, 'Pakistan', 30, 69),
  P('country', 4, 'Thailand', 15, 101), P('country', 4, 'Vietnam', 16, 107), P('country', 4, 'South Korea', 36.5, 128), P('country', 4, 'Philippines', 12, 122),
  P('city', 3, 'Reykjavik', 64.15, -21.94), P('city', 3, 'Oslo', 59.9, 10.75), P('city', 4, 'Stockholm', 59.33, 18.07), P('city', 3, 'London', 51.5, -0.12),
  P('city', 3, 'Paris', 48.85, 2.35), P('city', 4, 'Zurich', 47.37, 8.54), P('city', 4, 'Vienna', 48.2, 16.37), P('city', 3, 'Rome', 41.9, 12.5),
  P('city', 4, 'Athens', 37.98, 23.73), P('city', 3, 'Istanbul', 41, 28.98), P('city', 4, 'Sofia', 42.7, 23.3), P('city', 5, 'Ljubljana', 46.05, 14.5),
  P('city', 4, 'Munich', 48.14, 11.58), P('city', 4, 'Milan', 45.46, 9.19), P('city', 5, 'Venice', 45.44, 12.33), P('city', 3, 'Austin', 30.27, -97.74),
  P('city', 3, 'New York', 40.7, -74), P('city', 3, 'Mexico City', 19.43, -99.13), P('city', 3, 'Los Angeles', 34.05, -118.24), P('city', 4, 'Almaty', 43.24, 76.9),
  P('city', 4, 'Queenstown', -45.03, 168.66), P('city', 3, 'Auckland', -36.85, 174.76), P('city', 3, 'Sydney', -33.87, 151.2), P('city', 3, 'Tokyo', 35.68, 139.7),
  P('city', 3, 'Cape Town', -33.92, 18.42), P('city', 3, 'Cairo', 30.04, 31.24), P('city', 4, 'Nairobi', -1.29, 36.82), P('city', 3, 'Lima', -12.05, -77.04),
  P('city', 3, 'Sao Paulo', -23.55, -46.63), P('city', 3, 'Buenos Aires', -34.6, -58.38), P('city', 3, 'Delhi', 28.6, 77.2), P('city', 3, 'Beijing', 39.9, 116.4),
  P('city', 3, 'Singapore', 1.35, 103.8), P('spot', 5, 'Lofoten', 68.2, 14.6), P('spot', 6, 'Hallstatt', 47.56, 13.65), P('spot', 6, 'Lake Bled', 46.37, 14.1),
  P('spot', 5, 'Milford Sound', -44.67, 167.93), P('spot', 5, 'Santorini', 36.39, 25.46), P('spot', 5, 'Snaefellsnes', 64.9, -23.3), P('spot', 5, 'Dolomites', 46.6, 12),
  P('spot', 5, 'Rila Mountains', 42.15, 23.35), P('spot', 6, 'Walensee', 47.12, 9.2),
];
