// Presentation labels only; API identifiers and real GTFS route names stay intact.
const labels = { SYN_A: 'M1', SYN_B: '14M', SYN_C: '21G' };
export function busLabel(value = '') {
  return String(value).replace(/SYN_[ABC](?:_R)?/g, id => labels[id.replace(/_R$/, '')]);
}
