import './boardingScene.css';

function Passenger({ index, shirt, trousers, bag }) {
  return <g className={`boarding-passenger passenger-${index}`} style={{ '--shirt': shirt, '--trousers': trousers, '--bag': bag }}>
    <ellipse cx="0" cy="1" rx="12" ry="3" fill="#233c3820" />
    <g className="passenger-leg leg-back"><path d="M-3-24L-6-12-8 0"/><path className="shoe" d="M-8 0h8"/></g>
    <g className="passenger-leg leg-front"><path d="M3-24L6-12 7 0"/><path className="shoe" d="M7 0h7"/></g>
    <path d="M-7-46Q0-50 7-45L8-24H-7Z" fill="var(--shirt)"/>
    <path d="M-7-43L-12-29" stroke="#ad7959" strokeWidth="5" strokeLinecap="round"/>
    <rect x="-15" y="-43" width="10" height="19" rx="4" fill="var(--bag)"/>
    <path d="M5-43L11-31 16-34" stroke="#ad7959" strokeWidth="5" fill="none" strokeLinecap="round"/>
    <path d="M0-49v-6" stroke="#ad7959" strokeWidth="6"/>
    <ellipse cx="1" cy="-59" rx="7" ry="9" fill="#c39170"/>
    <path d="M-6-59Q-9-72 4-69Q12-66 8-59L4-64-5-63Z" fill="#29332e"/>
  </g>;
}

