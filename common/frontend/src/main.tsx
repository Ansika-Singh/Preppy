import React from 'react';
import ReactDOM from 'react-dom/client';
import { LearnView } from './learn/LearnView';
import './learn/learn.css';
import './styles.css';

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);

root.render(
  <React.StrictMode>
    <LearnView isStandalone={true} />
  </React.StrictMode>,
);
