// Synthetic MCP fixture. State belongs to this process, not to an external service.
import readline from 'node:readline';

let count = 0;
const tools = [
  { name: 'counter', description: 'Increment a synthetic in-memory counter.',
    inputSchema: { type: 'object', properties: {} } },
  { name: 'echo', description: 'Return synthetic text.',
    inputSchema: { type: 'object', properties: { text: { type: 'string' } },
      required: ['text'] } },
];

const respond = (id, result) =>
  process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');

readline.createInterface({ input: process.stdin }).on('line', line => {
  const message = JSON.parse(line);
  if (!Object.hasOwn(message, 'id')) return;
  switch (message.method) {
    case 'initialize':
      respond(message.id, {
        protocolVersion: message.params.protocolVersion,
        capabilities: { tools: {} },
        serverInfo: { name: 'byoi-synthetic-stdio-fixture', version: '1' },
      });
      break;
    case 'tools/list':
      respond(message.id, { tools });
      break;
    case 'tools/call':
      respond(message.id, {
        content: [{ type: 'text', text: message.params.name === 'counter'
          ? String(++count) : message.params.arguments.text }],
      });
      break;
    case 'ping':
      respond(message.id, {});
      break;
    default:
      process.stdout.write(JSON.stringify({
        jsonrpc: '2.0', id: message.id,
        error: { code: -32601, message: 'Method not found.' },
      }) + '\n');
  }
});
