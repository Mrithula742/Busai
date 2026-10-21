// Illustrative area anchors, not surveyed stops or road/GTFS geometry.
const anchors = {
  Madipakkam: [12.965, 80.198], Velachery: [12.978, 80.221],
  Guindy: [13.007, 80.212], 'T Nagar': [13.041, 80.234],
  'Chennai Central': [13.083, 80.275], Chennai: [13.083, 80.275],
  Tambaram: [12.925, 80.118], Kanchipuram: [12.835, 79.704],
  'Demo interchange': [13.01, 79.91],
};
export function demoPoints(route) {
  const points = route.stops.map(name => anchors[name]);
  return points.every(Boolean) ? points : [];
}
export function demoPosition(points, progress) {
  if (!points.length) return null;
  if (points.length === 1) return points[0];
  const p = ((progress % 1) + 1) % 1 * (points.length - 1);
  const i = Math.floor(p), fraction = p - i;
  return points[i].map((v, axis) => v + (points[i + 1][axis] - v) * fraction);
}
