import { useState } from 'react';
import Home from './pages/Home.jsx';
import Landing from './pages/Landing.jsx';

export default function App() {
  const [entered, setEntered] = useState(false);
  return entered ? <Home /> : <Landing onEnter={() => setEntered(true)} />;
}
