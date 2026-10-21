import {test,expect} from '@playwright/test';
import {spawn} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const backend=process.env.E2E_BACKEND||'http://127.0.0.1:8024';
test('low-crowd search, transfer itinerary, moving GPS, refreshed My Journey and insights',async({page,request})=>{
  const existing=await (await request.get(`${backend}/api/network-events`)).json();for(const e of existing.filter(e=>e.event_id.startsWith('AI_E2E_')))await request.post(`${backend}/api/network-events/${e.event_id}/clear`);
  let eventId=null;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const simulator=spawn(path.join(root,'.venv/bin/python'),['-B','simulator/multi_bus_simulator.py','--backend',backend,'--config','frontend/tests/fixtures/synthetic_simulator.json'],{cwd:root,stdio:'ignore'});
  try{
    await page.goto('/');await page.getByRole('button',{name:/Start journey/}).click();
    const nav=page.getByRole('navigation',{name:'Main navigation'});await nav.getByRole('button',{name:'AI Journey',exact:true}).click();
    const ai=page.getByRole('region',{name:'Integrated AI journey system'});
    await ai.getByLabel('AI destination',{exact:true}).selectOption('KAN');await ai.getByLabel('Departure date (IST)').fill('2026-10-17');
    await ai.getByLabel('AI preference',{exact:true}).selectOption('less_crowd');await ai.getByRole('button',{name:'Find AI journeys'}).click();
    await expect(ai.getByTestId('ai-option').first()).toBeVisible();expect(await ai.getByTestId('ai-option').count()).toBeGreaterThanOrEqual(2);
    await expect(ai).toContainText('SYNTHETIC_TRAINED_DEEP_LEARNING');
    const before=parseFloat(await ai.getByTestId('ai-option').filter({has:page.getByRole('heading',{name:'SYN_B → SYN_C',exact:true})}).locator('dd').nth(1).textContent());
    eventId=`AI_E2E_${Date.now()}`;
    const eventResponse=await request.post(`${backend}/api/network-events`,{data:{event_id:eventId,event_type:'CONGESTION',route_id:'SYN_B',severity:'HIGH',latitude:12.965,longitude:80.198,start_time:'2026-10-17T07:00:00+05:30',end_time:new Date(Date.now()+8*3600000).toISOString(),description:'SYNTHETIC browser test: congestion changes itinerary estimates'}});
    expect(eventResponse.status()).toBe(201);
    await ai.getByRole('button',{name:'Refresh estimates',exact:true}).click();
    await expect.poll(async()=>parseFloat(await ai.getByTestId('ai-option').filter({has:page.getByRole('heading',{name:'SYN_B → SYN_C',exact:true})}).locator('dd').nth(1).textContent())).toBeGreaterThan(before);
    await request.post(`${backend}/api/network-events/${eventId}/clear`);
    await expect(ai.getByRole('button',{name:'Refresh estimates',exact:true})).toBeEnabled();await ai.getByRole('button',{name:'Refresh estimates',exact:true}).click();
    await expect(ai.getByRole('button',{name:'Refresh estimates',exact:true})).toBeEnabled();
    await ai.getByTestId('ai-option').nth(1).getByRole('button',{name:'Select this journey'}).click();await expect(ai.getByTestId('ai-option').nth(1).getByRole('button')).toHaveAttribute('aria-pressed','true');
    await expect(ai.getByTestId('ai-selected')).toContainText(/includes 5(?:\.0)? min transfer buffer/);
    const marker=ai.locator('.bus-marker[title^="SIM_SYN_A ·"]');await expect(marker).toBeVisible();const first=await marker.getAttribute('style');await expect.poll(()=>marker.getAttribute('style'),{timeout:8000}).not.toBe(first);
    await ai.getByRole('button',{name:'Track in My Journey'}).click();await expect(ai.getByRole('heading',{name:'Your selected journey'})).toBeVisible();
    const updated=await ai.locator('.ai-result-heading small').textContent();await expect.poll(()=>ai.locator('.ai-result-heading small').textContent(),{timeout:16000}).not.toBe(updated);await expect(ai.getByTestId('ai-selected')).toContainText('SYN_C');
    await nav.getByRole('button',{name:'Model Insights',exact:true}).click();await expect(ai).toContainText('LOADED_AND_VALIDATED');await expect(ai).toContainText('Held-out MAE');
    await nav.getByRole('button',{name:'AI Journey',exact:true}).click();await ai.getByText('Synthetic disruption controls',{exact:true}).click();await ai.getByRole('button',{name:'Activate synthetic scenario'}).click();await expect(ai.getByRole('button',{name:'Clear scenario'})).toBeVisible();await ai.getByRole('button',{name:'Clear scenario'}).click();await expect(ai.getByRole('button',{name:'Clear scenario'})).toHaveCount(0);
    await page.screenshot({path:'test-results/ai-system-desktop.png',fullPage:true});expect(errors).toEqual([]);
  }finally{simulator.kill('SIGTERM');if(eventId)await request.post(`${backend}/api/network-events/${eventId}/clear`);}
});
test('integrated planner remains usable on mobile',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.goto('/');await page.getByRole('button',{name:/Start journey/}).click();await page.getByRole('navigation',{name:'Main navigation'}).getByRole('button',{name:'AI Journey',exact:true}).click();
  const ai=page.getByRole('region',{name:'Integrated AI journey system'});await ai.getByLabel('Departure date (IST)').fill('2026-10-17');await ai.getByRole('button',{name:'Find AI journeys'}).click();await expect(ai.getByTestId('ai-option').first()).toBeVisible();await expect(ai).toContainText('SYNTHETIC_TRAINED_DEEP_LEARNING');expect(await ai.evaluate(el=>el.scrollWidth>el.clientWidth+2)).toBe(false);await page.screenshot({path:'test-results/ai-system-mobile.png',fullPage:true});
});
