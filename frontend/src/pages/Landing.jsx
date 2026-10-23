import BoardingScene from '../components/BoardingScene.jsx';
import DevBeezLogo from '../components/DevBeezLogo.jsx';
import { useState } from 'react';

const chapters = [
  ['01', 'Know the wait', 'Scheduled service information, with live updates where a bus signal is available.'],
  ['02', 'Follow live signals', 'See the last confirmed bus position and where that signal came from.'],
  ['03', 'Choose with confidence', 'Compare valid GTFS journeys and see what is known at a glance.'],
];

export default function Landing({ onEnter }) {
  const [exiting,setExiting]=useState(false);
  function enter(){if(exiting)return;setExiting(true);setTimeout(onEnter,520);}
  return <main className={`landing ${exiting?'is-exiting':''}`}>
    <header className="landing-nav"><a className="brand" href="#top"><span className="brand-icon">↗</span><span>Bus<span className="brand-light">Sure</span><small>JOURNEYS, IN VIEW</small></span></a><div className="landing-header-right"><span className="landing-tag">PUBLIC TRANSPORT, MADE CLEAR</span><DevBeezLogo /></div></header>
    <section className="landing-hero" id="top"><div className="hero-copy"><span className="eyebrow">A CALMER WAY TO GET THERE</span><h1>Know your journey<br/>before you <em>board.</em></h1><p>Explore nearby stops, follow buses and compare your public transport options with BusSure.</p><button className="primary-cta" onClick={enter}>Start journey <span>↗</span></button><div className="hero-proof"><span className="proof-dot"/> GTFS schedules · Live bus signals · Clear sources</div></div>
      <BoardingScene />
    </section>
    <section className="story-section"><div className="story-heading"><span className="eyebrow">THE WHOLE JOURNEY, MADE CLEAR</span><h2>Good travel decisions<br/>start with better context.</h2></div><div className="story-steps">{chapters.map(([n, title, copy]) => <article className="story-step" key={n}><span className="step-number">{n}</span><div><h3>{title}</h3><p>{copy}</p></div><span className="step-arrow">↗</span></article>)}</div><div className="landing-bottom"><span>Schedules and live signals are shown with their source.</span><button className="primary-cta" onClick={enter}>Enter BusSure <span>→</span></button></div></section>
  </main>;
}
