import {test,expect} from '@playwright/test';
import {spawn} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const backend=process.env.E2E_BACKEND||'http://127.0.0.1:8030';
async function enter(page){await page.goto('/');await page.getByRole('button',{name:/Start journey/}).click();await page.getByRole('navigation',{name:'Main navigation'}).getByRole('button',{name:'AI Journey',exact:true}).click();}

test('assistant, comparison, isolated studio, dashboard and notification permission',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{window.__notificationRequests=0;class NotificationDouble{static permission='default';static async requestPermission(){window.__notificationRequests++;this.permission='denied';return 'denied';}constructor(){throw new Error('Permission denied');}}Object.defineProperty(window,'Notification',{value:NotificationDouble,configurable:true});});
  const simulator=spawn(path.join(root,'.venv/bin/python'),['-B','simulator/multi_bus_simulator.py','--backend',backend,'--config','frontend/tests/fixtures/synthetic_simulator.json'],{cwd:root,stdio:'ignore'});
  try{
    await enter(page);const ai=page.getByRole('region',{name:'Integrated AI journey system'});
    await ai.getByLabel('Departure date (IST)').fill('2026-10-17');
    const assistant=ai.getByRole('region',{name:'Natural language journey assistant'});
    await assistant.getByLabel('Your journey request').fill('Take me to Stop G at 08:00 with low crowd and fewer transfers.');
    await assistant.getByRole('button',{name:'Interpret request'}).click();await expect(assistant.getByText('Please supply origin.',{exact:true})).toBeVisible();
    await assistant.getByLabel('Choose missing origin').selectOption('MAD');await assistant.getByRole('button',{name:'Use interpreted journey'}).click();
    await expect(ai.getByTestId('ai-option').first()).toBeVisible();
    const comparison=ai.getByRole('region',{name:'Smart journey comparison'});await expect(comparison.locator('.compare-tile')).toHaveCount(3);await comparison.getByRole('button',{name:'Compare on map'}).last().click();await comparison.screenshot({path:'test-results/showcase-comparison.png'});
    const studio=ai.getByRole('region',{name:'What-if simulation studio'});await studio.getByLabel('Traffic severity').selectOption('1.6');const demand=studio.getByLabel(/Passenger demand/);await demand.focus();await demand.press('Home');for(let i=0;i<10;i++)await demand.press('ArrowRight');await studio.getByRole('button',{name:'Preview scenario'}).click();await expect(studio.getByTestId('studio-result')).toContainText('No event or GPS state is changed');await expect(studio.getByRole('table')).toBeVisible();await studio.screenshot({path:'test-results/showcase-studio.png'});await studio.getByRole('button',{name:'Reset studio'}).click();await expect(studio.getByTestId('studio-result')).toHaveCount(0);
    const alerts=ai.getByRole('region',{name:'Smart boarding alerts'});expect(await page.evaluate(()=>window.__notificationRequests)).toBe(0);await alerts.getByRole('button',{name:'Enable browser notifications'}).click();await expect(alerts).toContainText('Browser permission: denied');expect(await page.evaluate(()=>window.__notificationRequests)).toBe(1);
    const nav=page.getByRole('navigation',{name:'Main navigation'});await expect(nav.getByRole('button',{name:'Digital Twin',exact:true})).toHaveCount(0);
    await nav.getByRole('button',{name:'Model Insights',exact:true}).click();const dashboard=ai.getByRole('region',{name:'AI model performance dashboard'});await expect(dashboard.getByRole('img',{name:'Predicted versus actual held-out synthetic values'})).toBeVisible();await expect(dashboard).toContainText('1932 × 7');await dashboard.getByLabel('Performance model').selectOption('eta');await expect(dashboard).toContainText('644 × 18');await dashboard.getByLabel('Evaluation node').selectOption({index:1});await dashboard.getByText('Accessible test-value table',{exact:true}).click();await expect(dashboard.locator('tbody tr')).toHaveCount(64);await dashboard.getByText('Accessible test-value table',{exact:true}).click();await dashboard.screenshot({path:'test-results/showcase-performance.png'});expect(errors).toEqual([]);
  }finally{simulator.kill('SIGTERM');}
});

test('showcase mobile layout and recoverable studio errors',async({page})=>{
  await page.setViewportSize({width:390,height:844});await enter(page);const ai=page.getByRole('region',{name:'Integrated AI journey system'});await ai.getByLabel('Departure date (IST)').fill('2026-10-17');await ai.getByRole('button',{name:'Find AI journeys'}).click();await expect(ai.getByTestId('ai-option').first()).toBeVisible();
  await page.route('**/api/ai/what-if',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Preview temporarily unavailable. Retry.'})}));
  const studio=ai.getByRole('region',{name:'What-if simulation studio'});await studio.getByRole('button',{name:'Preview scenario'}).click();await expect(studio.getByRole('alert')).toContainText('Retry');await studio.getByRole('button',{name:'Reset studio'}).click();await expect(studio.getByRole('alert')).toHaveCount(0);
  expect(await ai.evaluate(el=>el.scrollWidth>el.clientWidth+2)).toBe(false);expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);await ai.screenshot({path:'test-results/showcase-mobile.png'});
});

test('in-app boarding fallback renders and does not repeat after dismissal',async({page})=>{
  // API fixture controls timing only; normal journey values still come from FastAPI.
  let rid='SYN_B';
  await page.addInitScript(()=>{class Denied{static permission='denied';static requestPermission(){throw new Error('Must not ask automatically');}constructor(){throw new Error('Must not notify without permission');}}Object.defineProperty(window,'Notification',{value:Denied,configurable:true});});
  await page.route('**/api/ai/journeys',async route=>{const response=await route.fetch();const data=await response.json();rid=data.options[0].legs[0].route_id;for(const o of data.options){o.arrival_time=new Date(Date.now()+60*60000).toISOString();o.legs[0].departure_time=new Date(Date.now()+2*60000).toISOString();}await route.fulfill({response,json:data});});
  await page.route('**/api/twin**',route=>route.fulfill({json:{vehicles:[{bus_id:'PHONE_ALERT_UI_FIXTURE',route_id:rid,trip_id:'UI_FIXTURE',source:'REAL_PHONE_GPS',timestamp:new Date().toISOString(),status:'MOVING',tracking_status:'FRESH',boarding_eta_minutes:2,next_stop_eta_minutes:null,next_stop_id:'CEN',next_stop_name:'Chennai Central',occupancy_ratio:null,simulation_delay_minutes:0}],stale_seconds:45}}));
  await enter(page);const ai=page.getByRole('region',{name:'Integrated AI journey system'});await ai.getByLabel('Departure date (IST)').fill('2026-10-17');await ai.getByRole('button',{name:'Find AI journeys'}).click();const alerts=ai.getByRole('region',{name:'Smart boarding alerts'});await expect(alerts.locator('.boarding-alert')).toHaveCount(1);await expect(alerts).toContainText('Real phone GPS');await alerts.getByRole('button',{name:'Dismiss alert'}).click();await ai.getByRole('button',{name:'Refresh estimates',exact:true}).click();await expect(ai.getByRole('button',{name:'Refresh estimates',exact:true})).toBeEnabled();await expect(alerts.locator('.boarding-alert')).toHaveCount(0);
});
