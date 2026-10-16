importScripts('engine.js');
onmessage=({data})=>{try{let bars=data.bars;if(data.split)bars=bars.slice(Math.floor(bars.length*.7));postMessage({result:Forex.run(bars,data.config),bars});}catch(e){postMessage({error:e.message});}};