export default function BoardingScene() {
  return <div className="hero-art boarding-art">
    <div className="art-orbit orbit-one"/><div className="art-orbit orbit-two"/><div className="sun-disc"/>
    <div className="route-ribbon">YOUR JOURNEY <b>→</b> STARTS HERE</div>
    <svg className="boarding-illustration" viewBox="0 0 680 460" role="img" aria-labelledby="boarding-title boarding-description">
      <title id="boarding-title">Passengers boarding a city bus</title>
      <desc id="boarding-description">An illustrative animation: a green and ivory city bus arrives, opens its doors, lets three passengers board in sequence, and departs.</desc>
      <defs>
        <linearGradient id="coach-paint" x2="0" y2="1"><stop stopColor="#fffefa"/><stop offset=".52" stopColor="#e9eee9"/><stop offset="1" stopColor="#b8cac0"/></linearGradient>
        <linearGradient id="coach-glass" x2=".3" y2="1"><stop stopColor="#1d353c"/><stop offset="1" stopColor="#527078"/></linearGradient>
        <linearGradient id="coach-green" x2="0" y2="1"><stop stopColor="#328577"/><stop offset="1" stopColor="#105244"/></linearGradient>
        <linearGradient id="glass-glint"><stop stopColor="#fff" stopOpacity="0"/><stop offset=".5" stopColor="#fff" stopOpacity=".24"/><stop offset="1" stopColor="#fff" stopOpacity="0"/></linearGradient>
        <filter id="coach-shadow"><feGaussianBlur stdDeviation="7"/></filter>
      </defs>
      <g opacity=".42" fill="#dbe6df">
        <path d="M40 281V151h47v130M94 281V111h55v170M164 281V169h38v112M512 281V130h45v151M567 281V172h55v109"/>
        <path d="M105 111V96h32v15M525 130v-17h18v17"/>
      </g>
      <path d="M20 360H660" stroke="#c4d3c9" strokeWidth="2"/>
      <path d="M20 374H660" stroke="#e0e7df" strokeWidth="12"/>
      <path d="M55 405h105m55 0h105m55 0h105m55 0h70" stroke="#d3ded4" strokeWidth="3"/>
      <g className="bus-stop-sign"><path d="M67 217v141" stroke="#7f9387" strokeWidth="4"/><rect x="47" y="191" width="40" height="39" rx="9" fill="#176b5b"/><rect x="56" y="199" width="22" height="20" rx="4" fill="none" stroke="white" strokeWidth="2"/><path d="M59 209h16m-15 9v4m14-4v4" stroke="white" strokeWidth="2"/></g>
      <g className="coach-cycle">
        <ellipse cx="338" cy="349" rx="248" ry="12" fill="#294b3930" filter="url(#coach-shadow)"/>
        <g className="coach-suspension">
          <path d="M100 183Q101 160 125 159H522Q549 161 559 187L571 285V320Q571 333 554 333H107Q91 332 91 316V203Q91 188 100 183Z" fill="url(#coach-paint)" stroke="#8fa89b" strokeWidth="1.5"/>
          <path d="M98 266H569V315Q569 332 550 332H106Q92 332 92 315V282Z" fill="url(#coach-green)"/>
          <path d="M97 263H568" stroke="#d5ae5c" strokeWidth="5"/>
          <path d="M119 158h388l-9-8H145Z" fill="#d2ddd6" stroke="#a6b8ac"/>
          <rect x="216" y="143" width="142" height="14" rx="6" fill="#dce5de" stroke="#adbbaf"/>
          <rect x="109" y="180" width="298" height="75" rx="5" fill="url(#coach-glass)" stroke="#a7b9ae" strokeWidth="3"/>
          {[125,181,237,293,349].map(x=><g key={x}><path d={`M${x} 238v-14q10-9 20 0v14`} fill="#8aa59d" opacity=".4"/><circle cx={x+10} cy="213" r="7" fill="#c5b49c" opacity=".4"/></g>)}
          <path d="M168 181v73m59-73v73m59-73v73m59-73v73" stroke="#b2c1b8" strokeWidth="4"/>
          <path d="M121 183h53l55 69h-51Zm157 0h29l56 69h-29Z" fill="url(#glass-glint)"/>
          <path d="M487 181h40q14 1 18 19l6 53h-64Z" fill="url(#coach-glass)" stroke="#b6c6ba" strokeWidth="3"/>
          <path d="M537 217l14 23m-10 2 9-2" stroke="#182d30" strokeWidth="2"/>
          <rect x="419" y="176" width="59" height="28" rx="3" fill="#152c29"/>
          <text x="448" y="194" textAnchor="middle" fill="#f4ce78" fontSize="10" fontFamily="monospace">01 CITY</text>
          <rect x="419" y="209" width="59" height="117" rx="3" fill="#172d2b"/>
          <path d="M423 319h51m-51-7h51m-51-7h51" stroke="#a5b2a3" strokeWidth="3"/>
          <g className="coach-door door-left"><path d="M420 210h28v95h-28Z" fill="#759189" stroke="#afc1b4" strokeWidth="2"/><path d="M424 216h19v64h-19Z" fill="url(#coach-glass)"/><path d="M443 283v13" stroke="#ece5bd" strokeWidth="2"/></g>
          <g className="coach-door door-right"><path d="M449 210h28v95h-28Z" fill="#759189" stroke="#afc1b4" strokeWidth="2"/><path d="M454 216h18v64h-18Z" fill="url(#coach-glass)"/><path d="M453 283v13" stroke="#ece5bd" strokeWidth="2"/></g>
          <text x="267" y="295" textAnchor="middle" fill="#f4faf4" fontSize="16" fontWeight="700" letterSpacing="3">BUSSURE</text>
          <text x="267" y="310" textAnchor="middle" fill="#c1d9cc" fontSize="6.5" letterSpacing="2">YOUR CITY. YOUR JOURNEY.</text>
          <path d="M97 315h27m79 0h199m91 0h70" stroke="#90aea0" strokeWidth="2"/>
          <path d="M128 332a36 36 0 0 1 72 0m277 0a36 36 0 0 1 72 0" fill="#263c34"/>
          {[164,513].map(x=><g key={x} className="coach-wheel" style={{transformOrigin:`${x}px 330px`}}><circle cx={x} cy="330" r="28" fill="#23302d"/><circle cx={x} cy="330" r="19" fill="#73817c" stroke="#b5bfb7" strokeWidth="3"/><circle cx={x} cy="330" r="8" fill="#ced5cb"/>{[0,60,120].map(a=><path key={a} d={`M${x} 315v30`} stroke="#bcc7bd" strokeWidth="2" transform={`rotate(${a} ${x} 330)`}/>)}</g>)}
          <rect x="558" y="279" width="10" height="19" rx="4" fill="#ffe7a2"/>
          <rect x="93" y="280" width="5" height="16" rx="2" fill="#c66345"/>
          <path d="M551 192h24v32h-8v-27h-16" fill="#2e4740"/>
          <rect x="552" y="311" width="18" height="5" rx="2" fill="#a9b6ab"/>
        </g>
      </g>
      <Passenger index={1} shirt="#c79350" trousers="#374e57" bag="#6b5140"/>
      <Passenger index={2} shirt="#698e9c" trousers="#34443f" bag="#c8a36a"/>
      <Passenger index={3} shirt="#a86e64" trousers="#475163" bag="#465f4d"/>
    </svg>
    <div className="float-chip chip-live boarding-status"><span className="live-dot"/><span className="status-arriving">ARRIVING</span><span className="status-boarding">ALL ABOARD</span><span className="status-departing">ON OUR WAY</span></div>
    <div className="float-chip chip-stop"><span>◎</span> A SMOOTHER START <b>One step closer.</b></div>
    <span className="boarding-caption">A little preview of the journey ahead</span>
  </div>;
}
