export async function aiRequest(path, body, signal) {
  const response = await fetch(path, { ...(body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {}), signal });
  const data = await response.json().catch(()=>({}));
  if (!response.ok) throw new Error(typeof data.detail==='string' ? data.detail : `Request failed (${response.status}). Check your inputs and backend.`);
  return data;
}
export function plannerPayload(form, position) {
  return {...(form.useLocation ? {latitude:position.latitude,longitude:position.longitude} : {origin:form.origin}),destination:form.destination,departure_time:`${form.date}T${form.time}:00+05:30`,preference:form.preference,max_transfers:Number(form.maxTransfers),transfer_buffer:Number(form.buffer)};
}
