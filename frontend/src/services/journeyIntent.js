const supportedPriorities = [
  ['less_crowd', /\b(low|less|fewer)\s+(crowd|people|passengers)\b/i],
  ['fewer_transfers', /\b(fewer|less)\s+transfers?\b|\bdirect\b/i],
  ['faster', /\b(fastest|quickest|faster)\b/i],
];

export function parseJourneyIntent(text) {
  const source = text.trim();
  const match = source.match(/^from\s+(.+?)\s+to\s+(.+)$/i);
  let destinationQuery = match?.[2]?.trim() || '';
  destinationQuery = destinationQuery.split(/\s+(?=(?:i want|please|with|and i|prefer|but|fastest|quickest|faster|low crowd|less crowd|fewer transfers|less walking|most reliable)\b)/i)[0].replace(/[.,!?]+$/,'').trim();
  const priority = supportedPriorities.find(([,pattern])=>pattern.test(source))?.[0] || '';
  const wait = source.match(/\b(?:wait|waiting)\s+(?:up\s+to\s+)?(\d{1,2})\s*(?:minutes?|mins?)\b/i);
  return { originQuery: match?.[1]?.trim() || '', destinationQuery, priority, maxWaitMinutes: wait ? Math.min(60,Number(wait[1])) : null,
    unsupportedPriority: /\b(reliable|reliability|less walking|shorter walk|comfortable)\b/i.test(source) ? 'This preference is understood but not ranked by the current journey planner.' : '' };
}
