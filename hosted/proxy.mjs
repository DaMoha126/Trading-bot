// Outbound transport uses the existing private host key; no inbound tunnel required.
import {createRelayServer} from './relay-server.mjs';
const server=createRelayServer({key:process.env.MT5_HOST_KEY||'',origin:process.env.PUBLIC_URL||process.env.RENDER_EXTERNAL_URL});
server.listen(Number(process.env.PORT||3000),'0.0.0.0');
process.on('SIGTERM',()=>server.shutdown());
process.on('SIGINT',()=>server.shutdown());
