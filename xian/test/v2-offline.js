const assert=require('assert');const {createSandbox}=require('./harness');
const {G}=createSandbox();G.GameEngine.stop();const s=G.GameState.state;
const end=Date.now(),start=end-120000; s.lastSaved=start;s.pendingOffline=null;
s.alchemy.activeBuffs.cult={pill:'juqi',expiresAt:start+60000};
const base=G.Rates.cultPerSec(end);const off=G.SaveSystem.computeOffline(end/1000);
assert(Math.abs(off.cult-base*(60*1.3+60))<1e-6,'offline must split at buff expiry');
console.log('offline buff integration passed');
